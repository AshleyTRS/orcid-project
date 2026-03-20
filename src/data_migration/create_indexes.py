"""
Migration: Create optimized indexes for analytical queries.

Creates indexes on works collection to optimize:
- Statistical aggregation
- Author productivity analysis
- NLP grouping
- Graph analysis
- General querying
"""
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_indexes(collection):
    """
    Create optimized indexes on works collection.
    
    Args:
        collection: MongoDB works collection
    """
    logger.info("Starting index creation migration...")
    
    # Define all indexes to create
    indexes = [
        # Single field indexes
        (
            [("doi", 1)],
            {"name": "doi_1", "sparse": True},
            "DOI lookup"
        ),
        (
            [("publication_year", 1)],
            {"name": "publication_year_1", "sparse": True},
            "Year-based queries"
        ),
        (
            [("type", 1)],
            {"name": "type_1"},
            "Work type filtering"
        ),
        (
            [("author_count", 1)],
            {"name": "author_count_1", "sparse": True},
            "Author productivity analysis"
        ),
        
        # Compound indexes for aggregation
        (
            [("publication_year", 1), ("type", 1)],
            {"name": "publication_year_type_1"},
            "Year and type aggregation"
        ),
        (
            [("orcid_id", 1), ("publication_year", 1)],
            {"name": "orcid_id_publication_year_1"},
            "Author productivity by year"
        ),
        
        # Contributor analysis
        (
            [("contributors.orcid_id", 1)],
            {"name": "contributors_orcid_id_1", "sparse": True},
            "Co-authorship network analysis"
        ),
        (
            [("contributors.orcid_id", 1), ("publication_year", 1)],
            {"name": "contributors_orcid_id_publication_year_1", "sparse": True},
            "Co-authorship timeline analysis"
        ),
        
        # Institution analysis
        (
            [("institutions.name", 1)],
            {"name": "institutions_name_1", "sparse": True},
            "Institutional productivity"
        ),
        
        # NLP grouping
        (
            [("topics.display_name", 1)],
            {"name": "topics_display_name_1", "sparse": True},
            "Topic-based grouping"
        ),
        (
            [("concepts.display_name", 1)],
            {"name": "concepts_display_name_1", "sparse": True},
            "Concept-based grouping"
        ),
        
        # ORCID lookups
        (
            [("orcid_id", 1)],
            {"name": "orcid_id_1"},
            "ORCID profile lookup (already exists, will skip)"
        ),
    ]
    
    created_count = 0
    skipped_count = 0
    errors = 0
    
    try:
        for index_spec, index_opts, description in indexes:
            try:
                logger.info(f"Creating index for {description}: {index_spec}")
                
                collection.create_index(index_spec, **index_opts)
                created_count += 1
                logger.info(f"✓ Index created: {index_opts['name']}")
            
            except Exception as e:
                # Index might already exist or be a duplicate
                if "already exists" in str(e) or "dup key" in str(e).lower():
                    logger.warning(
                        f"⊘ Index already exists: {index_opts['name']} - {description}"
                    )
                    skipped_count += 1
                else:
                    logger.error(f"✗ Error creating index {index_opts['name']}: {str(e)}")
                    errors += 1
        
        logger.info(
            f"Index creation migration completed. "
            f"Created: {created_count}, Skipped: {skipped_count}, Errors: {errors}"
        )
        
        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Index creation migration failed: {str(e)}")
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
    result = create_indexes(mongo.works())
    print(result)
    mongo.close()
