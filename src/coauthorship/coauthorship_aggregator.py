"""
Co-authorship Network Aggregator

This module provides the main interface for computing co-authorship networks
from MongoDB works collection using an object-oriented approach.
"""

from typing import Dict, Any, List, Optional
import logging

from src.coauthorship.network_builder import MongoDBNetworkExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoauthorshipAggregator:
    """
    Main aggregator class for co-authorship network computation.
    
    This class provides a clean interface for extracting and formatting
    co-authorship network data from MongoDB.
    """
    
    def __init__(self, db):
        """
        Initialize the aggregator.
        
        Args:
            db: MongoDB database connection
        """
        self.db = db
        self.extractor = MongoDBNetworkExtractor(db)
    
    def get_network_data(
        self,
        start_year: int,
        end_year: int,
        types: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        institutes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compute co-authorship network data for a given year range and optional
        filters (work types, subjects, keywords, institutes; each matches any of
        the given values).
        
        This method:
        1. Queries MongoDB for publications in the year range
        2. Deduplicates publications by work_key (DOI or matched title)
        3. Extracts all authors (with and without ORCIDs)
        4. Computes productivity (publication counts per author)
        5. Computes collaboration edges and weights
        
        Args:
            start_year: Starting year for filtering publications
            end_year: Ending year for filtering publications
        
        Returns:
            Dictionary containing 'nodes' and 'edges' lists suitable for JSON serialization.
            
            Nodes structure:
            [
                {"id": "0000-0001-2345-6789", "publications": 5},
                ...
            ]
            
            Edges structure:
            [
                {"source": "0000-0001-2345-6789", "target": "0000-0002-3456-7890", "weight": 3},
                ...
            ]
        
        Raises:
            ValueError: If year range is invalid
            Exception: If database query or processing fails
        """
        # Validate input
        if start_year > end_year:
            raise ValueError(f"start_year ({start_year}) cannot be greater than end_year ({end_year})")
        
        if start_year < 1900 or end_year > 2100:
            raise ValueError(f"Years must be between 1900 and 2100")
        
        try:
            logger.info(f"Starting co-authorship aggregation for {start_year}-{end_year}")
            
            # Extract network using the builder
            network = self.extractor.extract_network(
                start_year, end_year, types=types, subjects=subjects,
                keywords=keywords, institutes=institutes
            )
            
            # Get statistics for logging
            stats = network.get_stats()
            logger.info(f"Network statistics: {stats}")
            
            # Convert to dictionary for API response
            return network.to_dict()
            
        except Exception as e:
            logger.error(f"Error in get_network_data: {str(e)}", exc_info=True)
            raise


def get_coauthorship_data(db, start_year: int, end_year: int) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    
    This function maintains the same interface as the original implementation
    but uses the new OOP approach internally.
    
    Args:
        db: MongoDB database connection
        start_year: Starting year for filtering publications
        end_year: Ending year for filtering publications
    
    Returns:
        Dictionary containing 'nodes' and 'edges' lists
    """
    aggregator = CoauthorshipAggregator(db)
    return aggregator.get_network_data(start_year, end_year)
