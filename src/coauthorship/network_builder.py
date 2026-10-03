"""
Co-authorship Network Builder

This module provides the logic to construct co-authorship networks from MongoDB data.
It correctly handles the fact that publications may appear multiple times in the database
(once per author with an ORCID).
"""

from collections import Counter, defaultdict
from typing import Dict, List, Optional
import logging

from src.analytics.aggregations import build_works_match
from src.coauthorship.models import Publication, Node, Edge, NetworkData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoauthorshipNetworkBuilder:
    """
    Builds co-authorship networks from MongoDB publication data.
    
    This class handles the core logic of:
    1. Deduplicating publications by work_key (DOI or matched title)
    2. Extracting all authors per publication
    3. Computing author productivity (publication counts)
    4. Computing collaboration edges with weights
    """
    
    def __init__(self):
        self.publications: Dict[str, Publication] = {}  # keyed by work_key
        self.author_publication_counts: Counter = Counter()
        self.collaboration_counts: Counter = Counter()
    
    def add_document(self, document: Dict) -> None:
        """
        Process a single MongoDB document and add it to the network.
        
        MongoDB stores one document per author per publication, and an ORCID
        record can list the same publication several times, so documents are
        merged by work_key (see src/works/work_key.py) and their authors combined.
        
        Args:
            document: MongoDB document with work_key, doi, orcid_id, and contributors
        """
        work_key = document.get('work_key')
        orcid_id = document.get('orcid_id')
        year = document.get('publication_year')
        
        if not work_key:
            logger.debug(f"Skipping document without work_key")
            return
        
        # Get or create publication
        if work_key not in self.publications:
            self.publications[work_key] = Publication(doi=document.get('doi') or work_key, year=year)
        
        publication = self.publications[work_key]
        
        # Add main author (from orcid_id field)
        if orcid_id:
            publication.add_author(orcid_id)
        
        # Add contributors with valid ORCID IDs
        contributors = document.get('contributors', [])
        if contributors and isinstance(contributors, list):
            for contributor in contributors:
                if isinstance(contributor, dict):
                    contrib_orcid = contributor.get('orcid_id')
                    if contrib_orcid:
                        publication.add_author(contrib_orcid)
    
    def _compute_author_counts(self) -> None:
        """
        Compute publication count for each author.
        
        This counts how many unique publications each author has contributed to.
        """
        self.author_publication_counts.clear()
        
        for publication in self.publications.values():
            for author_id in publication.authors:
                self.author_publication_counts[author_id] += 1
    
    def _compute_collaboration_edges(self) -> None:
        """
        Compute collaboration edges from multi-author publications.
        
        For each multi-author publication, creates edges between all pairs
        of co-authors and counts the number of shared publications.
        """
        self.collaboration_counts.clear()
        
        for publication in self.publications.values():
            if publication.is_collaboration():
                pairs = publication.get_coauthor_pairs()
                for pair in pairs:
                    self.collaboration_counts[pair] += 1
    
    def build(self) -> NetworkData:
        """
        Build the complete co-authorship network.
        
        Returns:
            NetworkData object containing nodes and edges
        """
        logger.info(f"Building network from {len(self.publications)} unique publications")
        
        # Compute metrics
        self._compute_author_counts()
        self._compute_collaboration_edges()
        
        # Create nodes for all authors
        nodes = [
            Node(id=orcid_id, publications=count)
            for orcid_id, count in self.author_publication_counts.items()
        ]
        
        # Create edges for all collaborations
        edges = [
            Edge(source=pair[0], target=pair[1], weight=weight)
            for pair, weight in self.collaboration_counts.items()
        ]
        
        network = NetworkData(nodes=nodes, edges=edges)
        
        stats = network.get_stats()
        logger.info(f"Network built: {stats['total_nodes']} nodes, "
                   f"{stats['total_edges']} edges, "
                   f"{stats['solo_authors']} solo authors")
        
        return network
    
    def reset(self) -> None:
        """Clear all data and reset the builder."""
        self.publications.clear()
        self.author_publication_counts.clear()
        self.collaboration_counts.clear()


class MongoDBNetworkExtractor:
    """
    Extracts co-authorship network data from MongoDB.
    
    This class handles the MongoDB query and delegates network construction
    to CoauthorshipNetworkBuilder.
    """
    
    def __init__(self, db):
        """
        Initialize the extractor.
        
        Args:
            db: MongoDB database connection
        """
        self.db = db
    
    def extract_network(
        self,
        start_year: int,
        end_year: int,
        types: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        institutes: Optional[List[str]] = None
    ) -> NetworkData:
        """
        Extract co-authorship network for a given year range and optional filters.

        Args:
            start_year: Starting year for filtering publications
            end_year: Ending year for filtering publications
            types: Optional work types to include (any of)
            subjects: Optional OpenAlex topic fields to include (any of)
            keywords: Optional keywords to include (any of)
            institutes: Optional institute names to include (any of)

        Returns:
            NetworkData object containing the complete network
        """
        logger.info(f"Extracting network for years {start_year}-{end_year} "
                    f"(types={types}, subjects={subjects}, keywords={keywords}, institutes={institutes})")

        # Query MongoDB for relevant documents
        pipeline = [
            {
                "$match": build_works_match(
                    start_year=start_year, end_year=end_year, types=types,
                    subjects=subjects, keywords=keywords, institutes=institutes
                )
            },
            {
                "$project": {
                    "_id": 0,
                    "doi": 1,
                    "work_key": 1,
                    "orcid_id": 1,
                    "publication_year": 1,
                    # Only contributor ORCID iDs are used; skipping names/tokens cuts transfer ~3x
                    "contributors.orcid_id": 1
                }
            }
        ]
        
        logger.info("Executing MongoDB aggregation pipeline")
        documents = list(self.db.works.aggregate(pipeline))
        logger.info(f"Retrieved {len(documents)} documents from MongoDB")
        
        # Build network
        builder = CoauthorshipNetworkBuilder()
        
        for doc in documents:
            builder.add_document(doc)
        
        network = builder.build()
        
        return network
