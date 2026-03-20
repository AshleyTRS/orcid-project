"""
Migration: Add precomputed author_count field.

Adds author_count field to each work, computed as the length of
the contributors array for fast aggregation queries.
"""
import logging
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_author_count(collection):
    """
    Add author_count field (precomputed from contributors array length).
    
    Args:
        collection: MongoDB works collection
    """
    logger.info("Starting author_count migration...")
    
    try:
        # Use MongoDB aggregation pipeline to compute author_count
        pipeline = [
            {
                "$addFields": {
                    "author_count": {
                        "$cond": [
                            {
                                "$isArray": "$contributors"
                            },
                            {"$size": "$contributors"},
                            0
                        ]
                    }
                }
            },
            {
                "$merge": {
                    "into": "works",
                    "whenMatched": "replace",
                    "whenNotMatched": "insert"
                }
            }
        ]
        
        result = collection.aggregate(pipeline)
        # Force evaluation of the aggregation
        list(result)
        
        # Verify the update
        total_works = collection.count_documents({})
        with_author_count = collection.count_documents(
            {"author_count": {"$exists": True}}
        )
        
        logger.info(
            f"Author count migration completed. "
            f"Total works: {total_works}, With author_count: {with_author_count}"
        )
        
        return {
            "status": "success",
            "total_works": total_works,
            "with_author_count": with_author_count
        }
    
    except Exception as e:
        logger.error(f"Author count migration failed: {str(e)}")
        
        # Fallback: Use batch update if $merge not available
        logger.info("Attempting fallback batch update method...")
        try:
            works = collection.find({}, {"_id": 1, "contributors": 1})
            updated_count = 0
            errors = 0
            
            for work in works:
                try:
                    contributors = work.get("contributors", [])
                    author_count = len(contributors) if isinstance(contributors, list) else 0
                    
                    collection.update_one(
                        {"_id": work["_id"]},
                        {"$set": {"author_count": author_count}}
                    )
                    updated_count += 1
                
                except Exception as inner_e:
                    logger.error(f"Error updating work {work['_id']}: {str(inner_e)}")
                    errors += 1
            
            logger.info(
                f"Fallback author count update completed. "
                f"Updated: {updated_count}, Errors: {errors}"
            )
            return {
                "status": "success (fallback)",
                "updated": updated_count,
                "errors": errors
            }
        
        except Exception as fallback_e:
            logger.error(f"Fallback author count migration also failed: {str(fallback_e)}")
            return {
                "status": "error",
                "message": str(fallback_e)
            }


if __name__ == "__main__":
    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    result = add_author_count(mongo.works())
    print(result)
    mongo.close()
