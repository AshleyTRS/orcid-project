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
import re
import unicodedata
from typing import List, Dict, Optional
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Search helpers ------------------------------------------------------------

MAX_SEARCH_TERMS = 10

# Characters that commonly carry accents in Spanish/Portuguese/French names,
# mapped to every variant so "Garcia" matches "García" and vice versa.
_ACCENT_VARIANTS = {
    "a": "aáàäâã", "e": "eéèëê", "i": "iíìïî", "o": "oóòöôõ",
    "u": "uúùüû", "n": "nñ", "c": "cç", "y": "yý",
}


def strip_accents(text: str) -> str:
    """Return ``text`` lower-cased with diacritics removed."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def accent_insensitive_regex(text: str) -> str:
    """
    Build a regex that matches ``text`` regardless of accents.

    Use with ``$options: "i"``. Upper-case variants are included explicitly
    because case-folding of non-ASCII letters is not guaranteed.
    """
    parts = []
    for ch in strip_accents(text):
        variants = _ACCENT_VARIANTS.get(ch)
        if variants:
            parts.append(f"[{variants}{variants.upper()}]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def search_terms(query: Optional[str]) -> List[str]:
    """Split a free-text query into at most MAX_SEARCH_TERMS whitespace-separated terms."""
    if not query:
        return []
    return query.split()[:MAX_SEARCH_TERMS]


def _regex(text: str) -> Dict:
    return {"$regex": accent_insensitive_regex(text), "$options": "i"}


def build_works_match(
    query: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    types: Optional[List[str]] = None,
    subjects: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    institutes: Optional[List[str]] = None
) -> Dict:
    """
    Build a ``$match`` filter for works that have a DOI.

    Shared by the works search and the co-authorship network so both apply
    filters identically. Every argument is optional; list arguments match
    works having any of the given values.

    Args:
        query: Free text; every term must match the title, a contributor
            name or the DOI (accent-insensitive)
        start_year / end_year: Inclusive publication_year bounds
        types: Work types, e.g. "journal-article"
        subjects: OpenAlex topic fields, e.g. "Computer Science"
        keywords: OpenAlex keyword display names
        institutes: Institute names, matched as accent-insensitive
            substrings of the affiliated institution names
    """
    conditions = [{"doi": {"$exists": True, "$ne": None}}]

    year_range = {}
    if start_year is not None:
        year_range["$gte"] = start_year
    if end_year is not None:
        year_range["$lte"] = end_year
    if year_range:
        conditions.append({"publication_year": year_range})

    for term in search_terms(query):
        conditions.append({"$or": [
            {"title": _regex(term)},
            # normalized_name is lower-case, accent-free and stores hyphens as spaces
            {"contributors.normalized_name": {
                "$regex": re.escape(re.sub(r"[-‐]+", " ", strip_accents(term)))
            }},
            {"doi": {"$regex": re.escape(term), "$options": "i"}},
        ]})

    if types:
        conditions.append({"type": {"$in": types}})
    if subjects:
        conditions.append({"topics.field.display_name": {"$in": subjects}})
    if keywords:
        conditions.append({"keywords.display_name": {"$in": keywords}})
    if institutes:
        conditions.append({"$or": [{"institutions.name": _regex(name)} for name in institutes]})

    return {"$and": conditions}


def publications_per_year(
    db,
    start_year: int = 1969,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Aggregate publication counts by year.
    
    Counts unique DOIs per publication_year within the requested range.
    Handles duplicate work documents for the same DOI to prevent overcounting.
    
    Args:
        db: MongoDB database object
        start_year: Filter results from this year onwards (default: 1969)
        end_year: Filter results up to this year (default: current year)
    
    Returns:
        List of dicts with format:
        [
            { "year": 2020, "count": 120 },
            { "year": 2021, "count": 150 }
        ]
    
    Example:
        >>> stats = publications_per_year(mongo.db)
        >>> for record in stats:
        ...     print(f"{record['year']}: {record['count']} publications")
    """
    current_year = datetime.now(timezone.utc).year
    end_year = current_year if end_year is None else end_year
    logger.info(f"Computing publications per year (range: {start_year}-{end_year})...")
    
    try:
        works_collection = db.works
        
        # Build match stage to filter by DOI, year range, and exclude invalid values
        match_filters = {
            "doi": {"$exists": True, "$ne": None},
            "publication_year": {"$exists": True, "$ne": None}
        }
        
        match_filters["publication_year"]["$gte"] = start_year
        match_filters["publication_year"]["$lte"] = end_year
        
        # Aggregation pipeline deduplicates by DOI per year first, then counts unique DOIs per year
        pipeline = [
            {"$match": match_filters},
            {
                "$group": {
                    "_id": {
                        "doi": "$doi",
                        "year": "$publication_year"
                    }
                }
            },
            {
                "$group": {
                    "_id": "$_id.year",
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


def all_authors_details(
    db,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> List[Dict]:
    """
    Get all authors with their publication counts and details from the orcids collection.
    
    Queries the orcids collection and returns all authors with their ORCID IDs,
    names, publication counts, and a placeholder institute value.
    
    Args:
        db: MongoDB database object
        start_year: Not used (kept for consistency with other functions)
        end_year: Not used (kept for consistency with other functions)
    
    Returns:
        List of dicts with format:
        [
            {
                "orcid_id": "0000-0001-2345-6789",
                "given_names": "Given Name",
                "family_names": "Family Name",
                "count": 50,
                "institute": "INSTITUTO"
            }
        ]
    
    Example:
        >>> authors = all_authors_details(mongo.db)
        >>> for author in authors:
        ...     print(f"{author['orcid_id']}: {author['count']} publications")
    """
    logger.info("Computing all authors details from orcids collection...")
    
    try:
        orcids_collection = db.orcids
        
        # Query all documents from orcids collection
        results = list(orcids_collection.find({}, {
            "orcid_id": 1,
            "given_names": 1,
            "family_names": 1,
            "works_count": 1
        }))
        
        # Format the results
        formatted_results = [
            {
                "orcid_id": doc["orcid_id"],
                "given_names": doc.get("given_names", ""),
                "family_names": doc.get("family_names", ""),
                "count": doc.get("works_count", 0),
                "institute": "INSTITUTO"
            }
            for doc in results
        ]
        
        # Sort by count descending
        formatted_results.sort(key=lambda x: x["count"], reverse=True)
        
        logger.info(f"SUCCESS: Computed all authors details: returned {len(formatted_results)} authors")
        return formatted_results
    
    except Exception as e:
        logger.error(f"ERROR: Computing all authors details: {str(e)}")
        raise


def all_authors_details_paginated(
    db,
    page: int = 1,
    limit: int = 50,
    query: Optional[str] = None,
    institutes: Optional[List[str]] = None
) -> Dict:
    """
    Get paginated authors with minimal fields for fast loading.

    Fetches authors from the orcids collection with pagination support.
    Sorts by works_count DESC for most productive authors first.

    Args:
        db: MongoDB database object
        page: Page number (1-indexed, default: 1)
        limit: Results per page (default: 50, max: 100)
        query: Optional free text. Every term must match the author's given
            names, family names, credit name or ORCID iD (accent-insensitive).
        institutes: Optional institute names; authors affiliated with any of
            them (substring match on institution_names) are returned.

    Returns:
        Dict with format:
        {
            "data": [
                {
                    "orcid_id": "0000-0001-2345-6789",
                    "given_names": "Given Name",
                    "family_names": "Family Name",
                    "count": 50
                }
            ],
            "page": 1,
            "has_next": true,
            "total": 5386
        }
    
    Example:
        >>> result = all_authors_details_paginated(mongo.db, page=1, limit=50)
        >>> print(f"Page {result['page']}: {len(result['data'])} authors")
    """
    logger.info(f"Fetching authors page {page} with limit {limit}...")
    
    try:
        orcids_collection = db.orcids
        
        # Ensure reasonable limits
        limit = max(1, min(limit, 100))  # 1-100 items per page
        page = max(1, page)
        skip = (page - 1) * limit

        conditions = [
            {"$or": [
                {"given_names": _regex(term)},
                {"family_names": _regex(term)},
                {"credit_name": _regex(term)},
                {"orcid_id": {"$regex": re.escape(term), "$options": "i"}},
            ]}
            for term in search_terms(query)
        ]
        if institutes:
            conditions.append({"$or": [{"institution_names": _regex(name)} for name in institutes]})
        match_filter = {"$and": conditions} if conditions else {}

        # Get total count (for has_next calculation)
        total = orcids_collection.count_documents(match_filter)

        # Fetch paginated results sorted by works_count DESC (orcid_id keeps page boundaries stable)
        results = list(orcids_collection.find(
            match_filter,
            {
                "orcid_id": 1,
                "given_names": 1,
                "family_names": 1,
                "works_count": 1
            }
        ).sort([("works_count", -1), ("orcid_id", 1)]).skip(skip).limit(limit))
        
        # Format the results
        formatted_results = [
            {
                "orcid_id": doc["orcid_id"],
                "given_names": doc.get("given_names") or "",
                "family_names": doc.get("family_names") or "",
                "count": doc.get("works_count") or 0
            }
            for doc in results
        ]

        has_next = (skip + limit) < total
        
        response = {
            "data": formatted_results,
            "page": page,
            "has_next": has_next,
            "total": total
        }
        
        logger.info(f"SUCCESS: Fetched page {page} with {len(formatted_results)} authors (has_next: {has_next})")
        return response
    
    except Exception as e:
        logger.error(f"ERROR: Fetching paginated authors: {str(e)}")
        raise


def all_works_details(db) -> List[Dict]:
    """
    Return unique works details grouped by DOI.

    Collects one representative work document per unique DOI and returns
    the requested fields. Includes ``oa_url`` only when ``is_oa`` is True.

    Args:
        db: MongoDB database object

    Returns:
        List of dicts with the selected work details.
    """
    logger.info("Computing all unique works details from works collection...")

    try:
        works_collection = db.works

        cursor = works_collection.find(
            {"doi": {"$exists": True, "$ne": None}},
            {
                "doi": 1,
                "title": 1,
                "journal_title": 1,
                "publication_year": 1,
                "type": 1,
                "contributors": 1,
                "visibility": 1,
                "concepts": 1,
                "keywords": 1,
                "topics": 1,
                "is_oa": 1,
                "oa_url": 1
            }
        )

        formatted_results = []
        seen_dois = set()
        for doc in cursor:
            try:
                doi = doc.get("doi")
                if not doi:
                    logger.warning("Skipping work with missing doi")
                    continue
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)

                raw_contributors = doc.get("contributors")
                contributors = []
                if isinstance(raw_contributors, list):
                    for contributor in raw_contributors:
                        if isinstance(contributor, dict):
                            name = contributor.get("credit_name")
                            if name:
                                contributors.append(name)

                is_oa = bool(doc.get("is_oa", False))
                work_entry = {
                    "doi": doi,
                    "title": doc.get("title", ""),
                    "journal_title": doc.get("journal_title", ""),
                    "publication_year": doc.get("publication_year"),
                    "type": doc.get("type", ""),
                    "contributors": contributors,
                    "visibility": doc.get("visibility", ""),
                    "concepts": doc.get("concepts") if isinstance(doc.get("concepts"), list) else [],
                    "keywords": doc.get("keywords") if isinstance(doc.get("keywords"), list) else [],
                    "topics": doc.get("topics") if isinstance(doc.get("topics"), list) else [],
                    "is_oa": is_oa
                }

                if is_oa:
                    oa_url = doc.get("oa_url")
                    if oa_url:
                        work_entry["oa_url"] = oa_url

                formatted_results.append(work_entry)
            except Exception as inner_error:
                logger.error(f"Error formatting work for DOI {doc.get('doi', 'unknown')}: {inner_error}")
                continue

        logger.info(f"Found {len(formatted_results)} unique DOI-based works")
        logger.info(f"SUCCESS: Computed all works details: returned {len(formatted_results)} unique works")
        return formatted_results

    except Exception as e:
        logger.error(f"ERROR: Computing all works details: {str(e)}")
        raise


def all_works_details_paginated(
    db,
    page: int = 1,
    limit: int = 50,
    query: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    keywords: Optional[List[str]] = None,
    institutes: Optional[List[str]] = None
) -> Dict:
    """
    Get paginated works with minimal fields for fast loading.

    Fetches unique works (by DOI) from the works collection with pagination support.
    The same publication is stored once per harvested co-author, so documents are
    grouped by DOI before paginating; ``total`` is the number of unique DOIs.
    Sorts by publication_year DESC to show recent publications first.

    Args:
        db: MongoDB database object
        page: Page number (1-indexed, default: 1)
        limit: Results per page (default: 50, max: 100)
        query: Optional free text. Every term must match the title, a
            contributor name or the DOI (accent-insensitive).
        start_year: Optional inclusive lower bound on publication_year
        end_year: Optional inclusive upper bound on publication_year
        keywords: Optional keyword display names; works tagged with any are returned
        institutes: Optional institute names; works with an affiliated
            institution matching any of them (substring) are returned

    Returns:
        Dict with format:
        {
            "data": [
                {
                    "doi": "10.1234/example.doi",
                    "title": "Research Paper Title",
                    "publication_year": 2025,
                    "type": "journal-article",
                    "journal_title": "Journal Name",
                    "contributors": ["Name One", "Name Two"]
                }
            ],
            "page": 1,
            "has_next": true,
            "total": 14780
        }
    
    Example:
        >>> result = all_works_details_paginated(mongo.db, page=1, limit=50)
        >>> print(f"Page {result['page']}: {len(result['data'])} works")
    """
    logger.info(f"Fetching works page {page} with limit {limit}...")
    
    try:
        works_collection = db.works
        
        # Ensure reasonable limits
        limit = max(1, min(limit, 100))  # 1-100 items per page
        page = max(1, page)
        
        skip = (page - 1) * limit

        match_filter = build_works_match(
            query=query, start_year=start_year, end_year=end_year,
            keywords=keywords, institutes=institutes
        )

        # Filter first, then collapse per-author duplicates into one row per DOI,
        # then paginate and count in a single round trip.
        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$doi",
                "title": {"$first": "$title"},
                "publication_year": {"$max": "$publication_year"},
                "type": {"$first": "$type"},
                "journal_title": {"$first": "$journal_title"},
                "contributors": {"$first": "$contributors.credit_name"},
            }},
            {"$sort": {"publication_year": -1, "_id": 1}},
            {"$facet": {
                "data": [{"$skip": skip}, {"$limit": limit}],
                "total": [{"$count": "count"}],
            }},
        ]

        facet = next(works_collection.aggregate(pipeline), {"data": [], "total": []})
        results = facet["data"]
        total = facet["total"][0]["count"] if facet["total"] else 0

        # Format results
        formatted_results = [
            {
                "doi": doc["_id"],
                "title": doc.get("title") or "",
                "publication_year": doc.get("publication_year"),
                "type": doc.get("type") or "",
                "journal_title": doc.get("journal_title") or "",
                "contributors": [name for name in (doc.get("contributors") or []) if name]
            }
            for doc in results
        ]

        has_next = (skip + limit) < total
        
        response = {
            "data": formatted_results,
            "page": page,
            "has_next": has_next,
            "total": total
        }
        
        logger.info(f"SUCCESS: Fetched page {page} with {len(formatted_results)} works (has_next: {has_next})")
        return response
    
    except Exception as e:
        logger.error(f"ERROR: Fetching paginated works: {str(e)}")
        raise


def value_counts(db, field_path: str, limit: int = 100) -> List[Dict]:
    """
    Count unique works (by DOI) per value of ``field_path``, most frequent first.

    ``field_path`` may be a scalar field ("type") or a path into an array of
    sub-documents ("topics.field.display_name"); a value repeated within one
    work is counted once for that work.

    Returns:
        List of dicts: [{ "value": "journal-article", "count": 9120 }, ...]
    """
    logger.info(f"Computing top {limit} values of {field_path}...")

    try:
        pipeline = [
            {"$match": {"doi": {"$exists": True, "$ne": None}, field_path: {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$doi", "value": {"$first": f"${field_path}"}}},
            {"$unwind": "$value"},
            {"$group": {"_id": {"doi": "$_id", "value": "$value"}}},
            {"$group": {"_id": "$_id.value", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": limit},
        ]
        results = [
            {"value": doc["_id"], "count": doc["count"]}
            for doc in db.works.aggregate(pipeline)
            if doc["_id"]
        ]
        logger.info(f"SUCCESS: Computed {len(results)} values of {field_path}")
        return results

    except Exception as e:
        logger.error(f"ERROR: Computing values of {field_path}: {str(e)}")
        raise


def top_keywords(db, limit: int = 100) -> List[Dict]:
    """
    Return the most frequent keywords across unique works (by DOI).

    Returns:
        List of dicts: [{ "keyword": "Computer science", "count": 812 }, ...]
    """
    return [
        {"keyword": item["value"], "count": item["count"]}
        for item in value_counts(db, "keywords.display_name", limit=limit)
    ]


def main():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_CONN")
    db_name = os.getenv("DB_NAME")
    mongo = MongoConnection(mongo_uri, db_name)

    year_stats = publications_per_year(mongo.db)
    print(f"Publication counts returned for {len(year_stats)} years")
    if year_stats:
        print(year_stats[:5])

if __name__ == "__main__":
    main()