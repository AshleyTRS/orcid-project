"""Utility functions for data enrichment pipeline."""


def normalize_doi(doi_value):
    """Normalize a DOI value by removing URL prefixes and standardizing format.
    
    Handles multiple common DOI URL formats:
    - https://doi.org/10.xxxx
    - http://doi.org/10.xxxx
    - https://www.doi.org/10.xxxx
    - http://www.doi.org/10.xxxx
    - www.doi.org/10.xxxx
    - doi.org/10.xxxx
    
    Args:
        doi_value: String or non-string DOI value
        
    Returns:
        Lowercase, whitespace-stripped DOI value (e.g., "10.1234/example"),
        or None if input is not a string.
    """
    if not isinstance(doi_value, str):
        return None
    
    # Remove common URL prefixes
    normalized = doi_value.strip()
    prefixes = [
        "https://www.doi.org/",
        "http://www.doi.org/",
        "https://doi.org/",
        "http://doi.org/",
        "www.doi.org/",
        "doi.org/"
    ]
    
    for prefix in prefixes:
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    
    return normalized.strip().lower()
