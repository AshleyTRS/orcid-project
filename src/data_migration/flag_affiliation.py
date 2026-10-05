"""
Migration: flag which researchers and works belong to UAEH.

Sets orcids.uaeh_affiliated and works.uaeh_work (see src/orcid/affiliation.py).
Nothing is deleted: researchers with no affiliation to the university stay in
the database but are left out of every listing and statistic.

With fetch_activities (the ORCID Public API, run as a script with
--verify-live), researchers whose stored institutions do not mention UAEH are
checked against their current ORCID record; those who list UAEH there get the
UAEH institution names added to institution_names and are flagged.

Safe to re-run: only values that change are written. Run after add_work_key
(works are flagged per work_key).
"""
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

# Add project root to path so src module can be imported when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orcid.affiliation import (
    flag_affiliated_authors,
    flag_uaeh_works,
    is_uaeh_affiliated,
    uaeh_institutions_from_activities,
)

logger = logging.getLogger(__name__)


def verify_unmatched_authors(orcids_collection, fetch_activities: Callable[[str], Dict]) -> Dict:
    """
    Check researchers whose stored institutions do not mention UAEH against
    their live ORCID record, adding the UAEH institutions found there.

    Returns:
        {"checked": int, "found": int, "failed": [orcid_id]}
    """
    unmatched = [a for a in orcids_collection.find({}, {"orcid_id": 1, "institution_names": 1})
                 if not is_uaeh_affiliated(a.get("institution_names"))]
    stats = {"checked": len(unmatched), "found": 0, "failed": []}
    for author in unmatched:
        try:
            names = uaeh_institutions_from_activities(fetch_activities(author["orcid_id"]))
        except Exception as e:
            logger.warning(f"{author['orcid_id']}: could not fetch affiliations ({e})")
            stats["failed"].append(author["orcid_id"])
            continue
        if names:
            orcids_collection.update_one(
                {"_id": author["_id"]},
                {"$addToSet": {"institution_names": {"$each": names}}}
            )
            stats["found"] += 1
    logger.info(f"Live affiliation check: {stats}")
    return stats


def flag_affiliation(works_collection, orcids_collection,
                     fetch_activities: Optional[Callable[[str], Dict]] = None) -> Dict:
    """
    Flag UAEH researchers and works, optionally verifying unmatched researchers live.

    Returns:
        Status dict with the counts of each step
    """
    try:
        result = {"status": "success"}
        if fetch_activities is not None:
            result["live_check"] = verify_unmatched_authors(orcids_collection, fetch_activities)
        result["authors"] = flag_affiliated_authors(orcids_collection)
        result["works"] = flag_uaeh_works(works_collection, orcids_collection)

        # Listing affiliated researchers by unique works
        orcids_collection.create_index([("uaeh_affiliated", 1), ("unique_works_count", -1), ("orcid_id", 1)])
        logger.info(f"Affiliation migration completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Affiliation migration failed: {str(e)}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import os

    import requests
    from dotenv import load_dotenv
    from src.db.MongoConnection import MongoConnection

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))

    fetch = None
    if "--verify-live" in sys.argv:
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})

        def fetch(orcid_id):
            response = session.get(f"https://pub.orcid.org/v3.0/{orcid_id}/activities", timeout=30)
            response.raise_for_status()
            return response.json()

    print(flag_affiliation(mongo.works(), mongo.orcids(), fetch))
    mongo.close()
