"""
Database dump script: Create timestamped backups of MongoDB database.

Creates a mongodump backup of the database specified in .env file.
Backups are stored in ./backups/ directory with timestamp.

Usage:
    python scripts/dump_database.py              # Dump the database
    python scripts/dump_database.py --help       # Show help
"""
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def dump_database(mongo_uri: str, db_name: str, backup_dir: str = "backups") -> bool:
    """
    Create a MongoDB database dump using mongodump.
    
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
    backup_subdir = backup_path / f"{db_name}_backup_{timestamp}"
    
    logger.info("=" * 70)
    logger.info("DATABASE DUMP - STARTING")
    logger.info("=" * 70)
    logger.info(f"Database: {db_name}")
    logger.info(f"Backup location: {backup_subdir.absolute()}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info("=" * 70)
    
    try:
        # Build mongodump command
        cmd = [
            "mongodump",
            f"--uri={mongo_uri}",
            f"--db={db_name}",
            f"--out={backup_subdir}"
        ]
        
        logger.info(f"Running command: mongodump --uri=<hidden> --db={db_name} --out={backup_subdir}")
        
        # Run mongodump
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            # Count backed up collections
            backup_db_dir = backup_subdir / db_name
            if backup_db_dir.exists():
                collections = len(list(backup_db_dir.glob("*.bson")))
                logger.info(f"\n✓ SUCCESS: Database backup completed")
                logger.info(f"  Collections backed up: {collections}")
                logger.info(f"  Location: {backup_subdir.absolute()}")
                
                # Get directory size
                total_size = sum(f.stat().st_size for f in backup_subdir.rglob("*") if f.is_file())
                size_mb = total_size / (1024 * 1024)
                logger.info(f"  Total size: {size_mb:.2f} MB")
                
                logger.info("=" * 70)
                return True
            else:
                logger.error("✗ FAILED: Backup directory not created")
                return False
        else:
            logger.error(f"\n✗ FAILED: mongodump returned error code {result.returncode}")
            if result.stderr:
                logger.error(f"Error message: {result.stderr}")
            return False
    
    except FileNotFoundError:
        logger.error("✗ FAILED: mongodump command not found")
        logger.error("  Please install MongoDB tools: https://docs.mongodb.com/database-tools/installation/")
        return False
    
    except Exception as e:
        logger.error(f"✗ FAILED: {str(e)}")
        return False


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
    success = dump_database(mongo_uri, db_name)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
