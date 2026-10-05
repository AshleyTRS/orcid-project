"""
Migration: store ORCID's grouping and identifier relationships on works.

ORCID groups an author's entries for the same work (entries that share a self
identifier) and marks each external identifier as "self" (it identifies the
work) or "part-of" (the ISSN of the journal, the ISBN or DOI of the book a
chapter is in). Works harvested before these were stored lack both; this
migration fetches each author's work summaries (one ORCID request per author)
and sets:
    works.orcid_group                    see src.works.work_key.orcid_group_id
    works.external_ids[].relationship

Needs the ORCID Public API. Run before add_work_key, which reads both.
Safe to re-run: only documents whose values change are written. Records that
are no longer on the author's ORCID record are counted, not deleted.
"""
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from pymongo import UpdateOne

# Add project root to path so src module can be imported when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.works.work_key import orcid_group_id

logger = logging.getLogger(__name__)

BULK_BATCH_SIZE = 1000


def _id_key(id_type: Optional[str], value: Optional[str]) -> Tuple[str, str]:
    return ((id_type or "").lower(), (value or "").strip().lower())


def parse_work_groups(orcid_id: str, works_json: Dict) -> Dict[int, Dict]:
    """
    Map each put_code of an ORCID /works response to its group and identifier relationships.

    Returns:
        {put_code: {"orcid_group": str, "relationships": {(type, value): relationship}}}
    """
    summaries = {}
    for group in works_json.get("group") or []:
        works = [w for w in group.get("work-summary") or [] if "put-code" in w]
        if not works:
            continue
        group_id = orcid_group_id(orcid_id, [w["put-code"] for w in works])
        for work in works:
            ids = (work.get("external-ids") or {}).get("external-id") or []
            summaries[work["put-code"]] = {
                "orcid_group": group_id,
                "relationships": {
                    _id_key(e.get("external-id-type"), e.get("external-id-value")): e.get("external-id-relationship")
                    for e in ids
                },
            }
    return summaries


def _work_update(doc: Dict, summary: Dict) -> Optional[Dict]:
    """$set for one works document, or None when it already matches ORCID."""
    changes = {}
    if doc.get("orcid_group") != summary["orcid_group"]:
        changes["orcid_group"] = summary["orcid_group"]

    external_ids = []
    ids_changed = False
    for ext in doc.get("external_ids") or []:
        relationship = summary["relationships"].get(_id_key(ext.get("type"), ext.get("value")))
        if relationship and ext.get("relationship") != relationship:
            ext = {**ext, "relationship": relationship}
            ids_changed = True
        external_ids.append(ext)
    if ids_changed:
        changes["external_ids"] = external_ids
    return changes or None


def add_orcid_groups(works_collection, fetch_works: Callable[[str], Dict],
                     orcid_ids: Optional[Iterable[str]] = None) -> Dict:
    """
    Backfill orcid_group and identifier relationships from ORCID.

    Args:
        works_collection: MongoDB works collection
        fetch_works: returns the ORCID /works JSON for an ORCID iD
            (OrcidSearchClient.get_works)
        orcid_ids: authors to process; defaults to every record owner in works

    Returns:
        Status dict with author, document, update and error counts
    """
    authors = sorted(orcid_ids) if orcid_ids is not None else sorted(works_collection.distinct("orcid_id"))
    logger.info(f"Fetching ORCID work groups for {len(authors)} authors...")

    updates: List[UpdateOne] = []
    stats = {"authors": len(authors), "documents": 0, "updated": 0, "not_on_orcid": 0, "failed_authors": []}

    def flush():
        if updates:
            works_collection.bulk_write(list(updates), ordered=False)
            stats["updated"] += len(updates)
            updates.clear()

    for n, orcid_id in enumerate(authors, 1):
        try:
            summaries = parse_work_groups(orcid_id, fetch_works(orcid_id))
        except Exception as e:
            logger.warning(f"{orcid_id}: could not fetch works ({e})")
            stats["failed_authors"].append(orcid_id)
            continue

        for doc in works_collection.find({"orcid_id": orcid_id},
                                         {"put_code": 1, "orcid_group": 1, "external_ids": 1}):
            stats["documents"] += 1
            summary = summaries.get(doc.get("put_code"))
            if summary is None:
                stats["not_on_orcid"] += 1
                continue
            changes = _work_update(doc, summary)
            if changes:
                updates.append(UpdateOne({"_id": doc["_id"]}, {"$set": changes}))
        if len(updates) >= BULK_BATCH_SIZE:
            flush()
        if n % 100 == 0:
            logger.info(f"  {n}/{len(authors)} authors")
    flush()

    stats["status"] = "success" if not stats["failed_authors"] else "partial"
    logger.info(f"orcid_group migration completed: {stats}")
    return stats


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from src.db.MongoConnection import MongoConnection
    from src.orcid.search.OrcidSearchClient import OrcidSearchClient

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    client = OrcidSearchClient("https://pub.orcid.org/v3.0", client_id=os.getenv("ACCESS_TOKEN"))
    print(add_orcid_groups(mongo.works(), client.get_works))
    mongo.close()
