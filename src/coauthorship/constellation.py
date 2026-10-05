"""
Constellation details: one connected group of the co-authorship network.

The network page draws researchers as nodes and shared works as edges; a
constellation is everything reachable from one researcher through shared works
under the same filters (years, types, subjects, keywords, institutes). This
module rebuilds that group and describes it: its members, every pair that
worked together, the works they share and the topics, types and years of those works.

Works are identified by work_key (see src/works/work_key.py), the same way the
network counts them, so the numbers match the graph.

With broad filters most researchers can fall into one very large group, so the
lists are capped (MAX_WORKS, MAX_PAIRS) while totals, years, topics and types
always describe the whole group. Everything involving the clicked researcher is
always included, so the page can also show their direct collaborations in full.
"""
import logging
from collections import Counter, defaultdict, deque
from typing import Dict, List, Optional, Set

from src.analytics.aggregations import build_works_match
from src.analytics.author_profile import _is_pdf_link, _safe_url

logger = logging.getLogger(__name__)

MAX_WORKS = 200        # shared works returned besides the focus researcher's (newest first)
MAX_PAIRS = 300        # collaborating pairs returned besides the focus researcher's (strongest first)
MAX_MEMBERS = 300      # most active members returned besides those the listed pairs and works mention
MAX_INSTITUTIONS = 3   # institutions listed per member
TOP_VALUES = 10        # topics / types listed for the whole constellation
PAIR_TOPICS = 3        # topics listed per pair


def _author_sets(db, match: Dict):
    """
    Returns:
        (authors, years): work_key -> ORCID iDs on that work (record owner and
        linked contributors), and work_key -> publication year
    """
    authors = defaultdict(set)
    years = {}
    cursor = db.works.aggregate([
        {"$match": match},
        {"$project": {"_id": 0, "work_key": 1, "orcid_id": 1, "publication_year": 1, "contributors.orcid_id": 1}},
    ])
    for doc in cursor:
        key = doc.get("work_key")
        if not key:
            continue
        if doc.get("publication_year") and not years.get(key):
            years[key] = doc["publication_year"]
        if doc.get("orcid_id"):
            authors[key].add(doc["orcid_id"])
        for contributor in doc.get("contributors") or []:
            if isinstance(contributor, dict) and contributor.get("orcid_id"):
                authors[key].add(contributor["orcid_id"])
    return authors, years


def _component(start: str, authors_by_work: Dict[str, Set[str]]) -> Set[str]:
    """Everyone connected to start through works with two or more ORCID authors."""
    neighbors = defaultdict(set)
    for authors in authors_by_work.values():
        if len(authors) > 1:
            for author in authors:
                neighbors[author] |= authors
    seen = {start}
    queue = deque([start])
    while queue:
        for other in neighbors[queue.popleft()]:
            if other not in seen:
                seen.add(other)
                queue.append(other)
    return seen


def _work_details(db, keys: List[str]) -> Dict[str, Dict]:
    """One merged record per work_key with the metadata shown on the page."""
    details = {}
    cursor = db.works.aggregate([
        {"$match": {"work_key": {"$in": keys}}},
        {"$group": {
            "_id": "$work_key",
            # $max prefers a copy that has the value over one that lacks it
            "doi": {"$max": "$doi"},
            "title": {"$first": "$title"},
            "publication_year": {"$max": "$publication_year"},
            "type": {"$first": "$type"},
            "journal_title": {"$max": "$journal_title"},
            "contributors": {"$first": "$contributors"},
            "credits": {"$push": "$contributors"},
            "topics": {"$first": "$topics.display_name"},
            "is_oa": {"$max": {"$eq": ["$is_oa", True]}},
            "oa_url": {"$max": "$oa_url"},
        }},
    ], allowDiskUse=True)
    for doc in cursor:
        details[doc["_id"]] = doc
    return details


def _topic_and_type_counts(db, keys: List[str]) -> Dict[str, List[Dict]]:
    """Topics and types over every given work, each work counted once."""
    if not keys:
        return {"topics": [], "types": []}
    result = next(db.works.aggregate([
        {"$match": {"work_key": {"$in": keys}}},
        {"$group": {"_id": "$work_key", "topics": {"$first": "$topics.display_name"}, "type": {"$first": "$type"}}},
        {"$addFields": {"topics": {"$setUnion": [{"$ifNull": ["$topics", []]}]}}},
        {"$facet": {
            "topics": [{"$unwind": "$topics"}, {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
                       {"$sort": {"count": -1, "_id": 1}}, {"$limit": TOP_VALUES}],
            "types": [{"$match": {"type": {"$nin": [None, ""]}}}, {"$group": {"_id": "$type", "count": {"$sum": 1}}},
                      {"$sort": {"count": -1, "_id": 1}}, {"$limit": TOP_VALUES}],
        }},
    ], allowDiskUse=True))
    return {name: [{"value": d["_id"], "count": d["count"]} for d in result[name]] for name in ("topics", "types")}


def _member_names(db, members: Set[str], works: Dict[str, Dict]) -> Dict[str, Dict]:
    """Name, institutions and dataset membership per ORCID iD."""
    info = {}
    for author in db.orcids.find(
        {"orcid_id": {"$in": list(members)}},
        # emails are deliberately never read
        {"_id": 0, "orcid_id": 1, "given_names": 1, "family_names": 1, "credit_name": 1,
         "institution_names": 1, "uaeh_affiliated": 1},
    ):
        name = " ".join(f"{author.get('given_names') or ''} {author.get('family_names') or ''}".split())
        info[author["orcid_id"]] = {
            "name": name or (author.get("credit_name") or "").strip() or None,
            "institutions": sorted(set(author.get("institution_names") or []), key=str.lower)[:MAX_INSTITUTIONS],
            # Only UAEH researchers have an author page
            "in_dataset": bool(author.get("uaeh_affiliated")),
        }

    # Researchers outside the harvested set: use the name they are credited under most often
    credited = defaultdict(Counter)
    for work in works.values():
        for copy in work.get("credits") or []:
            for contributor in copy or []:
                orcid = contributor.get("orcid_id")
                if orcid in members and contributor.get("credit_name"):
                    credited[orcid][" ".join(contributor["credit_name"].split())] += 1
    for orcid in members:
        entry = info.setdefault(orcid, {"name": None, "institutions": [], "in_dataset": False})
        if not entry["name"] and credited[orcid]:
            entry["name"] = credited[orcid].most_common(1)[0][0]
    return info


def get_constellation(
    db,
    orcid_id: str,
    start_year: int,
    end_year: int,
    types: Optional[List[str]] = None,
    subjects: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    institutes: Optional[List[str]] = None,
) -> Optional[Dict]:
    """
    Describe the constellation that contains orcid_id under the given network filters.

    Returns None when the researcher has no works matching the filters.

    Returns:
        {
            "focus": str,
            "stats": {"members", "links", "shared_works", "collaborations",
                      "first_year", "last_year"},
            "members": [{"orcid_id", "name", "institutions", "in_dataset",
                         "works", "shared_works", "collaborators"}],   focus first, then most active
            "pairs": [{"source", "target", "weight", "first_year", "last_year",
                       "works": [work_key], "topics": [str]}],         strongest first
            "works": [{"key", "title", "publication_year", "type", "journal_title",
                       "doi", "topics", "members": [orcid], "contributors": [name],
                       "is_oa", "oa_url", "oa_is_pdf"}],              newest first
            "works_total": int, "pairs_total": int,
            "per_year": [{"year", "count"}], "topics": [{"value", "count"}],
            "types": [{"value", "count"}]
        }
        works and pairs hold every entry involving the focus researcher plus
        the newest works / strongest pairs of the rest, up to MAX_WORKS /
        MAX_PAIRS; members holds everyone those mention plus the MAX_MEMBERS
        most active. stats, per_year, topics and types cover the whole group.
        For a researcher with no co-authors in the network, works lists their
        own works so the page still shows what they published.
    """
    match = build_works_match(start_year=start_year, end_year=end_year, types=types,
                              subjects=subjects, keywords=keywords, institutes=institutes)
    authors_by_work, year_by_work = _author_sets(db, match)
    if not any(orcid_id in authors for authors in authors_by_work.values()):
        return None

    members = _component(orcid_id, authors_by_work)
    member_works = {key: authors & members for key, authors in authors_by_work.items() if authors & members}
    shared = {key: authors for key, authors in member_works.items() if len(authors) > 1}

    pair_works = defaultdict(list)
    for key, authors in shared.items():
        ordered = sorted(authors)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pair_works[(a, b)].append(key)

    # Works described on the page: the shared ones, or a solo researcher's own works.
    # The focus researcher's are always listed; the rest are the newest up to MAX_WORKS.
    scope = shared if shared else member_works
    year = lambda key: year_by_work.get(key)
    newest = sorted(scope, key=lambda k: (-(year(k) or 0), k))
    focus_keys = [k for k in newest if orcid_id in scope[k]]
    others = [k for k in newest if orcid_id not in scope[k]][:MAX_WORKS]
    listed = {k: scope[k] for k in focus_keys + others}
    details = _work_details(db, list(listed))
    totals = _topic_and_type_counts(db, list(scope))

    works = []
    for key, authors in listed.items():
        d = details.get(key, {})
        oa_url = _safe_url(d.get("oa_url")) if d.get("is_oa") else None
        works.append({
            "key": key,
            "title": d.get("title") or "",
            "publication_year": d.get("publication_year"),
            "type": d.get("type") or "",
            "journal_title": d.get("journal_title") or "",
            "doi": d.get("doi"),
            "topics": list(dict.fromkeys(d.get("topics") or [])),
            "members": sorted(authors),
            "contributors": [c.get("credit_name") for c in d.get("contributors") or [] if c.get("credit_name")],
            "is_oa": bool(d.get("is_oa")),
            "oa_url": oa_url,
            "oa_is_pdf": bool(oa_url and _is_pdf_link(oa_url)),
        })
    works.sort(key=lambda w: (-(w["publication_year"] or 0), w["title"].lower()))
    works_by_key = {w["key"]: w for w in works}

    pairs = []
    for (a, b), keys in pair_works.items():
        years = [y for y in (year(k) for k in keys) if y]
        # Topics from the listed works (all of them for pairs with the focus researcher)
        topics = Counter(t for k in keys if k in works_by_key for t in works_by_key[k]["topics"])
        pairs.append({
            "source": a, "target": b, "weight": len(keys),
            "first_year": min(years) if years else None,
            "last_year": max(years) if years else None,
            "works": sorted(keys, key=lambda k: -(year(k) or 0)),
            "topics": [t for t, _ in topics.most_common(PAIR_TOPICS)],
        })
    pairs.sort(key=lambda p: (-p["weight"], p["source"], p["target"]))
    involves_focus = lambda p: orcid_id in (p["source"], p["target"])
    pairs_listed = [p for p in pairs if involves_focus(p)] + [p for p in pairs if not involves_focus(p)][:MAX_PAIRS]

    collaborators = defaultdict(set)
    for a, b in pair_works:
        collaborators[a].add(b)
        collaborators[b].add(a)
    works_count = Counter(a for authors in member_works.values() for a in authors)
    shared_count = Counter(a for authors in shared.values() for a in authors)

    # Members the listed pairs and works mention, plus the most active others
    activity = lambda m: (m != orcid_id, -shared_count[m], -works_count[m], m)
    listed_members = {orcid_id} | collaborators[orcid_id]
    listed_members |= {m for p in pairs_listed for m in (p["source"], p["target"])}
    listed_members |= {m for w in works for m in w["members"]}
    listed_members |= set(sorted(members, key=activity)[:MAX_MEMBERS])
    info = _member_names(db, listed_members, details)
    member_list = [{
        "orcid_id": orcid,
        "name": info[orcid]["name"],
        "institutions": info[orcid]["institutions"],
        "in_dataset": info[orcid]["in_dataset"],
        "works": works_count[orcid],
        "shared_works": shared_count[orcid],
        "collaborators": len(collaborators[orcid]),
    } for orcid in sorted(listed_members, key=activity)]

    years = [y for y in (year(k) for k in scope) if y]
    logger.info(f"Constellation of {orcid_id}: {len(members)} members, {len(pairs)} pairs, {len(works)} works")
    return {
        "focus": orcid_id,
        "stats": {
            "members": len(members),
            "links": len(pairs),
            "shared_works": len(shared),
            "collaborations": sum(p["weight"] for p in pairs),
            "first_year": min(years) if years else None,
            "last_year": max(years) if years else None,
        },
        "members": member_list,
        "pairs": pairs_listed,
        "pairs_total": len(pairs),
        "works": works,
        "works_total": len(scope),
        "per_year": [{"year": y, "count": c} for y, c in sorted(Counter(years).items())],
        "topics": totals["topics"],
        "types": totals["types"],
    }
