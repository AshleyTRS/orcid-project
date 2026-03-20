"""
Migration: Drop unused indexes.

Removes the contributors.normalized_name_1 index which is no longer needed
after linking contributors to ORCID profiles by orcid_id.
"""
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def drop_unused_indexes(collection):
    """
    Drop unused indexes from works collection.
    
    Args:
        collection: MongoDB works collection
    """
    logger.info("Starting unused index drop migration...")
    
    indexes_to_drop = [
        "contributors.normalized_name_1",
        "contributors_normalized_name_1"  # alternative naming
    ]
    
    dropped_count = 0
    not_found_count = 0
    errors = 0
    
    try:
        # Get current indexes
        current_indexes = collection.index_information()
        logger.info(f"Current indexes: {list(current_indexes.keys())}")
        
        for index_name in indexes_to_drop:
            try:
                if index_name in current_indexes:
                    logger.info(f"Dropping index: {index_name}")
                    collection.drop_index(index_name)
                    dropped_count += 1
                    logger.info(f"✓ Index dropped: {index_name}")
                else:
                    logger.warning(f"⊘ Index not found: {index_name}")
                    not_found_count += 1
            
            except Exception as e:
                logger.error(f"✗ Error dropping index {index_name}: {str(e)}")
                errors += 1
        
        logger.info(
            f"Unused index drop migration completed. "
            f"Dropped: {dropped_count}, Not found: {not_found_count}, Errors: {errors}"
        )
        
        return {
            "status": "success",
            "dropped": dropped_count,
            "not_found": not_found_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Unused index drop migration failed: {str(e)}")
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
    result = drop_unused_indexes(mongo.works())
    print(result)
    mongo.close()
