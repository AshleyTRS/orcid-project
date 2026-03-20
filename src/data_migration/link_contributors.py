"""
Migration: Link contributors to ORCID profiles.

Builds a mapping of normalized ORCID names (given_names + family_names)
and matches contributors by normalized name. Assigns orcid_id to matched
contributors.
"""
import logging
import re
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """
    Normalize a name for matching: lowercase, remove hyphens, trim whitespace.
    
    Args:
        name: Name string to normalize
        
    Returns:
        Normalized name string
    """
    if not name:
        return ""
    
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove hyphens
    normalized = normalized.replace("-", "")
    
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    
    return normalized


def link_contributors(works_collection, orcids_collection):
    """
    Link contributors to ORCID profiles by matching normalized names.
    
    Args:
        works_collection: MongoDB works collection
        orcids_collection: MongoDB orcids collection
    """
    logger.info("Starting contributor linking migration...")
    
    # Build ORCID name mapping
    logger.info("Building ORCID name mapping...")
    orcid_name_map = {}
    
    try:
        orcids = orcids_collection.find(
            {
                "$or": [
                    {"given_names": {"$exists": True, "$ne": None}},
                    {"family_names": {"$exists": True, "$ne": None}}
                ]
            },
            {"orcid_id": 1, "given_names": 1, "family_names": 1}
        )
        
        for orcid in orcids:
            given = orcid.get("given_names", "").strip()
            family = orcid.get("family_names", "").strip()
            
            if given or family:
                full_name = f"{given} {family}".strip()
                normalized = normalize_name(full_name)
                
                if normalized:
                    orcid_name_map[normalized] = orcid["orcid_id"]
        
        logger.info(f"Built mapping for {len(orcid_name_map)} ORCID names")
        
        # Process works and link contributors
        works = works_collection.find(
            {"contributors": {"$exists": True, "$type": "array"}},
            {"_id": 1, "contributors": 1}
        )
        
        updated_count = 0
        linked_count = 0
        errors = 0
        total_contributors = 0
        matched_contributors = 0
        
        works_list = list(works)
        logger.info(f"Processing {len(works_list)} works with contributors")
        
        for work in works_list:
            try:
                contributors = work.get("contributors", [])
                
                if not contributors:
                    continue
                
                total_contributors += len(contributors)
                
                # Update each contributor
                for i, contributor in enumerate(contributors):
                    normalized_name = contributor.get("normalized_name")
                    
                    if normalized_name:
                        normalized = normalize_name(normalized_name)
                        
                        if normalized in orcid_name_map:
                            orcid_id = orcid_name_map[normalized]
                            
                            works_collection.update_one(
                                {"_id": work["_id"]},
                                {
                                    "$set": {
                                        f"contributors.{i}.orcid_id": orcid_id
                                    }
                                }
                            )
                            
                            matched_contributors += 1
                            linked_count += 1
                
                updated_count += 1
            
            except Exception as e:
                logger.error(f"Error linking contributors in work {work['_id']}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Contributor linking completed. Works updated: {updated_count}, "
            f"Total contributors: {total_contributors}, Matched: {matched_contributors}, "
            f"Errors: {errors}"
        )
        return {
            "status": "success",
            "works_updated": updated_count,
            "total_contributors": total_contributors,
            "matched_contributors": matched_contributors,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Contributor linking migration failed: {str(e)}")
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
    result = link_contributors(mongo.works(), mongo.orcids())
    print(result)
    mongo.close()
