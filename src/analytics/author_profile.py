"""
Author profile queries: one author's details, summary statistics and works.

A publication is stored once per harvested co-author, and ORCID records often
hold the same work several times (imported from different sources). Works are
therefore collapsed to one entry per DOI, or per normalised title + year when
there is no DOI.
"""
import logging
import re
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
SORT_OPTIONS = {
    "newest": {"publication_year": -1, "sort_title": 1},
    "oldest": {"publication_year": 1, "sort_title": 1},
    "title": {"sort_title": 1, "publication_year": -1},
}
TOP_BREAKDOWN = 8
MAX_OBSERVED_NAMES = 8

# Characters ignored at the start/end of a title when sorting by title
_TITLE_TRIM_CHARS = " \"'`“”‘’«»¿¡([{*-"

# One row per unique work: the DOI when present (DOIs are case-insensitive, so
# lower-cased), otherwise lower-cased title + year, falling back to the
# document id when the title is empty. No collation is used, so the author
# match keeps using the orcid_id indexes; $toLower only folds ASCII, so a
# title duplicated with accented capitals is not merged.
_WORK_KEY = {
    "$cond": [
        {"$gt": [{"$strLenCP": {"$ifNull": ["$doi", ""]}}, 0]},
        {"$concat": ["doi:", {"$toLower": "$doi"}]},
        {"$cond": [
            {"$gt": [{"$strLenCP": {"$trim": {"input": {"$ifNull": ["$title", ""]}}}}, 0]},
            {"$concat": [
                "title:", {"$toLower": {"$trim": {"input": "$title"}}},
                "|", {"$toString": {"$ifNull": ["$publication_year", ""]}},
            ]},
            {"$toString": "$_id"},
        ]},
    ]
}

_GROUP_WORKS = {
    "$group": {
        "_id": _WORK_KEY,
        "doi": {"$first": "$doi"},
        "title": {"$first": "$title"},
        "publication_year": {"$max": "$publication_year"},
        "type": {"$first": "$type"},
        "journal_title": {"$max": "$journal_title"},
        "contributors": {"$first": "$contributors.credit_name"},
        "contributor_ids": {"$first": "$contributors.orcid_id"},
        "topics": {"$first": "$topics.display_name"},
        "is_oa": {"$max": {"$eq": ["$is_oa", True]}},
        "oa_url": {"$max": "$oa_url"},
    }
}


def is_valid_orcid(orcid_id: str) -> bool:
    return bool(ORCID_PATTERN.match(orcid_id or ""))


def _author_match(orcid_id: str) -> Dict:
    """Works the author harvested themselves or appears on as a contributor."""
    return {"$or": [{"orcid_id": orcid_id}, {"contributors.orcid_id": orcid_id}]}


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


def get_author_profile(db, orcid_id: str) -> Optional[Dict]:
    """
    Return an author's details and summary statistics, or None if unknown.

    Returns:
        {
            "orcid_id": str, "name": str, "observed_names": [str],
            "institutions": [str], "orcid_works_count": int | None,
            "stats": {"works", "open_access", "coauthors", "first_year", "last_year"},
            "per_year": [{"year", "count"}], "topics": [{"value", "count"}],
            "types": [{"value", "count"}]
        }
    """
    logger.info(f"Building author profile for {orcid_id}")
    author = db.orcids.find_one(
        {"orcid_id": orcid_id},
        # emails are deliberately never read or returned
        {"_id": 0, "given_names": 1, "family_names": 1, "credit_name": 1,
         "other_names": 1, "institution_names": 1, "works_count": 1},
    )

    breakdown = lambda field: [
        {"$unwind": f"${field}"},
        {"$match": {field: {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": TOP_BREAKDOWN},
    ]
    pipeline = [
        {"$match": _author_match(orcid_id)},
        _GROUP_WORKS,
        # a topic listed twice on one work counts once
        {"$addFields": {"topics": {"$setUnion": [{"$ifNull": ["$topics", []]}]}}},
        {"$facet": {
            "totals": [{"$group": {
                "_id": None,
                "works": {"$sum": 1},
                "open_access": {"$sum": {"$cond": ["$is_oa", 1, 0]}},
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
            "coauthors": [
                {"$unwind": "$contributor_ids"},
                {"$match": {"contributor_ids": {"$nin": [None, orcid_id]}}},
                {"$group": {"_id": "$contributor_ids"}},
                {"$count": "count"},
            ],
        }},
    ]
    facets = next(db.works.aggregate(pipeline))
    totals = facets["totals"][0] if facets["totals"] else None

    if author is None and totals is None:
        return None

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

    totals = totals or {"works": 0, "open_access": 0, "first_year": None, "last_year": None}
    return {
        "orcid_id": orcid_id,
        "name": name,
        "observed_names": observed_names,
        "institutions": sorted(set(author.get("institution_names") or []), key=str.lower),
        "orcid_works_count": author.get("works_count"),
        "stats": {
            "works": totals["works"],
            "open_access": totals["open_access"],
            "coauthors": facets["coauthors"][0]["count"] if facets["coauthors"] else 0,
            "first_year": totals["first_year"],
            "last_year": totals["last_year"],
        },
        "per_year": [{"year": d["_id"], "count": d["count"]} for d in facets["per_year"]],
        "topics": [{"value": d["_id"], "count": d["count"]} for d in facets["topics"]],
        "types": [{"value": d["_id"], "count": d["count"]} for d in facets["types"]],
    }


def get_author_works(
    db,
    orcid_id: str,
    page: int = 1,
    limit: int = 20,
    sort: str = "newest",
    open_access_only: bool = False
) -> Dict:
    """
    Return one page of an author's unique works.

    Each work has: doi, title, publication_year, type, journal_title,
    contributors (names), is_oa, oa_url (http/https only) and oa_is_pdf.
    """
    limit = max(1, min(limit, 100))
    page = max(1, page)
    sort_spec = SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])

    pipeline = [{"$match": _author_match(orcid_id)}, _GROUP_WORKS]
    if open_access_only:
        pipeline.append({"$match": {"is_oa": True}})
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
