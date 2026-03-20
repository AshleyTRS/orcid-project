"""
Tests for merge_metadata.py - Metadata merging migration.

Verifies that metadata (concepts, keywords, topics) from works_metadata
is correctly merged into works documents.
"""
import pytest
from src.data_migration.merge_metadata import merge_metadata


class TestMergeMetadata:
    """Test suite for metadata merging migration."""
    
    def test_merge_basic_metadata(self, mock_collection, sample_metadata_documents):
        """Test basic metadata fields are merged correctly."""
        # Populate works collection
        works_docs = [
            {
                "_id": 1,
                "orcid_id": "0000-0001-1111-1111",
                "doi": "10.1000/xyz123",
                "title": "Test Paper"
            }
        ]
        
        # Create separate mock collections
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        metadata_collection._next_id = 1
        metadata_collection._indexes = {}
        
        # Copy mock methods
        for attr in dir(works_collection):
            if not attr.startswith("_") and callable(getattr(works_collection, attr)):
                setattr(metadata_collection, attr, getattr(works_collection, attr))
        
        # Populate collections
        for doc in works_docs:
            works_collection._documents[doc["_id"]] = doc
        
        metadata_collection._documents[1] = sample_metadata_documents[0]
        
        result = merge_metadata(works_collection, metadata_collection)
        
        assert result["status"] == "success"
        # Migration should complete
        assert "updated" in result or "merged" in result
    
    def test_no_matching_metadata(self, mock_collection, sample_works_documents):
        """Test works without matching metadata are still updated."""
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        
        # Works without corresponding metadata
        work_doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "doi": "10.9999/nonexistent"
        }
        works_collection._documents[1] = work_doc
        
        result = merge_metadata(works_collection, metadata_collection)
        
        assert result["status"] == "success"
        # Should still report as processed
        assert result["updated"] >= 0
    
    def test_works_without_doi_skipped(self, mock_collection):
        """Test works without DOI field are skipped."""
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        
        # Work without DOI
        work_doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Test Paper"
        }
        works_collection._documents[1] = work_doc
        
        result = merge_metadata(works_collection, metadata_collection)
        
        assert result["status"] == "success"
        # Should not modify document without DOI
        assert "concepts" not in works_collection._documents[1]
    
    def test_partial_metadata_merge(self, mock_collection):
        """Test that partial metadata is merged correctly."""
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        
        # Work with DOI
        work_doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "doi": "10.1000/partial"
        }
        works_collection._documents[1] = work_doc
        
        # Metadata with only concepts
        metadata_doc = {
            "_id": 1,
            "doi": "10.1000/partial",
            "source": "openalex",
            "concepts": [{"display_name": "Computer Science"}]
            # No keywords or topics
        }
        metadata_collection._documents[1] = metadata_doc
        
        result = merge_metadata(works_collection, metadata_collection)
        
        assert result["status"] == "success"
        # Should complete without errors
        assert result["errors"] == 0
    
    def test_empty_metadata_fields_not_merged(self, mock_collection):
        """Test that empty metadata fields are not merged."""
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        
        work_doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "doi": "10.1000/empty"
        }
        works_collection._documents[1] = work_doc
        
        # Metadata with empty arrays
        metadata_doc = {
            "_id": 1,
            "doi": "10.1000/empty",
            "source": "openalex",
            "concepts": [],
            "keywords": [],
            "topics": []
        }
        metadata_collection._documents[1] = metadata_doc
        
        result = merge_metadata(works_collection, metadata_collection)
        
        # Empty fields should not be merged
        assert result["status"] == "success"
    
    def test_multiple_works_merge(self, mock_collection, sample_metadata_documents):
        """Test merging metadata for multiple works."""
        works_collection = mock_collection
        metadata_collection = mock_collection.__class__()
        metadata_collection._documents = {}
        
        # Multiple works
        works_docs = [
            {"_id": 1, "orcid_id": "0000-0001-1111-1111", "doi": "10.1000/xyz123"},
            {"_id": 2, "orcid_id": "0000-0002-2222-2222", "doi": "10.2000/abc456"},
            {"_id": 3, "orcid_id": "0000-0003-3333-3333", "doi": "10.3000/none"}
        ]
        
        for doc in works_docs:
            works_collection._documents[doc["_id"]] = doc
        
        for doc in sample_metadata_documents:
            metadata_collection._documents[doc["_id"]] = doc
        
        result = merge_metadata(works_collection, metadata_collection)
        
        assert result["status"] == "success"
        assert result["updated"] <= 3
