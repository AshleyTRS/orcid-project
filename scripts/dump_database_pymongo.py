"""
Database dump script (PyMongo): Create timestamped backups of MongoDB database.

Alternative to mongodump using PyMongo. Creates JSON backups of all collections.
Backups are stored in ./backups/ directory with timestamp.

Usage:
    python scripts/dump_database_pymongo.py              # Dump the database
    python scripts/dump_database_pymongo.py --help       # Show help
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path so src module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.MongoConnection import MongoConnection


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB ObjectId and other special types."""
    def default(self, obj):
        from bson import ObjectId
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def dump_collection(collection, backup_dir: Path, collection_name: str) -> int:
    """
    Dump a single collection to JSON file.
    
    Args:
        collection: PyMongo collection object
        backup_dir: Directory to save dump
        collection_name: Name of collection (for filename)
        
    Returns:
        Number of documents dumped
    """
    backup_file = backup_dir / f"{collection_name}.json"
    
    logger.info(f"Dumping collection: {collection_name}...")
    
    try:
        # Find all documents
        documents = list(collection.find({}))
        
        # Write to JSON file
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, cls=JSONEncoder)
        
        logger.info(f"✓ ({len(documents)} documents)")
        return len(documents)
    
    except Exception as e:
        logger.error(f"✗ Failed: {str(e)}")
        return 0


def dump_database_pymongo(mongo_uri: str, db_name: str, backup_dir: str = "backups") -> bool:
    """
    Create a MongoDB database dump using PyMongo.
    
    Args:
        mongo_uri: MongoDB connection URI
        db_name: Database name to dump
        backup_dir: Directory to store backups (default: ./backups)
        
    Returns:
        True if successful, False otherwise
    """
    # Create backup directory
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    # Create timestamped subdirectory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = backup_path / f"{db_name}_backup_pymongo_{timestamp}"
    backup_subdir.mkdir(exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("DATABASE DUMP (PyMongo) - STARTING")
    logger.info("=" * 70)
    logger.info(f"Database: {db_name}")
    logger.info(f"Backup location: {backup_subdir.absolute()}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info("=" * 70)
    
    mongo = None
    total_documents = 0
    
    try:
        # Connect to MongoDB
        mongo = MongoConnection(mongo_uri, db_name)
        
        # Get all collection names
        collection_names = mongo.db.list_collection_names()
        logger.info(f"\nFound {len(collection_names)} collections to dump:\n")
        
        if not collection_names:
            logger.warning("No collections found in database")
            return False
        
        # Dump each collection
        for collection_name in collection_names:
            try:
                collection = mongo.db[collection_name]
                count = dump_collection(collection, backup_subdir, collection_name)
                total_documents += count
            except Exception as e:
                logger.error(f"Error dumping {collection_name}: {str(e)}")
        
        # Create metadata file
        metadata = {
            "database": db_name,
            "timestamp": timestamp,
            "collections": collection_names,
            "total_documents": total_documents,
            "backed_up_at": datetime.now().isoformat()
        }
        
        metadata_file = backup_subdir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("\n" + "=" * 70)
        logger.info(f"✓ SUCCESS: Database backup completed")
        logger.info(f"  Collections: {len(collection_names)}")
        logger.info(f"  Total documents: {total_documents}")
        logger.info(f"  Location: {backup_subdir.absolute()}")
        logger.info(f"  Metadata: {metadata_file.name}")
        
        # Get directory size
        total_size = sum(f.stat().st_size for f in backup_subdir.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        logger.info(f"  Total size: {size_mb:.2f} MB")
        logger.info("=" * 70)
        
        return True
    
    except Exception as e:
        logger.error(f"\n✗ FAILED: {str(e)}")
        return False
    
    finally:
        if mongo:
            mongo.close()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_CONN")
    db_name = os.getenv("DB_NAME")
    
    if not mongo_uri or not db_name:
        logger.error("Missing MONGO_CONN or DB_NAME environment variables")
        logger.error("Make sure your .env file contains:")
        logger.error("  MONGO_CONN=<your_mongodb_uri>")
        logger.error("  DB_NAME=<your_database_name>")
        sys.exit(1)
    
    # Run dump
    success = dump_database_pymongo(mongo_uri, db_name)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
