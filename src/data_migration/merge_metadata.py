"""
Migration: Merge enriched metadata from works_metadata into works.

For each work with a DOI, retrieves matching metadata from works_metadata
and copies concepts, keywords, and topics fields.
"""
import logging
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def merge_metadata(works_collection, metadata_collection):
    """
    Merge metadata from works_metadata into works documents.
    
    Args:
        works_collection: MongoDB works collection
        metadata_collection: MongoDB works_metadata collection
    """
    logger.info("Starting metadata merge migration...")
    
    # Find all works with DOI
    works_with_doi = works_collection.find(
        {"doi": {"$exists": True, "$ne": None}},
        {"_id": 1, "doi": 1}
    )
    
    updated_count = 0
    merged_count = 0
    errors = 0
    
    try:
        works_list = list(works_with_doi)
        logger.info(f"Found {len(works_list)} works with DOI to process")
        
        for work in works_list:
            try:
                doi = work["doi"]
                
                # Find metadata by DOI (OpenAlex source preferred)
                metadata = metadata_collection.find_one(
                    {"doi": doi},
                    {"concepts": 1, "keywords": 1, "topics": 1}
                )
                
                if metadata:
                    update_dict = {}
                    
                    if "concepts" in metadata and metadata["concepts"]:
                        update_dict["concepts"] = metadata["concepts"]
                        merged_count += 1
                    
                    if "keywords" in metadata and metadata["keywords"]:
                        update_dict["keywords"] = metadata["keywords"]
                    
                    if "topics" in metadata and metadata["topics"]:
                        update_dict["topics"] = metadata["topics"]
                    
                    if update_dict:
                        works_collection.update_one(
                            {"_id": work["_id"]},
                            {"$set": update_dict}
                        )
                        updated_count += 1
                
            except Exception as e:
                logger.error(f"Error merging metadata for work {work['_id']}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Metadata merge completed. Updated: {updated_count}, "
            f"Merged: {merged_count}, Errors: {errors}"
        )
        return {
            "status": "success",
            "updated": updated_count,
            "merged": merged_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Metadata merge migration failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


def merge_open_access(works_collection, metadata_collection):
    """
    Merge open access information from works_metadata into works documents.
    
    For each work with a DOI, retrieves matching metadata from works_metadata
    and copies is_oa and oa_url fields from the open_access object.
    
    Args:
        works_collection: MongoDB works collection
        metadata_collection: MongoDB works_metadata collection
    """
    logger.info("Starting open access merge migration...")
    
    # Find all works with DOI
    works_with_doi = works_collection.find(
        {"doi": {"$exists": True, "$ne": None}},
        {"_id": 1, "doi": 1}
    )
    
    updated_count = 0
    merged_count = 0
    errors = 0
    
    try:
        works_list = list(works_with_doi)
        logger.info(f"Found {len(works_list)} works with DOI to process")
        
        for work in works_list:
            try:
                doi = work["doi"]
                
                # Find metadata by DOI
                metadata = metadata_collection.find_one(
                    {"doi": doi},
                    {"open_access": 1}
                )
                
                if metadata and "open_access" in metadata:
                    open_access = metadata["open_access"]
                    update_dict = {}
                    
                    # Extract is_oa if present
                    if "is_oa" in open_access:
                        update_dict["is_oa"] = open_access["is_oa"]
                        merged_count += 1
                    
                    # Extract oa_url if present
                    if "oa_url" in open_access and open_access["oa_url"]:
                        update_dict["oa_url"] = open_access["oa_url"]
                    
                    if update_dict:
                        works_collection.update_one(
                            {"_id": work["_id"]},
                            {"$set": update_dict}
                        )
                        updated_count += 1
                        logger.debug(f"Updated work {work['_id']} with open access info")
                
            except Exception as e:
                logger.error(f"Error merging open access for work {work['_id']}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Open access merge completed. Updated: {updated_count}, "
            f"Merged: {merged_count}, Errors: {errors}"
        )
        return {
            "status": "success",
            "updated": updated_count,
            "merged": merged_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Open access merge migration failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


def check_works_count(orcids_collection, works_collection):
    """
    Verify and update works_count field in orcids collection.
    
    For each ORCID profile, counts the actual number of works associated
    with that orcid_id in the works collection and updates works_count
    if it doesn't match.
    
    Args:
        orcids_collection: MongoDB orcids collection
        works_collection: MongoDB works collection
    """
    logger.info("Starting works count verification...")
    
    # Find all orcids documents
    orcids_cursor = orcids_collection.find(
        {"orcid_id": {"$exists": True, "$ne": None}},
        {"_id": 1, "orcid_id": 1, "works_count": 1}
    )
    
    updated_count = 0
    verified_count = 0
    errors = 0
    
    try:
        orcids_list = list(orcids_cursor)
        logger.info(f"Found {len(orcids_list)} ORCID profiles to verify")
        
        for orcid_doc in orcids_list:
            try:
                orcid_id = orcid_doc["orcid_id"]
                current_works_count = orcid_doc.get("works_count", 0)
                
                # Count actual works for this orcid_id
                actual_works_count = works_collection.count_documents(
                    {"orcid_id": orcid_id}
                )
                
                verified_count += 1
                
                # Update if counts don't match
                if actual_works_count != current_works_count:
                    orcids_collection.update_one(
                        {"_id": orcid_doc["_id"]},
                        {"$set": {"works_count": actual_works_count}}
                    )
                    updated_count += 1
                    logger.info(
                        f"Updated works_count for ORCID {orcid_id}: "
                        f"{current_works_count} -> {actual_works_count}"
                    )
                else:
                    logger.debug(f"Works count correct for ORCID {orcid_id}: {actual_works_count}")
                
            except Exception as e:
                logger.error(f"Error verifying works count for ORCID {orcid_doc.get('orcid_id', 'unknown')}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Works count verification completed. Verified: {verified_count}, "
            f"Updated: {updated_count}, Errors: {errors}"
        )
        return {
            "status": "success",
            "verified": verified_count,
            "updated": updated_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Works count verification failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add project root to path so src module can be imported
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    result = check_works_count(mongo.orcids(), mongo.works())
    print(result)
    mongo.close()
