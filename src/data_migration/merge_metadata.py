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


if __name__ == "__main__":
    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    result = merge_metadata(mongo.works(), mongo.metadata())
    print(result)
    mongo.close()
