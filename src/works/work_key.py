"""
Work identity: decide which `works` documents describe the same publication.

ORCID records often hold the same publication several times (one entry per
import source, each with its own put_code), and the same publication also
appears on every co-author's record. Every works document therefore gets a
`work_key`; documents sharing a key are one work, and all counts should count
distinct keys rather than documents.

Documents are clustered across the whole collection; two documents are the
same work when any of these links them (links are transitive):
    1. they share a self identifier of a STRONG_ID_TYPES type (DOI, Scopus EID,
       WoS UID, PMID, ...). Identifiers with relationship "part-of" (the ISSN
       of the journal, the ISBN or DOI of the book a chapter is in) never link,
       and neither do the DOIs of a record listing more than
       MAX_DOIS_PER_RECORD of them (an author pasting all their DOIs into one entry)
    2. ORCID grouped them (same `orcid_group`) and their titles are similar
       (GROUP_TITLE_MIN_SIMILARITY). ORCID groups on any self identifier, and
       authors often mark the journal ISSN, the book ISBN or a placeholder URL
       as self, so a group alone would merge different articles and chapters
    3. same normalised title and compatible years (equal, within
       YEAR_TOLERANCE, or one unknown). Titles shorter than
       GLOBAL_TITLE_MIN_LENGTH only match within one owner's record, so
       generic titles such as "Editorial" are never merged across researchers
    4. titles of one owner that differ only by typos (a few character edits)
       with identical numbers and Roman numerals ("vol ii" vs "vol iii",
       "siglo xix" vs "siglo xx" are different works) and compatible years
Title links (3, 4) never join two works that both have a DOI: different DOIs
with one title are mostly a preprint and its article, translations published
separately, or errata. A no-DOI record whose title matches several DOI works is
ambiguous and stays on its own.

The work_key names its cluster: "doi:<smallest DOI>", else the smallest
"title:..." key of its documents, else "put:<orcid_id>:<put_code>".
"""
import difflib
import html
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from pymongo import UpdateOne

logger = logging.getLogger(__name__)

GLOBAL_TITLE_MIN_LENGTH = 40
YEAR_TOLERANCE = 1
MAX_DOIS_PER_RECORD = 2
GROUP_TITLE_MIN_SIMILARITY = 0.8
BULK_BATCH_SIZE = 1000

# Identifier types that name one specific work (ISSN/ISBN name a journal or book)
STRONG_ID_TYPES = frozenset({
    "doi", "eid", "wosuid", "pmid", "pmc", "arxiv", "handle", "urn", "dnb", "lensid", "bibcode",
})
# Typo matching: titles (spaces removed) of at least TYPO_MIN_LENGTH characters
# may differ by max(TYPO_MIN_EDITS, length // TYPO_CHARS_PER_EDIT) edits
TYPO_MIN_LENGTH = 20
TYPO_MIN_EDITS = 2
TYPO_CHARS_PER_EDIT = 30

_DOI_PREFIX = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[\W_]+")
_DIGITS = re.compile(r"\d+")
_ROMAN = re.compile(r"^[ivxlcdm]+$")


def normalize_doi(value: Optional[str]) -> Optional[str]:
    """Lower-cased DOI without URL/"doi:" prefixes, or None if it is not a DOI."""
    if not value or not isinstance(value, str):
        return None
    doi = _DOI_PREFIX.sub("", value.strip()).strip().lower()
    return doi if doi.startswith("10.") else None


def orcid_group_id(orcid_id: str, put_codes: Iterable[int]) -> str:
    """Name of one ORCID work group: the owner plus the group's smallest put_code."""
    return f"{orcid_id}:{min(put_codes)}"


def _is_self(ext: Dict) -> bool:
    """Identifier of the work itself. Records harvested before relationships were stored count as self."""
    return ext.get("relationship") in (None, "self")


def self_ids(doc: Dict) -> Set[Tuple[str, str]]:
    """The document's normalised (type, value) self identifiers of STRONG_ID_TYPES."""
    ids = set()
    for ext in doc.get("external_ids") or []:
        if not isinstance(ext, dict) or not _is_self(ext):
            continue
        id_type = (ext.get("type") or "").lower()
        value = (ext.get("value") or "").strip().lower() if isinstance(ext.get("value"), str) else ""
        if id_type not in STRONG_ID_TYPES or not value:
            continue
        if id_type == "doi":
            value = normalize_doi(value)
            if not value:
                continue
        ids.add((id_type, value))
    if not any(id_type == "doi" for id_type, _ in ids) and not doc.get("external_ids"):
        doi = normalize_doi(doc.get("doi"))
        if doi:
            ids.add(("doi", doi))
    return ids


def work_doi(doc: Dict) -> Optional[str]:
    """
    A document's normalised self DOI from `external_ids` (the smallest if it
    has several), falling back to `doi` for documents without external_ids.
    """
    dois = sorted(value for id_type, value in self_ids(doc) if id_type == "doi")
    return dois[0] if dois else None


def normalize_title(title: Optional[str]) -> str:
    """Title reduced for matching: no markup, accents, case or punctuation."""
    if not title or not isinstance(title, str):
        return ""
    # Tags such as <inf>/<sup> sit inside words (AgSbS<inf>2</inf>), so drop them without a space
    text = html.unescape(_HTML_TAG.sub("", title))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(_NON_WORD.sub(" ", text).split())


def _title_key(doc: Dict) -> Optional[str]:
    title = normalize_title(doc.get("title"))
    if not title:
        return None
    year = doc.get("publication_year")
    year_part = "" if year is None else str(year)
    if len(title) >= GLOBAL_TITLE_MIN_LENGTH:
        return f"title:{title}|{year_part}"
    return f"title:{doc.get('orcid_id')}:{title}|{year_part}"


def _put_key(doc: Dict) -> str:
    return f"put:{doc.get('orcid_id')}:{doc.get('put_code')}"


def compute_work_key(doc: Dict, linked_doi: Optional[str] = None) -> str:
    """
    Provisional work_key for one document on its own (used at harvest time,
    before assign_work_keys clusters it with the rest of the collection).

    Args:
        doc: works document (needs orcid_id, put_code, title,
            publication_year and doi/external_ids)
        linked_doi: DOI of the work this document was matched to, if any
    """
    doi = work_doi(doc) or linked_doi
    if doi:
        return f"doi:{doi}"
    return _title_key(doc) or _put_key(doc)


def _levenshtein_within(a: str, b: str, limit: int) -> bool:
    """True when the edit distance between a and b is at most limit."""
    if abs(len(a) - len(b)) > limit:
        return False
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit


def _linking_ids(doc: Dict) -> Set[Tuple[str, str]]:
    """Self identifiers used for linking: a record's DOIs are dropped when it lists too many."""
    ids = self_ids(doc)
    if sum(1 for id_type, _ in ids if id_type == "doi") > MAX_DOIS_PER_RECORD:
        ids = {(id_type, value) for id_type, value in ids if id_type != "doi"}
    return ids


class _Clusters:
    """Union-find over document indexes that tracks each cluster's DOIs and years."""

    def __init__(self, docs: List[Dict]):
        self.parent = list(range(len(docs)))
        self.dois = [{v for t, v in _linking_ids(d) if t == "doi"} for d in docs]
        self.years = [{d["publication_year"]} if d.get("publication_year") is not None else set() for d in docs]

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a == b:
            return
        if b < a:
            a, b = b, a
        self.parent[b] = a
        self.dois[a] |= self.dois[b]
        self.years[a] |= self.years[b]

    def years_compatible(self, a: int, b: int) -> bool:
        years_a, years_b = self.years[self.find(a)], self.years[self.find(b)]
        if not years_a or not years_b:
            return True
        return min(abs(x - y) for x in years_a for y in years_b) <= YEAR_TOLERANCE

    def title_link_allowed(self, a: int, b: int) -> bool:
        """A title may join two clusters unless both carry DOIs (they are then different works)."""
        a, b = self.find(a), self.find(b)
        return a != b and not (self.dois[a] and self.dois[b]) and self.years_compatible(a, b)


def _link_identifiers(docs: List[Dict], clusters: _Clusters) -> None:
    first_seen = {}
    for i, doc in enumerate(docs):
        for ident in _linking_ids(doc):
            if ident in first_seen:
                clusters.union(i, first_seen[ident])
            else:
                first_seen[ident] = i


def _link_orcid_groups(docs: List[Dict], titles: List[str], clusters: _Clusters) -> None:
    """
    Join entries ORCID grouped together when their titles also agree. With an
    identical title the shared identifier is enough and years may differ
    (e.g. a book entered with its first and its reprint year).
    """
    groups = defaultdict(list)
    for i, doc in enumerate(docs):
        if doc.get("orcid_group") and titles[i]:
            groups[doc["orcid_group"]].append(i)
    for members in groups.values():
        for x, a in enumerate(members):
            for b in members[x + 1:]:
                root_a, root_b = clusters.find(a), clusters.find(b)
                if root_a == root_b or (clusters.dois[root_a] and clusters.dois[root_b]):
                    continue
                if titles[a] == titles[b] or (
                        clusters.years_compatible(a, b)
                        and difflib.SequenceMatcher(None, titles[a], titles[b]).ratio() >= GROUP_TITLE_MIN_SIMILARITY):
                    clusters.union(a, b)


def _link_bucket(members: List[int], clusters: _Clusters) -> None:
    """Join the clusters of documents that share one normalised title."""
    roots = sorted({clusters.find(i) for i in members})
    if len(roots) < 2:
        return
    with_doi = [r for r in roots if clusters.dois[r]]
    without_doi = [r for r in roots if not clusters.dois[r]]

    # A no-DOI record joins the single DOI work it fits; with several it is ambiguous
    unmatched = []
    for root in without_doi:
        candidates = [d for d in with_doi if clusters.years_compatible(root, d)]
        if len(candidates) == 1:
            clusters.union(root, candidates[0])
        elif not candidates:
            unmatched.append(root)

    # Remaining no-DOI records: one work per run of close years
    first_year = lambda r: min(clusters.years[clusters.find(r)])
    dated = sorted((r for r in unmatched if clusters.years[r]), key=first_year)
    anchors = []
    for root in dated:
        if anchors and first_year(root) - first_year(anchors[-1]) <= YEAR_TOLERANCE:
            clusters.union(root, anchors[-1])
        else:
            anchors.append(root)
    undated = [r for r in unmatched if not clusters.years[r]]
    if len(anchors) <= 1:
        target = anchors[0] if anchors else (undated[0] if undated else None)
        for root in undated:
            clusters.union(root, target)


def _link_titles(docs: List[Dict], titles: List[str], clusters: _Clusters) -> None:
    buckets = defaultdict(list)
    for i, title in enumerate(titles):
        if title:
            scope = None if len(title) >= GLOBAL_TITLE_MIN_LENGTH else docs[i].get("orcid_id")
            buckets[(scope, title)].append(i)
    for key in sorted(buckets, key=lambda k: (k[0] or "", k[1])):
        _link_bucket(buckets[key], clusters)


def _link_typos(docs: List[Dict], titles: List[str], clusters: _Clusters) -> None:
    """Join one owner's works whose titles differ only by a few character edits."""
    groups = defaultdict(dict)
    for i, title in enumerate(titles):
        compact = title.replace(" ", "")
        if len(compact) < TYPO_MIN_LENGTH:
            continue
        # Numbers and Roman numerals tell volumes, editions and centuries apart
        signature = (tuple(_DIGITS.findall(title)), tuple(t for t in title.split() if _ROMAN.match(t)))
        groups[(docs[i].get("orcid_id"), signature)].setdefault(compact, i)

    for titles_in_group in groups.values():
        entries = sorted(titles_in_group.items(), key=lambda item: (len(item[0]), item[0]))
        for x, (compact_a, a) in enumerate(entries):
            for compact_b, b in entries[x + 1:]:
                limit = max(TYPO_MIN_EDITS, len(compact_a) // TYPO_CHARS_PER_EDIT)
                if len(compact_b) - len(compact_a) > limit:
                    break
                if clusters.title_link_allowed(a, b) and _levenshtein_within(compact_a, compact_b, limit):
                    clusters.union(a, b)


def assign_work_keys(docs: Iterable[Dict]) -> Dict:
    """
    Cluster documents into works and name each cluster (see module docstring).

    Pass the whole collection: clusters span authors, so keys computed from a
    subset can differ from the collection-wide ones.

    Returns:
        {document _id: work_key}
    """
    docs = sorted(docs, key=lambda d: (str(d.get("orcid_id")), d.get("put_code") or 0, str(d["_id"])))
    titles = [normalize_title(d.get("title")) for d in docs]
    clusters = _Clusters(docs)

    _link_identifiers(docs, clusters)
    _link_orcid_groups(docs, titles, clusters)
    _link_titles(docs, titles, clusters)
    _link_typos(docs, titles, clusters)

    members = defaultdict(list)
    for i in range(len(docs)):
        members[clusters.find(i)].append(i)

    keys = {}
    used = set()
    for root in sorted(members):
        dois = clusters.dois[root]
        if dois:
            key = f"doi:{min(dois)}"
        else:
            title_keys = [k for k in (_title_key(docs[i]) for i in members[root]) if k]
            key = min(title_keys) if title_keys else _put_key(docs[root])
        if key in used:
            # Same title + year as another work that must stay separate (e.g. ambiguous)
            key = f"{key}#{_put_key(docs[root])}"
        used.add(key)
        for i in members[root]:
            keys[docs[i]["_id"]] = key
    return keys


_KEY_FIELDS = {"orcid_id": 1, "put_code": 1, "title": 1, "publication_year": 1,
               "doi": 1, "external_ids": 1, "orcid_group": 1, "work_key": 1}


def apply_work_keys(works_collection) -> Dict:
    """
    Recompute work_key for the whole collection and store the ones that changed.

    Re-run after harvesting or changing works: a new record can join works
    held by other authors.

    Returns:
        {"documents": int, "updated": int}
    """
    docs = list(works_collection.find({}, _KEY_FIELDS))
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
