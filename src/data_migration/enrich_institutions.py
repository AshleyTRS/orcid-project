"""
Migration: Enrich works with institution information from ORCID profiles.

For each work, finds the corresponding ORCID document and copies
institution_names as an array of objects with 'name' field.
"""
import logging
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enrich_institutions(works_collection, orcids_collection):
    """
    Enrich works with institution information from ORCID profiles.
    
    Args:
        works_collection: MongoDB works collection
        orcids_collection: MongoDB orcids collection
    """
    logger.info("Starting institution enrichment migration...")
    
    # Find all works
    works = works_collection.find(
        {"orcid_id": {"$exists": True, "$ne": None}},
        {"_id": 1, "orcid_id": 1}
    )
    
    # Build ORCID to institutions mapping
    logger.info("Building ORCID to institutions mapping...")
    orcid_institutions = {}
    
    try:
        orcids = orcids_collection.find(
            {"institution_names": {"$exists": True, "$ne": []}},
            {"orcid_id": 1, "institution_names": 1}
        )
        
        for orcid in orcids:
            orcid_institutions[orcid["orcid_id"]] = orcid["institution_names"]
        
        logger.info(f"Built mapping for {len(orcid_institutions)} ORCIDs with institutions")
        
        # Enrich works with institutions
        updated_count = 0
        enriched_count = 0
        errors = 0
        
        works_list = list(works)
        logger.info(f"Processing {len(works_list)} works")
        
        for work in works_list:
            try:
                orcid_id = work["orcid_id"]
                
                if orcid_id in orcid_institutions:
                    # Convert institution names to array of objects
                    institutions = [
                        {"name": inst}
                        for inst in orcid_institutions[orcid_id]
                    ]
                    
                    works_collection.update_one(
                        {"_id": work["_id"]},
                        {"$set": {"institutions": institutions}}
                    )
                    
                    updated_count += 1
                    enriched_count += 1
                else:
                    # Still update to initialize field as empty array
                    works_collection.update_one(
                        {"_id": work["_id"]},
                        {"$set": {"institutions": []}}
                    )
                    updated_count += 1
            
            except Exception as e:
                logger.error(f"Error enriching work {work['_id']}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Institution enrichment completed. Updated: {updated_count}, "
            f"Enriched: {enriched_count}, Errors: {errors}"
        )
        return {
            "status": "success",
            "updated": updated_count,
            "enriched": enriched_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Institution enrichment migration failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    result = enrich_institutions(mongo.works(), mongo.orcids())
    print(result)
    mongo.close()
