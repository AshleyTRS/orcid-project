"""
Migration: give every works document a `work_key` and every author a
`unique_works_count`.

ORCID records can contain the same publication several times (one entry per
import source, each with a different put_code). Documents are kept as
harvested; `work_key` marks which ones are the same work so analytics count
each work once. See src/works/work_key.py for the matching rules.

Safe to re-run: only documents whose key or count changes are written.
Run after migrate_doi and link_contributors (it reads both).
"""
import logging
import sys
from pathlib import Path

# Add project root to path so src module can be imported when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.works.work_key import apply_work_keys, update_unique_works_counts

logger = logging.getLogger(__name__)


def add_work_key(works_collection, orcids_collection):
    """
    Backfill works.work_key, index it, and recompute orcids.unique_works_count.

    Args:
        works_collection: MongoDB works collection
        orcids_collection: MongoDB orcids collection

    Returns:
        Status dict with document, update and distinct-work counts
    """
    logger.info("Assigning work_key to works...")
    try:
        keys = apply_work_keys(works_collection)

        works_collection.create_index([("work_key", 1)])
        works_collection.create_index([("orcid_id", 1), ("work_key", 1)])

        counts = update_unique_works_counts(works_collection, orcids_collection)
        # The search page lists authors by unique works
        orcids_collection.create_index([("unique_works_count", -1), ("orcid_id", 1)])
        distinct_works = len(works_collection.distinct("work_key"))

        result = {
            "status": "success",
            "documents": keys["documents"],
            "work_keys_updated": keys["updated"],
            "distinct_works": distinct_works,
            "duplicate_documents": keys["documents"] - distinct_works,
            "authors": counts["authors"],
            "unique_works_counts_updated": counts["updated"],
        }
        logger.info(f"work_key migration completed: {result}")
        return result

    except Exception as e:
        logger.error(f"work_key migration failed: {str(e)}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from src.db.MongoConnection import MongoConnection

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    print(add_work_key(mongo.works(), mongo.orcids()))
    mongo.close()
