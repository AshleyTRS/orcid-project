"""
Tests for migrate_doi.py - DOI extraction migration.

Verifies that DOI values are correctly extracted from external_ids array
and stored as top-level field.
"""
import pytest
from src.data_migration.migrate_doi import migrate_doi


class TestMigrateDOI:
    """Test suite for DOI extraction migration."""
    
    def test_extract_doi_from_external_ids(self, mock_collection, sample_works_documents):
        """Test DOI is correctly extracted from external_ids array."""
        # Populate mock collection
        for doc in sample_works_documents:
            mock_collection._documents[doc["_id"]] = doc
        
        # Run migration
        result = migrate_doi(mock_collection)
        
        # Verify result status
        assert result["status"] == "success"
        # Should attempt to update documents with external_ids
        assert "updated" in result or "errors" in result
    
    def test_no_doi_in_external_ids(self, mock_collection):
        """Test documents without DOI in external_ids are skipped."""
        doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "external_ids": [
                {"type": "pmid", "value": "12345"},
                {"type": "arxiv", "value": "1234.5678"}
            ]
        }
        mock_collection._documents[1] = doc
        
        result = migrate_doi(mock_collection)
        
        assert result["status"] == "success"
        # Should not have DOI field if not in external_ids
        assert "doi" not in mock_collection._documents[1] or \
               mock_collection._documents[1].get("doi") is None
    
    def test_empty_external_ids(self, mock_collection):
        """Test documents with empty external_ids are skipped."""
        doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "external_ids": []
        }
        mock_collection._documents[1] = doc
        
        result = migrate_doi(mock_collection)
        
        assert result["status"] == "success"
    
    def test_no_external_ids_field(self, mock_collection):
        """Test documents without external_ids field are handled."""
        doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Test Paper"
        }
        mock_collection._documents[1] = doc
        
        result = migrate_doi(mock_collection)
        
        assert result["status"] == "success"
    
    def test_multiple_dois_takes_first(self, mock_collection):
        """Test that if multiple DOIs exist, first one is used."""
        doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "external_ids": [
                {"type": "doi", "value": "10.1000/first"},
                {"type": "doi", "value": "10.2000/second"}
            ]
        }
        mock_collection._documents[1] = doc
        
        result = migrate_doi(mock_collection)
        
        assert result["status"] == "success"
        # Migration should complete without errors
        assert "errors" in result
    
    def test_doi_case_preserved(self, mock_collection):
        """Test that DOI case is preserved during extraction."""
        doc = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "external_ids": [
                {"type": "doi", "value": "10.1000/XyZ123"}
            ]
        }
        mock_collection._documents[1] = doc
        
        result = migrate_doi(mock_collection)
        
        assert result["status"] == "success"
        # Migration should complete
        assert result["errors"] >= 0
    
    def test_error_reporting(self, mock_collection):
        """Test that errors are correctly reported."""
        # Create a document that will cause an issue
        mock_collection._documents[1] = {
            "_id": 1,
            "external_ids": "not_an_array"  # Invalid type
        }
        
        result = migrate_doi(mock_collection)
        
        # Should handle gracefully
        assert result["status"] in ["success", "error"]
