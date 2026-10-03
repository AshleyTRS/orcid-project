"""
Work identity: decide which `works` documents describe the same publication.

ORCID records often hold the same publication several times (one entry per
import source, each with its own put_code), and the same publication also
appears on every co-author's record. Every works document therefore gets a
`work_key`; documents sharing a key are one work, and all counts should count
distinct keys rather than documents.

Key rules, in order:
    1. doi:<doi>          the DOI (from `doi` or `external_ids`), normalised
    2. doi:<doi>          a no-DOI record whose title + year match exactly one
                          DOI record of the same author is linked to that DOI
    3. title:<t>|<year>   normalised title + year; titles shorter than
                          GLOBAL_TITLE_MIN_LENGTH are scoped to the record owner
                          ("title:<orcid_id>:<t>|<year>") so generic titles such
                          as "Editorial" are never merged across researchers
    4. put:<orcid_id>:<put_code>   no DOI and no title: the record is its own work
"""
import html
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from pymongo import UpdateOne

logger = logging.getLogger(__name__)

GLOBAL_TITLE_MIN_LENGTH = 40
BULK_BATCH_SIZE = 1000

_DOI_PREFIX = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[\W_]+")


def normalize_doi(value: Optional[str]) -> Optional[str]:
    """Lower-cased DOI without URL/"doi:" prefixes, or None if it is not a DOI."""
    if not value or not isinstance(value, str):
        return None
    doi = _DOI_PREFIX.sub("", value.strip()).strip().lower()
    return doi if doi.startswith("10.") else None


def work_doi(doc: Dict) -> Optional[str]:
    """A document's normalised DOI from `doi`, falling back to `external_ids`."""
    doi = normalize_doi(doc.get("doi"))
    if doi:
        return doi
    for ext in doc.get("external_ids") or []:
        if isinstance(ext, dict) and (ext.get("type") or "").lower() == "doi":
            doi = normalize_doi(ext.get("value"))
            if doi:
                return doi
    return None


def normalize_title(title: Optional[str]) -> str:
    """Title reduced for matching: no markup, accents, case or punctuation."""
    if not title or not isinstance(title, str):
        return ""
    # Tags such as <inf>/<sup> sit inside words (AgSbS<inf>2</inf>), so drop them without a space
    text = html.unescape(_HTML_TAG.sub("", title))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(_NON_WORD.sub(" ", text).split())


def compute_work_key(doc: Dict, linked_doi: Optional[str] = None) -> str:
    """
    The work_key for one document.

    Args:
        doc: works document (needs orcid_id, put_code, title,
            publication_year and doi/external_ids)
        linked_doi: DOI found for this document's title + year among the same
            author's records (rule 2), if any
    """
    doi = work_doi(doc) or linked_doi
    if doi:
        return f"doi:{doi}"

    title = normalize_title(doc.get("title"))
    year = doc.get("publication_year")
    year_part = "" if year is None else str(year)
    if title:
        if len(title) >= GLOBAL_TITLE_MIN_LENGTH:
            return f"title:{title}|{year_part}"
        return f"title:{doc.get('orcid_id')}:{title}|{year_part}"

    return f"put:{doc.get('orcid_id')}:{doc.get('put_code')}"


def assign_work_keys(docs: Iterable[Dict]) -> Dict:
    """
    Compute work_keys for documents, linking no-DOI duplicates to DOI records.

    Linking only happens within one author's own records and only when the
    title + year maps to exactly one DOI, so ambiguous cases stay separate.

    Returns:
        {document _id: work_key}
    """
    by_owner = defaultdict(list)
    for doc in docs:
        by_owner[doc.get("orcid_id")].append(doc)

    keys = {}
    for owner_docs in by_owner.values():
        dois_by_title = defaultdict(set)
        for doc in owner_docs:
            doi = work_doi(doc)
            title = normalize_title(doc.get("title"))
            if doi and title:
                dois_by_title[(title, doc.get("publication_year"))].add(doi)

        for doc in owner_docs:
            linked = None
            if not work_doi(doc):
                candidates = dois_by_title.get((normalize_title(doc.get("title")), doc.get("publication_year")))
                if candidates and len(candidates) == 1:
                    linked = next(iter(candidates))
            keys[doc["_id"]] = compute_work_key(doc, linked)
    return keys


_KEY_FIELDS = {"orcid_id": 1, "put_code": 1, "title": 1, "publication_year": 1,
               "doi": 1, "external_ids": 1, "work_key": 1}


def apply_work_keys(works_collection, orcid_ids: Optional[List[str]] = None) -> Dict:
    """
    Store work_key on works documents (all, or only the given authors' records).

    Only documents whose key changes are written, so re-running is cheap.

    Returns:
        {"documents": int, "updated": int}
    """
    query = {"orcid_id": {"$in": orcid_ids}} if orcid_ids else {}
    docs = list(works_collection.find(query, _KEY_FIELDS))
    keys = assign_work_keys(docs)

    updates = [
        UpdateOne({"_id": doc["_id"]}, {"$set": {"work_key": keys[doc["_id"]]}})
        for doc in docs
        if doc.get("work_key") != keys[doc["_id"]]
    ]
    for start in range(0, len(updates), BULK_BATCH_SIZE):
        works_collection.bulk_write(updates[start:start + BULK_BATCH_SIZE], ordered=False)

    logger.info(f"work_key: {len(docs)} documents checked, {len(updates)} updated")
    return {"documents": len(docs), "updated": len(updates)}


def update_unique_works_counts(works_collection, orcids_collection,
                               orcid_ids: Optional[List[str]] = None) -> Dict:
    """
    Set orcids.unique_works_count: distinct works per author.

    An author's works are the records on their own ORCID plus records on
    co-authors' ORCIDs that list them as a contributor (the same definition the
    author profile page uses), counted once per work_key. works_count keeps
    the raw number of ORCID records.

    Returns:
        {"authors": int, "updated": int}
    """
    match = {"work_key": {"$ne": None}}
    if orcid_ids:
        match["$or"] = [{"orcid_id": {"$in": orcid_ids}}, {"contributors.orcid_id": {"$in": orcid_ids}}]

    pipeline = [
        {"$match": match},
        {"$project": {
            "work_key": 1,
            "authors": {"$setUnion": [["$orcid_id"], {"$ifNull": ["$contributors.orcid_id", []]}]},
        }},
        {"$unwind": "$authors"},
        {"$match": {"authors": {"$ne": None, **({"$in": orcid_ids} if orcid_ids else {})}}},
        {"$group": {"_id": {"author": "$authors", "key": "$work_key"}}},
        {"$group": {"_id": "$_id.author", "count": {"$sum": 1}}},
    ]
    counts = {row["_id"]: row["count"] for row in works_collection.aggregate(pipeline, allowDiskUse=True)}

    author_query = {"orcid_id": {"$in": orcid_ids}} if orcid_ids else {"orcid_id": {"$ne": None}}
    updates = []
    authors = 0
    for author in orcids_collection.find(author_query, {"orcid_id": 1, "unique_works_count": 1}):
        authors += 1
        count = counts.get(author["orcid_id"], 0)
        if author.get("unique_works_count") != count:
            updates.append(UpdateOne({"_id": author["_id"]}, {"$set": {"unique_works_count": count}}))
    for start in range(0, len(updates), BULK_BATCH_SIZE):
        orcids_collection.bulk_write(updates[start:start + BULK_BATCH_SIZE], ordered=False)

    logger.info(f"unique_works_count: {authors} authors checked, {len(updates)} updated")
    return {"authors": authors, "updated": len(updates)}


def unique_works_stages(per_author: bool = False, fields: Optional[Dict] = None) -> List[Dict]:
    """
    Aggregation stages that keep one document per work (or per author + work).

    Insert after a $match. With per_author=True duplicates are collapsed per
    (orcid_id, work_key), for counts attributed to the record owner.

    Args:
        fields: optional projection applied first to keep the grouped documents small
    """
    group_id = {"author": "$orcid_id", "key": "$work_key"} if per_author else "$work_key"
    stages = [{"$project": fields}] if fields else []
    return stages + [
        {"$group": {"_id": group_id, "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
    ]
