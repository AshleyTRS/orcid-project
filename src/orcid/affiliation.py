"""
UAEH affiliation: which researchers and works belong to the Universidad
Autónoma del Estado de Hidalgo.

The ORCID search that discovered researchers also matched profiles that
mention the university anywhere (keywords, biographies, works), so the orcids
collection holds people with no affiliation to it. They are kept, but flagged:

    orcids.uaeh_affiliated  True when an institution of the researcher is UAEH
    works.uaeh_work         True when a UAEH researcher owns a record of the
                            work or is a linked contributor on one; the same
                            value is set on every record of a work (work_key)

Every author listing and works statistic filters on these flags
(AFFILIATED_AUTHOR, UAEH_WORK). Other "Hidalgo" institutions (Universidad
Michoacana de San Nicolás de Hidalgo, El Colegio del Estado de Hidalgo, state
government, ...) do not count.
"""
import html
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from pymongo import UpdateOne

logger = logging.getLogger(__name__)

BULK_BATCH_SIZE = 1000

# Filters for queries
AFFILIATED_AUTHOR = {"uaeh_affiliated": True}
UAEH_WORK = {"uaeh_work": True}

# Matched against normalised names (lower case, no accents or punctuation).
# Covers the spellings found in the data, e.g. "Universidad Autónoma del Estado
# de Hidalgo, Instituto de Ciencias de la Salud", "Universida Autonoma del
# Estado de Hidalgo", "Autonomous University of Hidalgo State", "UAEH".
_UAEH = re.compile(
    r"\buniversi\w* autonoma (del )?estado (de )?hidalgo\b"
    r"|\buniversidad autonoma de hidalgo\b"
    r"|\bautonomous university of (the )?(state of )?hidalgo\b"
    r"|\bhidalgo state autonomous university\b"
    r"|\buaeh\b"
)


def normalize_institution(name: Optional[str]) -> str:
    """Lower case, accents and punctuation removed, single spaces."""
    if not name or not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKD", html.unescape(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", text).split())


def is_uaeh_institution(name: Optional[str]) -> bool:
    return bool(_UAEH.search(normalize_institution(name)))


def is_uaeh_affiliated(institution_names: Optional[Iterable[str]]) -> bool:
    return any(is_uaeh_institution(name) for name in institution_names or [])


def flag_affiliated_authors(orcids_collection) -> Dict:
    """
    Set orcids.uaeh_affiliated from each researcher's institution_names.

    Only documents whose flag changes are written.

    Returns:
        {"authors": int, "affiliated": int, "updated": int}
    """
    updates = []
    stats = {"authors": 0, "affiliated": 0, "updated": 0}
    for author in orcids_collection.find({}, {"institution_names": 1, "uaeh_affiliated": 1}):
        stats["authors"] += 1
        affiliated = is_uaeh_affiliated(author.get("institution_names"))
        stats["affiliated"] += affiliated
        if author.get("uaeh_affiliated") != affiliated:
            updates.append(UpdateOne({"_id": author["_id"]}, {"$set": {"uaeh_affiliated": affiliated}}))
    _bulk(orcids_collection, updates)
    stats["updated"] = len(updates)
    logger.info(f"uaeh_affiliated: {stats}")
    return stats


def flag_uaeh_works(works_collection, orcids_collection) -> Dict:
    """
    Set works.uaeh_work: True on every record of a work (work_key) that a UAEH
    researcher owns or is a linked contributor on. Records without a work_key
    are judged on their own.

    Returns:
        {"documents": int, "uaeh_documents": int, "updated": int}
    """
    affiliated = set(orcids_collection.distinct("orcid_id", AFFILIATED_AUTHOR))
    docs = list(works_collection.find({}, {"work_key": 1, "orcid_id": 1, "contributors.orcid_id": 1, "uaeh_work": 1}))

    def has_uaeh_author(doc) -> bool:
        if doc.get("orcid_id") in affiliated:
            return True
        return any(isinstance(c, dict) and c.get("orcid_id") in affiliated for c in doc.get("contributors") or [])

    uaeh_keys = defaultdict(bool)
    for doc in docs:
        if has_uaeh_author(doc):
            uaeh_keys[doc.get("work_key") or doc["_id"]] = True

    updates = []
    uaeh_documents = 0
    for doc in docs:
        value = uaeh_keys[doc.get("work_key") or doc["_id"]]
        uaeh_documents += value
        if doc.get("uaeh_work") != value:
            updates.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"uaeh_work": value}}))
    _bulk(works_collection, updates)
    stats = {"documents": len(docs), "uaeh_documents": uaeh_documents, "updated": len(updates)}
    logger.info(f"uaeh_work: {stats}")
    return stats


def uaeh_institutions_from_activities(activities: Dict) -> List[str]:
    """
    UAEH organisation names (with department) in an ORCID /activities response:
    employments, educations, qualifications, invited positions, distinctions,
    memberships and services.
    """
    names = []
    sections = ("employments", "educations", "qualifications", "invited-positions",
                "distinctions", "memberships", "services")
    for section in sections:
        for group in (activities.get(section) or {}).get("affiliation-group", []):
            for summary in group.get("summaries", []):
                item = next(iter(summary.values()), {}) or {}
                org = ((item.get("organization") or {}).get("name") or "").strip()
                dept = (item.get("department-name") or "").strip()
                full = f"{org}, {dept}" if dept else org
                if is_uaeh_institution(full) and full not in names:
                    names.append(full)
    return names


def _bulk(collection, updates: List[UpdateOne]) -> None:
    for start in range(0, len(updates), BULK_BATCH_SIZE):
        collection.bulk_write(updates[start:start + BULK_BATCH_SIZE], ordered=False)
