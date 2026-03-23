"""
Analytics module for scholarly publication data.

Provides MongoDB aggregation pipelines for computing publication statistics,
institutional analysis, author metrics, and summary reports.
"""

from .aggregations import (
    publications_per_year,
    publications_per_institution_per_year,
    publications_per_type,
    top_authors,
    author_contributor_analysis,
    publication_metrics_summary
)

__all__ = [
    'publications_per_year',
    'publications_per_institution_per_year',
    'publications_per_type',
    'top_authors',
    'author_contributor_analysis',
    'publication_metrics_summary'
]
