"""
Master migration script: Execute all data migrations in correct order.

Runs all migrations sequentially:
1. migrate_doi - Extract DOI from external_ids
2. merge_metadata - Join works_metadata into works
3. enrich_institutions - Add institution information
4. link_contributors - Link contributors to ORCID profiles
5. add_author_count - Precompute author counts
6. create_indexes - Create optimized indexes
7. drop_unused_indexes - Remove obsolete indexes
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path so src module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.db.MongoConnection import MongoConnection

# Import all migration modules
from src.data_migration.migrate_doi import migrate_doi
from src.data_migration.merge_metadata import merge_metadata
from src.data_migration.enrich_institutions import enrich_institutions
from src.data_migration.link_contributors import link_contributors
from src.data_migration.add_author_count import add_author_count
from src.data_migration.create_indexes import create_indexes
from src.data_migration.drop_unused_indexes import drop_unused_indexes


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Orchestrates execution of all data migrations."""
    
    def __init__(self, mongo_connection: MongoConnection):
        self.mongo = mongo_connection
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def run_migration(
        self, 
        name: str, 
        migration_func,
        *args
    ) -> Tuple[str, Dict]:
        """
        Execute a single migration and track results.
        
        Args:
            name: Migration name
            migration_func: Function to execute
            *args: Arguments to pass to migration function
            
        Returns:
            Tuple of (migration_name, result_dict)
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"MIGRATION: {name}")
        logger.info(f"{'='*70}")
        
        try:
            result = migration_func(*args)
            logger.info(f"Status: {result.get('status', 'unknown')}")
            return (name, result)
        
        except Exception as e:
            logger.error(f"Migration failed with exception: {str(e)}")
            return (
                name,
                {
                    "status": "error",
                    "message": str(e)
                }
            )
    
    def run_all(self) -> Dict:
        """
        Execute all migrations in correct order.
        
        Returns:
            Summary dictionary with all migration results
        """
        self.start_time = datetime.now()
        logger.info(f"\n{'*'*70}")
        logger.info("DATA MIGRATION PIPELINE - STARTING")
        logger.info(f"Start time: {self.start_time}")
        logger.info(f"{'*'*70}\n")
        
        migrations: List[Tuple[str, callable, tuple]] = [
            (
                "1. Extract DOI from external_ids",
                migrate_doi,
                (self.mongo.works(),)
            ),
            (
                "2. Merge metadata from works_metadata",
                merge_metadata,
                (self.mongo.works(), self.mongo.metadata())
            ),
            (
                "3. Enrich institutions from ORCID profiles",
                enrich_institutions,
                (self.mongo.works(), self.mongo.orcids())
            ),
            (
                "4. Link contributors to ORCID profiles",
                link_contributors,
                (self.mongo.works(), self.mongo.orcids())
            ),
            (
                "5. Add precomputed author_count",
                add_author_count,
                (self.mongo.works(),)
            ),
            (
                "6. Create optimized indexes",
                create_indexes,
                (self.mongo.works(),)
            ),
            (
                "7. Drop unused indexes",
                drop_unused_indexes,
                (self.mongo.works(),)
            ),
        ]
        
        successful = 0
        failed = 0
        
        for migration_name, migration_func, args in migrations:
            result_name, result_data = self.run_migration(
                migration_name,
                migration_func,
                *args
            )
            
            self.results.append({
                "name": result_name,
                "result": result_data
            })
            
            if result_data.get("status") == "error":
                failed += 1
                logger.error(f"✗ FAILED: {result_name}")
                logger.error(f"  Error: {result_data.get('message', 'Unknown error')}")
            else:
                successful += 1
                logger.info(f"✓ SUCCESS: {result_name}")
        
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time
        
        # Print summary
        logger.info(f"\n{'*'*70}")
        logger.info("DATA MIGRATION PIPELINE - SUMMARY")
        logger.info(f"{'*'*70}")
        logger.info(f"Start time: {self.start_time}")
        logger.info(f"End time: {self.end_time}")
        logger.info(f"Duration: {duration}")
        logger.info(f"\nTotal migrations: {len(migrations)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"{'*'*70}\n")
        
        # Detailed results
        logger.info("DETAILED RESULTS:")
        logger.info("-" * 70)
        
        for i, result in enumerate(self.results, 1):
            logger.info(f"\n{i}. {result['name']}")
            logger.info(f"   Status: {result['result'].get('status', 'unknown')}")
            
            for key, value in result['result'].items():
                if key != 'status':
                    logger.info(f"   {key}: {value}")
        
        logger.info("\n" + "="*70)
        
        return {
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "duration": str(duration),
            "total_migrations": len(migrations),
            "successful": successful,
            "failed": failed,
            "results": self.results
        }


def main():
    """Main entry point for migration pipeline."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_CONN")
    db_name = os.getenv("DB_NAME")
    
    if not mongo_uri or not db_name:
        logger.error("Missing MONGO_CONN or DB_NAME environment variables")
        sys.exit(1)
    
    mongo = None
    
    try:
        mongo = MongoConnection(mongo_uri, db_name)
        runner = MigrationRunner(mongo)
        summary = runner.run_all()
        
        # Exit with appropriate code
        if summary["failed"] > 0:
            logger.error(f"Migration pipeline completed with {summary['failed']} failures")
            sys.exit(1)
        else:
            logger.info("Migration pipeline completed successfully")
            sys.exit(0)
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
    
    finally:
        if mongo:
            mongo.close()


if __name__ == "__main__":
    main()
