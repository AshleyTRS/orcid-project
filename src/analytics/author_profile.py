"""
Author profile queries: one author's details, summary statistics and works.

A publication is stored once per harvested co-author, and ORCID records often
hold the same work several times (imported from different sources). Works are
therefore collapsed to one entry per work_key (see src/works/work_key.py).
"""
import logging
import re
from typing import Dict, Optional
from urllib.parse import urlparse

from src.orcid.affiliation import AFFILIATED_AUTHOR, UAEH_WORK

logger = logging.getLogger(__name__)

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
SORT_OPTIONS = {
    "newest": {"publication_year": -1, "sort_title": 1},
    "oldest": {"publication_year": 1, "sort_title": 1},
    "title": {"sort_title": 1, "publication_year": -1},
}
TOP_BREAKDOWN = 8
TOP_COLLABORATORS = 5
MAX_OBSERVED_NAMES = 8

# Characters ignored at the start/end of a title when sorting by title
_TITLE_TRIM_CHARS = " \"'`“”‘’«»¿¡([{*-"

# One row per unique work. A document not yet keyed (harvested before the
# work_key migration ran) counts as its own work rather than being dropped.
_WORK_KEY = {"$ifNull": ["$work_key", {"$toString": "$_id"}]}

_GROUP_WORKS = {
    "$group": {
        "_id": _WORK_KEY,
        # $max prefers a record that has the DOI over a linked no-DOI duplicate
        "doi": {"$max": "$doi"},
        "title": {"$first": "$title"},
        "publication_year": {"$max": "$publication_year"},
        "type": {"$first": "$type"},
        "journal_title": {"$max": "$journal_title"},
        "contributors": {"$first": "$contributors.credit_name"},
        # every copy of the work: co-authors linked on one copy may be missing on another
        "contributor_ids": {"$push": "$contributors.orcid_id"},
        "topics": {"$first": "$topics.display_name"},
        "is_oa": {"$max": {"$eq": ["$is_oa", True]}},
        # open-access status is only known for works enriched from OpenAlex (by DOI)
        "oa_checked": {"$max": {"$eq": [{"$type": "$is_oa"}, "bool"]}},
        "oa_url": {"$max": "$oa_url"},
    }
}


def is_valid_orcid(orcid_id: str) -> bool:
    return bool(ORCID_PATTERN.match(orcid_id or ""))


def _author_match(orcid_id: str) -> Dict:
    """UAEH works the author harvested themselves or appears on as a contributor."""
    return {**UAEH_WORK, "$or": [{"orcid_id": orcid_id}, {"contributors.orcid_id": orcid_id}]}


def is_affiliated_author(db, orcid_id: str) -> bool:
    """True when the researcher is in the dataset and affiliated with UAEH (see src/orcid/affiliation.py)."""
    return db.orcids.count_documents({"orcid_id": orcid_id, **AFFILIATED_AUTHOR}, limit=1) > 0


# One row per unique work, topics listed once (a topic repeated on a work counts once)
_UNIQUE_TOPICS = {"$addFields": {"topics": {"$setUnion": [{"$ifNull": ["$topics", []]}]}}}


def _filter_match(filters: Optional[Dict], exclude: Optional[str] = None) -> Dict:
    """
    $match on unique works for the given filters, leaving out the one named by exclude.

    Args:
        filters: {"topics": [str], "types": [str], "oa": bool,
                  "year_from": int | None, "year_to": int | None}; a work matches
            when it has any of the topics and any of the types
        exclude: "topics", "types", "oa" or "years" - lets a facet count its own
            values as if it were not applied, so its other options stay visible
    """
    filters = filters or {}
    match = {}
    if exclude != "topics" and filters.get("topics"):
        match["topics"] = {"$in": list(filters["topics"])}
    if exclude != "types" and filters.get("types"):
        match["type"] = {"$in": list(filters["types"])}
    if exclude != "oa" and filters.get("oa"):
        match["is_oa"] = True
    if exclude != "years":
        years = {}
        if filters.get("year_from") is not None:
            years["$gte"] = filters["year_from"]
        if filters.get("year_to") is not None:
            years["$lte"] = filters["year_to"]
        if years:
            match["publication_year"] = years
    return match


def _safe_url(url: Optional[str]) -> Optional[str]:
    """Only pass through http(s) links so stored data can't inject other schemes."""
    if url and urlparse(url).scheme in ("http", "https"):
        return url
    return None


def _is_pdf_link(url: str) -> bool:
    """Heuristic: the link points at a PDF or a download rather than a landing page."""
    lowered = url.lower()
    path = urlparse(lowered).path
    return path.endswith(".pdf") or "/pdf" in path or "/download" in path


def _collaborators(db, orcid_id: str) -> list:
    """
    Everyone with an ORCID iD on any record of the author's works, as record
    owner or linked contributor, with the number of works shared, most first.

    All records of each work (work_key) count, including a co-author's own
    copy that does not link this author, the same way the co-authorship
    network builds its edges.

    Returns:
        [{"_id": orcid_id, "count": shared works}]
    """
    keys = [k for k in db.works.distinct("work_key", _author_match(orcid_id)) if k]
    if not keys:
        return []
    return list(db.works.aggregate([
        {"$match": {"work_key": {"$in": keys}, **UAEH_WORK}},
        {"$group": {
            "_id": "$work_key",
            "owners": {"$addToSet": "$orcid_id"},
            "contributors": {"$push": "$contributors.orcid_id"},
        }},
        {"$project": {"ids": {"$setDifference": [
            {"$setUnion": ["$owners", {"$reduce": {
                "input": "$contributors", "initialValue": [],
                "in": {"$concatArrays": ["$$value", {"$ifNull": ["$$this", []]}]},
            }}]},
            [orcid_id, None],
        ]}}},
        {"$unwind": "$ids"},
        {"$group": {"_id": "$ids", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ], allowDiskUse=True))


def _collaborator_details(db, rows) -> list:
    """Name and author-page availability for [{"_id": orcid, "count": shared works}]."""
    ids = [row["_id"] for row in rows]
    if not ids:
        return []
    known = {}
    for author in db.orcids.find({"orcid_id": {"$in": ids}},
                                 {"_id": 0, "orcid_id": 1, "given_names": 1, "family_names": 1,
                                  "credit_name": 1, "uaeh_affiliated": 1}):
        name = " ".join(f"{author.get('given_names') or ''} {author.get('family_names') or ''}".split())
        known[author["orcid_id"]] = (name or (author.get("credit_name") or "").strip(), bool(author.get("uaeh_affiliated")))
    # Researchers outside the dataset: the name they are credited under most often
    credited = {doc["_id"]["orcid"]: doc["_id"]["name"] for doc in db.works.aggregate([
        {"$match": {"contributors.orcid_id": {"$in": ids}}},
        {"$unwind": "$contributors"},
        {"$match": {"contributors.orcid_id": {"$in": ids}, "contributors.credit_name": {"$nin": [None, ""]}}},
        {"$group": {"_id": {"orcid": "$contributors.orcid_id", "name": "$contributors.credit_name"}, "count": {"$sum": 1}}},
        {"$sort": {"count": 1}},
    ])}
    return [{
        "orcid_id": row["_id"],
        "name": known.get(row["_id"], ("", False))[0] or " ".join((credited.get(row["_id"]) or "").split()) or None,
        "shared_works": row["count"],
        "in_dataset": known.get(row["_id"], ("", False))[1],
    } for row in rows]


def get_author_profile(db, orcid_id: str) -> Optional[Dict]:
    """
    Return an author's details and summary statistics, or None if the
    researcher is unknown or not affiliated with UAEH.

    Returns:
        {
            "orcid_id": str, "name": str, "observed_names": [str],
            "institutions": [str], "orcid_works_count": int | None,
            "stats": {"works", "open_access", "open_access_checked", "coauthors",
                      "first_year", "last_year"},
            "per_year": [{"year", "count"}], "topics": [{"value", "count"}],
            "types": [{"value", "count"}], "topics_total": int, "types_total": int,
            "top_collaborators": [{"orcid_id", "name", "shared_works", "in_dataset"}]
        }

    topics and types hold the TOP_BREAKDOWN most frequent values; *_total is
    the number of distinct values (get_author_facets returns all of them).
    Co-authors are counted like the co-authorship network (see _collaborators);
    top_collaborators lists the TOP_COLLABORATORS with the most shared works.
    """
    logger.info(f"Building author profile for {orcid_id}")
    author = db.orcids.find_one(
        {"orcid_id": orcid_id, **AFFILIATED_AUTHOR},
        # emails are deliberately never read or returned
        {"_id": 0, "given_names": 1, "family_names": 1, "credit_name": 1,
         "other_names": 1, "institution_names": 1, "works_count": 1},
    )

    values = lambda field: [
        {"$unwind": f"${field}"},
        {"$match": {field: {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
    ]
    breakdown = lambda field: values(field) + [{"$sort": {"count": -1, "_id": 1}}, {"$limit": TOP_BREAKDOWN}]
    pipeline = [
        {"$match": _author_match(orcid_id)},
        _GROUP_WORKS,
        _UNIQUE_TOPICS,
        {"$facet": {
            "totals": [{"$group": {
                "_id": None,
                "works": {"$sum": 1},
                "open_access": {"$sum": {"$cond": ["$is_oa", 1, 0]}},
                "open_access_checked": {"$sum": {"$cond": ["$oa_checked", 1, 0]}},
                "first_year": {"$min": "$publication_year"},
                "last_year": {"$max": "$publication_year"},
            }}],
            "per_year": [
                {"$match": {"publication_year": {"$ne": None}}},
                {"$group": {"_id": "$publication_year", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ],
            "types": breakdown("type"),
            "topics": breakdown("topics"),
            "types_total": values("type") + [{"$count": "count"}],
            "topics_total": values("topics") + [{"$count": "count"}],
        }},
    ]
    facets = next(db.works.aggregate(pipeline))
    totals = facets["totals"][0] if facets["totals"] else None

    if author is None:
        return None
    collaborators = _collaborators(db, orcid_id)

    # Names this author is credited under on their papers
    observed = [
        doc["_id"].strip() for doc in db.works.aggregate([
            {"$match": {"contributors.orcid_id": orcid_id}},
            {"$unwind": "$contributors"},
            {"$match": {"contributors.orcid_id": orcid_id, "contributors.credit_name": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$contributors.credit_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": MAX_OBSERVED_NAMES},
        ])
    ]

    author = author or {}
    clean = lambda value: " ".join(value.split()) if isinstance(value, str) else ""
    full_name = clean(f"{author.get('given_names') or ''} {author.get('family_names') or ''}")
    name = full_name or clean(author.get("credit_name")) or (observed[0] if observed else orcid_id)
    names = [clean(n) for n in [author.get("credit_name"), *(author.get("other_names") or []), *observed]]
    names = [n for n in names if n]
    observed_names = [n for i, n in enumerate(names) if n != name and n not in names[:i]]

    totals = totals or {"works": 0, "open_access": 0, "open_access_checked": 0,
                        "first_year": None, "last_year": None}
    return {
        "orcid_id": orcid_id,
        "name": name,
        "observed_names": observed_names,
        "institutions": sorted(set(author.get("institution_names") or []), key=str.lower),
        "orcid_works_count": author.get("works_count"),
        "stats": {
            "works": totals["works"],
            "open_access": totals["open_access"],
            "open_access_checked": totals["open_access_checked"],
            "coauthors": len(collaborators),
            "first_year": totals["first_year"],
            "last_year": totals["last_year"],
        },
        "per_year": [{"year": d["_id"], "count": d["count"]} for d in facets["per_year"]],
        "topics": [{"value": d["_id"], "count": d["count"]} for d in facets["topics"]],
        "types": [{"value": d["_id"], "count": d["count"]} for d in facets["types"]],
        "top_collaborators": _collaborator_details(db, collaborators[:TOP_COLLABORATORS]),
        "topics_total": facets["topics_total"][0]["count"] if facets["topics_total"] else 0,
        "types_total": facets["types_total"][0]["count"] if facets["types_total"] else 0,
    }


def get_author_facets(db, orcid_id: str, filters: Optional[Dict] = None) -> Dict:
    """
    Every topic, type and year of an author's unique works with counts, plus
    open-access and total counts, for the filtered works page.

    Each facet is counted with all the other filters applied but not its own,
    so checking one topic still shows the counts of the remaining topics.

    Returns:
        {
            "total": int,                                  works matching all filters
            "topics": [{"value", "count"}], "types": [{"value", "count"}],
            "years": [{"year", "count"}],
            "open_access": {"count": int, "total": int}
        }
    """
    def counted(field, exclude, sort):
        stages = [{"$match": _filter_match(filters, exclude)}]
        if field == "topics":
            stages.append({"$unwind": "$topics"})
        return stages + [
            {"$match": {field: {"$nin": [None, ""]}}},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$sort": sort},
        ]

    pipeline = [
        {"$match": _author_match(orcid_id)},
        _GROUP_WORKS,
        _UNIQUE_TOPICS,
        {"$facet": {
            "total": [{"$match": _filter_match(filters)}, {"$count": "count"}],
            "topics": counted("topics", "topics", {"count": -1, "_id": 1}),
            "types": counted("type", "types", {"count": -1, "_id": 1}),
            "years": counted("publication_year", "years", {"_id": 1}),
            "open_access": [
                {"$match": _filter_match(filters, "oa")},
                {"$group": {"_id": None, "total": {"$sum": 1},
                            "count": {"$sum": {"$cond": ["$is_oa", 1, 0]}}}},
            ],
        }},
    ]
    facets = next(db.works.aggregate(pipeline))
    oa = facets["open_access"][0] if facets["open_access"] else {"count": 0, "total": 0}
    return {
        "total": facets["total"][0]["count"] if facets["total"] else 0,
        "topics": [{"value": d["_id"], "count": d["count"]} for d in facets["topics"]],
        "types": [{"value": d["_id"], "count": d["count"]} for d in facets["types"]],
        "years": [{"year": d["_id"], "count": d["count"]} for d in facets["years"]],
        "open_access": {"count": oa["count"], "total": oa["total"]},
    }


def get_author_works(
    db,
    orcid_id: str,
    page: int = 1,
    limit: int = 20,
    sort: str = "newest",
    open_access_only: bool = False,
    filters: Optional[Dict] = None
) -> Dict:
    """
    Return one page of an author's unique works.

    Args:
        filters: optional topics/types/year filters (see _filter_match);
            open_access_only is the same as filters["oa"]

    Each work has: doi, title, publication_year, type, journal_title,
    contributors (names), is_oa, oa_url (http/https only) and oa_is_pdf.
    """
    limit = max(1, min(limit, 100))
    page = max(1, page)
    sort_spec = SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])

    filters = {**(filters or {}), "oa": open_access_only or (filters or {}).get("oa")}
    pipeline = [{"$match": _author_match(orcid_id)}, _GROUP_WORKS, _UNIQUE_TOPICS]
    match = _filter_match(filters)
    if match:
        pipeline.append({"$match": match})
    pipeline += [
        # Case-insensitive title order that ignores leading quotes/brackets
        {"$addFields": {"sort_title": {"$trim": {
            "input": {"$toLower": {"$ifNull": ["$title", ""]}},
            "chars": _TITLE_TRIM_CHARS,
        }}}},
        {"$sort": {**sort_spec, "_id": 1}},
        {"$facet": {
            "data": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
            "total": [{"$count": "count"}],
        }},
    ]
    facet = next(db.works.aggregate(pipeline))
    total = facet["total"][0]["count"] if facet["total"] else 0

    works = []
    for doc in facet["data"]:
        oa_url = _safe_url(doc.get("oa_url")) if doc.get("is_oa") else None
        works.append({
            "doi": doc.get("doi"),
            "title": doc.get("title") or "",
            "publication_year": doc.get("publication_year"),
            "type": doc.get("type") or "",
            "journal_title": doc.get("journal_title") or "",
            "contributors": [name for name in (doc.get("contributors") or []) if name],
            "is_oa": bool(doc.get("is_oa")),
            "oa_url": oa_url,
            "oa_is_pdf": bool(oa_url and _is_pdf_link(oa_url)),
        })

    return {
        "data": works,
        "page": page,
        "has_next": page * limit < total,
        "total": total,
    }
