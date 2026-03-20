"""
Migration: Extract DOI from external_ids and add as top-level field.

Extracts the DOI value from the external_ids array and stores it as a 
top-level 'doi' field in each works document.
"""
import logging
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_doi(collection):
    """
    Extract DOI from external_ids array and add as top-level field.
    
    Args:
        collection: MongoDB works collection
    """
    logger.info("Starting DOI extraction migration...")
    
    # Find all documents with external_ids containing DOI
    pipeline = [
        {
            "$match": {
                "external_ids": {
                    "$exists": True,
                    "$type": "array",
                    "$ne": []
                }
            }
        },
        {
            "$addFields": {
                "doi": {
                    "$arrayElemAt": [
                        {
                            "$filter": {
                                "input": "$external_ids",
                                "as": "ext_id",
                                "cond": {
                                    "$eq": ["$$ext_id.type", "doi"]
                                }
                            }
                        },
                        0
                    ]
                }
            }
        },
        {
            "$addFields": {
                "doi": "$doi.value"
            }
        },
        {
            "$match": {
                "doi": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "doi": 1
            }
        }
    ]
    
    updated_count = 0
    errors = 0
    
    try:
        cursor = collection.aggregate(pipeline)
        documents = list(cursor)
        logger.info(f"Found {len(documents)} documents with DOI to update")
        
        for doc in documents:
            try:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"doi": doc["doi"]}}
                )
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating document {doc['_id']}: {str(e)}")
                errors += 1
        
        logger.info(f"DOI migration completed. Updated: {updated_count}, Errors: {errors}")
        return {
            "status": "success",
            "updated": updated_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"DOI migration failed: {str(e)}")
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
    result = migrate_doi(mongo.works())
    print(result)
    mongo.close()
