"""
Co-authorship Network Module

This package provides tools for analyzing and visualizing co-authorship networks
from scholarly publication data stored in MongoDB.
"""

from .coauthorship_aggregator import get_coauthorship_data

__all__ = ['get_coauthorship_data']