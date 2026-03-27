"""
Domain models for co-authorship network.

This module defines the core data structures representing publications, authors,
and the co-authorship network graph.
"""

from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional
from collections import Counter


@dataclass
class Author:
    """Represents an author identified by ORCID."""
    orcid_id: str
    publication_count: int = 0
    
    def __hash__(self):
        return hash(self.orcid_id)
    
    def __eq__(self, other):
        if isinstance(other, Author):
            return self.orcid_id == other.orcid_id
        return False


@dataclass
class Publication:
    """Represents a unique publication with its authors."""
    doi: str
    authors: Set[str] = field(default_factory=set)  # Set of ORCID IDs
    year: Optional[int] = None
    
    def add_author(self, orcid_id: str) -> None:
        """Add an author to this publication."""
        if orcid_id:
            self.authors.add(orcid_id)
    
    def is_collaboration(self) -> bool:
        """Check if this is a multi-author publication."""
        return len(self.authors) > 1
    
    def get_coauthor_pairs(self) -> List[tuple]:
        """
        Generate all pairwise collaborations from this publication.
        
        Returns:
            List of (orcid1, orcid2) tuples representing collaborations.
        """
        if not self.is_collaboration():
            return []
        
        authors_list = sorted(list(self.authors))
        pairs = []
        
        for i in range(len(authors_list)):
            for j in range(i + 1, len(authors_list)):
                pairs.append((authors_list[i], authors_list[j]))
        
        return pairs


@dataclass
class Node:
    """Represents a node in the co-authorship network."""
    id: str  # ORCID ID
    publications: int  # Number of publications
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "publications": self.publications
        }


@dataclass
class Edge:
    """Represents an edge (collaboration) in the co-authorship network."""
    source: str  # Source ORCID
    target: str  # Target ORCID
    weight: int  # Number of shared publications
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight
        }


@dataclass
class NetworkData:
    """Complete co-authorship network data."""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges]
        }
    
    def get_stats(self) -> Dict:
        """Get network statistics."""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "total_collaborations": sum(edge.weight for edge in self.edges),
            "solo_authors": sum(1 for node in self.nodes if node.publications > 0 and 
                               not any(e.source == node.id or e.target == node.id for e in self.edges))
        }
