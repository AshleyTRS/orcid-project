"""
Co-authorship Network Aggregator

This module provides functionality to compute co-authorship networks from MongoDB works collection.
It generates nodes (authors) and edges (collaborations) based on publication data within a specified year range.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_coauthorship_data(db, start_year: int, end_year: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compute co-authorship network data for a given year range.
    
    Includes all authors (solo and collaborative) and all collaborations.

    Args:
        db: MongoDB database connection
        start_year: Starting year for filtering publications
        end_year: Ending year for filtering publications

    Returns:
        Dictionary containing 'nodes' and 'edges' lists.
        Nodes include all authors with publication counts.
        Edges represent collaborations between authors.
    """
    try:
        logger.info(f"Starting coauthorship aggregation for {start_year}-{end_year}")
        
        # Get all documents with DOI and orcid_id in year range (both solo and multi-author)
        pipeline = [
            {
                "$match": {
                    "publication_year": {"$gte": start_year, "$lte": end_year},
                    "doi": {"$exists": True, "$ne": None},
                    "orcid_id": {"$exists": True, "$ne": None}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "doi": 1,
                    "orcid_id": 1,
                    "contributors": 1
                }
            }
        ]

        logger.info("Running MongoDB aggregation pipeline")
        documents = list(db.works.aggregate(pipeline))
        logger.info(f"Retrieved {len(documents)} documents from MongoDB")

        # Group documents by DOI and count author publications
        publications_by_doi = defaultdict(set)
        author_counts = Counter()  # Total publication count per author
        
        for doc in documents:
            doi = doc.get('doi')
            orcid_id = doc.get('orcid_id')
            
            if doi and orcid_id:
                # Add main author
                publications_by_doi[doi].add(orcid_id)
                author_counts[orcid_id] += 1
                
                # Add contributors with valid ORCID IDs
                contributors = doc.get('contributors', [])
                if contributors and isinstance(contributors, list):
                    for contributor in contributors:
                        if isinstance(contributor, dict):
                            contrib_orcid = contributor.get('orcid_id')
                            if contrib_orcid and contrib_orcid is not None:
                                publications_by_doi[doi].add(contrib_orcid)
                                author_counts[contrib_orcid] += 1
        
        logger.info(f"Grouped into {len(publications_by_doi)} publications by DOI")
        logger.info(f"Found {len(author_counts)} unique authors")

        # Separate solo and multi-author publications
        solo_author_pubs = {
            doi: authors for doi, authors in publications_by_doi.items()
            if len(authors) == 1
        }
        
        multi_author_pubs = {
            doi: authors for doi, authors in publications_by_doi.items()
            if len(authors) > 1
        }
        
        logger.info(f"Found {len(solo_author_pubs)} solo-author publications and {len(multi_author_pubs)} multi-author publications")

        # Compute edges only from multi-author publications
        edge_counts = Counter()

        for doi, authors in multi_author_pubs.items():
            authors_list = list(authors)
            
            # Generate all pairwise collaborations
            for i in range(len(authors_list)):
                for j in range(i + 1, len(authors_list)):
                    pair = tuple(sorted([authors_list[i], authors_list[j]]))
                    edge_counts[pair] += 1

        # Create nodes for ALL authors with their total publication counts
        nodes = [
            {"id": orcid, "publications": count}
            for orcid, count in author_counts.items()
        ]

        # Create edges from collaborations
        edges = [
            {"source": pair[0], "target": pair[1], "weight": weight}
            for pair, weight in edge_counts.items()
        ]

        logger.info(f"Generated {len(nodes)} nodes (all authors) and {len(edges)} edges (collaborations only)")
        return {"nodes": nodes, "edges": edges}

    except Exception as e:
        logger.error(f"Error in get_coauthorship_data: {str(e)}", exc_info=True)
        raise