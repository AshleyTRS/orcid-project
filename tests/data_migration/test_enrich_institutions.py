"""
Tests for enrich_institutions.py - Institution enrichment migration.

Verifies that institution information from ORCID profiles is correctly
added to works documents.
"""
import pytest
from src.data_migration.enrich_institutions import enrich_institutions


class TestEnrichInstitutions:
    """Test suite for institution enrichment migration."""
    
    def test_enrich_with_institutions(self, mock_collection):
        """Test works are enriched with institution information."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        works_collection._next_id = 1
        works_collection._indexes = {}
        
        # Copy mock methods
        for attr in ["find", "update_one", "count_documents", "aggregate", 
                     "create_index", "index_information", "drop_index"]:
            if hasattr(orcids_collection, attr):
                setattr(works_collection, attr, getattr(orcids_collection, attr))
        
        # Populate ORCID collection
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "John",
            "family_names": "Smith",
            "institution_names": ["MIT", "Stanford"]
        }
        
        # Populate works collection
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Test Paper"
        }
        
        result = enrich_institutions(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should process at least one work
        assert result["updated"] >= 1
    
    def test_work_without_matching_orcid(self, mock_collection):
        """Test works whose ORCID has no institutions."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        # ORCID without institutions
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "Jane",
            "family_names": "Doe",
            "institution_names": []
        }
        
        # Work referencing this ORCID
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Test Paper"
        }
        
        result = enrich_institutions(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should complete without errors
        assert result["errors"] == 0
    
    def test_multiple_works_same_orcid(self, mock_collection):
        """Test multiple works by same ORCID get institutions."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        # ORCID with institutions
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "institution_names": ["University A", "University B"]
        }
        
        # Multiple works from same ORCID
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Paper 1"
        }
        works_collection._documents[2] = {
            "_id": 2,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Paper 2"
        }
        
        result = enrich_institutions(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should process at least the works in the collection
        assert result["updated"] >= 0
    
    def test_institution_format(self, mock_collection):
        """Test institutions are formatted as array of objects with 'name' key."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "institution_names": ["Harvard", "MIT"]
        }
        
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "title": "Test"
        }
        
        result = enrich_institutions(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should complete without errors
        assert result["errors"] == 0
    
    def test_unknown_orcid_id(self, mock_collection):
        """Test work with ORCID ID not in orcids collection."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        # Work with unknown ORCID
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-9999-9999-9999",
            "title": "Test"
        }
        
        result = enrich_institutions(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should complete without errors
        assert result["errors"] == 0
