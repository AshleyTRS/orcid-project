"""
Aggregation pipelines for scholarly publication analytics.

This module provides MongoDB aggregation queries to compute analytical metrics
over the works collection, including publication trends, institutional analysis,
publication types, and author productivity metrics.

Usage:
    from src.analytics.aggregations import publications_per_year
    from src.db.MongoConnection import MongoConnection
    
    mongo = MongoConnection(uri, db_name)
    stats = publications_per_year(mongo.db)
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def publications_per_year(
    db,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Aggregate publication counts by year.
    
    Groups all works by publication_year and returns count per year.
    Handles missing/null years and filters outliers.
    
    Args:
        db: MongoDB database object
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        List of dicts with format:
        [
            { "year": 2020, "count": 120 },
            { "year": 2021, "count": 150 }
        ]
    
    Example:
        >>> stats = publications_per_year(mongo.db, start_year=2020, end_year=2025)
        >>> for record in stats:
        ...     print(f"{record['year']}: {record['count']} publications")
    """
    logger.info(f"Computing publications per year (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage to filter by year range and exclude invalid years
        match_filters = {
            "publication_year": {"$exists": True, "$ne": None}
        }
        
        if start_year is not None:
            match_filters["publication_year"]["$gte"] = start_year
        
        if end_year is not None:
            match_filters["publication_year"]["$lte"] = end_year
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_filters},
            {
                "$group": {
                    "_id": "$publication_year",
                    "count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "year": "$_id",
                    "count": 1
                }
            },
            {"$sort": {"year": 1}}
        ]
        
        results = list(works_collection.aggregate(pipeline))
        logger.info(f"SUCCESS: Computed publications per year: {len(results)} years")
        return results
    
    except Exception as e:
        logger.error(f"ERROR: Computing publications per year: {str(e)}")
        raise


def publications_per_institution_per_year(
    db,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Aggregate publication counts by institution and year.
    
    Groups works by institution name and publication year. Handles missing
    institutions and years appropriately.
    
    Args:
        db: MongoDB database object
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        List of dicts with format:
        [
            {
                "institution": "Instituto Politécnico Nacional",
                "year": 2025,
                "count": 25
            }
        ]
    
    Example:
        >>> stats = publications_per_institution_per_year(mongo.db, start_year=2020)
        >>> for record in stats:
        ...     print(f"{record['institution']} ({record['year']}): {record['count']}")
    """
    logger.info(f"Computing publications per institution per year (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage
        match_filters = {
            "publication_year": {"$exists": True, "$ne": None},
            "institutions": {"$exists": True, "$ne": []}
        }
        
        if start_year is not None:
            match_filters["publication_year"]["$gte"] = start_year
        
        if end_year is not None:
            match_filters["publication_year"]["$lte"] = end_year
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_filters},
            {"$unwind": "$institutions"},
            {
                "$group": {
                    "_id": {
                        "institution": "$institutions.name",
                        "year": "$publication_year"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "institution": "$_id.institution",
                    "year": "$_id.year",
                    "count": 1
                }
            },
            {
                "$sort": {
                    "year": 1,
                    "count": -1
                }
            }
        ]
        
        results = list(works_collection.aggregate(pipeline))
        logger.info(f"SUCCESS: Computed publications per institution per year: {len(results)} records")
        return results
    
    except Exception as e:
        logger.error(f"ERROR: Computing publications per institution per year: {str(e)}")
        raise


def publications_per_type(
    db,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Aggregate publication counts by publication type.
    
    Groups works by type (journal-article, book-chapter, conference-paper, etc.)
    and counts publications in each category.
    
    Args:
        db: MongoDB database object
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        List of dicts with format:
        [
            { "type": "journal-article", "count": 300 },
            { "type": "book-chapter", "count": 80 }
        ]
    
    Example:
        >>> stats = publications_per_type(mongo.db)
        >>> for record in stats:
        ...     print(f"{record['type']}: {record['count']}")
    """
    logger.info(f"Computing publications per type (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage
        match_filters = {
            "type": {"$exists": True, "$ne": None}
        }
        
        if start_year is not None:
            match_filters["publication_year"] = {"$gte": start_year}
        
        if end_year is not None:
            if "publication_year" in match_filters:
                match_filters["publication_year"]["$lte"] = end_year
            else:
                match_filters["publication_year"] = {"$lte": end_year}
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_filters},
            {
                "$group": {
                    "_id": "$type",
                    "count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "type": "$_id",
                    "count": 1
                }
            },
            {"$sort": {"count": -1}}
        ]
        
        results = list(works_collection.aggregate(pipeline))
        logger.info(f"SUCCESS: Computed publications per type: {len(results)} types")
        return results
    
    except Exception as e:
        logger.error(f"ERROR: Computing publications per type: {str(e)}")
        raise


def top_authors(
    db,
    limit: int = 10,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Identify top authors by number of publications.
    
    Groups works by ORCID ID of the primary author (orcid_id field) and
    counts publications per author. Returns top N authors sorted by
    publication count descending.
    
    Args:
        db: MongoDB database object
        limit: Maximum number of authors to return (default: 10)
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        List of dicts with format:
        [
            { "orcid_id": "0000-0001-2345-6789", "count": 50 },
            { "orcid_id": "0000-0002-3456-7890", "count": 45 }
        ]
    
    Example:
        >>> top_10 = top_authors(mongo.db, limit=10)
        >>> top_5_recent = top_authors(mongo.db, limit=5, start_year=2023)
        >>> for author in top_10:
        ...     print(f"{author['orcid_id']}: {author['count']} publications")
    """
    logger.info(f"Computing top {limit} authors (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage
        match_filters = {
            "orcid_id": {"$exists": True, "$ne": None}
        }
        
        if start_year is not None:
            match_filters["publication_year"] = {"$gte": start_year}
        
        if end_year is not None:
            if "publication_year" in match_filters:
                match_filters["publication_year"]["$lte"] = end_year
            else:
                match_filters["publication_year"] = {"$lte": end_year}
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_filters},
            {
                "$group": {
                    "_id": "$orcid_id",
                    "count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "orcid_id": "$_id",
                    "count": 1
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        results = list(works_collection.aggregate(pipeline))
        logger.info(f"SUCCESS: Computed top {limit} authors: returned {len(results)} authors")
        return results
    
    except Exception as e:
        logger.error(f"ERROR: Computing top authors: {str(e)}")
        raise


def author_contributor_analysis(
    db,
    limit: int = 10,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Identify top contributors (including co-authors) by publication count.
    
    Unwraps the contributors array and aggregates publication counts for each
    contributor by ORCID ID. Returns top N contributors with verified ORCID IDs.
    
    Args:
        db: MongoDB database object
        limit: Maximum number of contributors to return (default: 10)
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        List of dicts with format:
        [
            {
                "orcid_id": "0000-0001-2345-6789",
                "name": "Author Name",
                "publication_count": 45
            }
        ]
    
    Example:
        >>> contributors = author_contributor_analysis(mongo.db, limit=15)
        >>> for contrib in contributors:
        ...     print(f"{contrib['name']} ({contrib['orcid_id']}): {contrib['publication_count']}")
    """
    logger.info(f"Computing top {limit} contributors (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage
        match_filters = {
            "contributors": {"$exists": True, "$ne": []}
        }
        
        if start_year is not None:
            match_filters["publication_year"] = {"$gte": start_year}
        
        if end_year is not None:
            if "publication_year" in match_filters:
                match_filters["publication_year"]["$lte"] = end_year
            else:
                match_filters["publication_year"] = {"$lte": end_year}
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_filters},
            {"$unwind": "$contributors"},
            {
                "$match": {
                    "contributors.orcid_id": {"$exists": True, "$ne": None}
                }
            },
            {
                "$group": {
                    "_id": {
                        "orcid_id": "$contributors.orcid_id",
                        "name": "$contributors.credit_name"
                    },
                    "publication_count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "orcid_id": "$_id.orcid_id",
                    "name": "$_id.name",
                    "publication_count": 1
                }
            },
            {"$sort": {"publication_count": -1}},
            {"$limit": limit}
        ]
        
        results = list(works_collection.aggregate(pipeline))
        logger.info(f"SUCCESS: Computed top {limit} contributors: returned {len(results)} contributors")
        return results
    
    except Exception as e:
        logger.error(f"ERROR: Computing top contributors: {str(e)}")
        raise


def publication_metrics_summary(
    db,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> Dict:
    """
    Generate a comprehensive summary of publication metrics.
    
    Computes key statistics including total publications, average authors,
    author distribution, and document type diversity.
    
    Args:
        db: MongoDB database object
        start_year: Filter results from this year onwards (optional)
        end_year: Filter results up to this year (optional)
    
    Returns:
        Dictionary with summary metrics:
        {
            "total_publications": 10000,
            "total_institutions": 150,
            "avg_authors_per_publication": 3.2,
            "min_authors": 1,
            "max_authors": 25,
            "publication_types": 8,
            "year_range": {"min": 2010, "max": 2025},
            "computed_at": "2026-03-20T..."
        }
    
    Example:
        >>> summary = publication_metrics_summary(mongo.db)
        >>> print(f"Total: {summary['total_publications']}")
        >>> print(f"Avg authors: {summary['avg_authors_per_publication']:.2f}")
    """
    logger.info(f"Computing publication metrics summary (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage
        match_filters = {}
        
        if start_year is not None:
            match_filters["publication_year"] = {"$gte": start_year}
        
        if end_year is not None:
            if "publication_year" in match_filters:
                match_filters["publication_year"]["$lte"] = end_year
            else:
                match_filters["publication_year"] = {"$lte": end_year}
        
        # Main aggregation pipeline
        pipeline = [
            {"$match": match_filters} if match_filters else {"$match": {}},
            {
                "$group": {
                    "_id": None,
                    "total_publications": {"$sum": 1},
                    "avg_authors": {"$avg": "$author_count"},
                    "min_authors": {"$min": "$author_count"},
                    "max_authors": {"$max": "$author_count"},
                    "min_year": {"$min": "$publication_year"},
                    "max_year": {"$max": "$publication_year"}
                }
            }
        ]
        
        # Get main statistics
        main_stats = list(works_collection.aggregate(pipeline))
        
        if not main_stats:
            logger.warning("No publications found for the specified criteria")
            return {}
        
        stats = main_stats[0]
        
        # Count unique institutions
        inst_pipeline = [
            {"$match": match_filters} if match_filters else {"$match": {}},
            {"$unwind": "$institutions"},
            {
                "$group": {
                    "_id": "$institutions.name"
                }
            },
            {"$count": "count"}
        ]
        
        inst_results = list(works_collection.aggregate(inst_pipeline))
        unique_institutions = inst_results[0]["count"] if inst_results else 0
        
        # Count unique publication types
        type_pipeline = [
            {"$match": match_filters} if match_filters else {"$match": {}},
            {
                "$group": {
                    "_id": "$type"
                }
            },
            {"$count": "count"}
        ]
        
        type_results = list(works_collection.aggregate(type_pipeline))
        unique_types = type_results[0]["count"] if type_results else 0
        
        # Build summary
        summary = {
            "total_publications": stats.get("total_publications", 0),
            "total_institutions": unique_institutions,
            "avg_authors_per_publication": round(stats.get("avg_authors", 0), 2),
            "min_authors": stats.get("min_authors", 0),
            "max_authors": stats.get("max_authors", 0),
            "publication_types": unique_types,
            "year_range": {
                "min": stats.get("min_year"),
                "max": stats.get("max_year")
            },
            "computed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"SUCCESS: Computed publication metrics summary")
        return summary
    
    except Exception as e:
        logger.error(f"ERROR: Computing publication metrics summary: {str(e)}")
        raise
