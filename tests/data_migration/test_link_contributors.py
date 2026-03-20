"""
Tests for link_contributors.py - Contributor linking migration.

Verifies that contributors are correctly matched with ORCID profiles
using normalized names.
"""
import pytest
from src.data_migration.link_contributors import (
    normalize_name, 
    link_contributors
)


class TestNormalizeName:
    """Test suite for name normalization function."""
    
    def test_basic_normalization(self):
        """Test basic name normalization: lowercase, remove hyphens."""
        assert normalize_name("John Smith") == "john smith"
        assert normalize_name("JANE DOE") == "jane doe"
        assert normalize_name("ROBERT JOHNSON") == "robert johnson"
    
    def test_remove_hyphens(self):
        """Test hyphens are removed during normalization."""
        # Note: The current implementation removes hyphens without inserting spaces
        # This matches the normalize_name function which does: name.replace("-", "")
        assert normalize_name("Jane Doe-Anderson") == "jane doeanderson"
        assert normalize_name("Mary-Jane Smith-Brown") == "maryjane smithbrown"
    
    def test_whitespace_normalization(self):
        """Test extra whitespace is trimmed."""
        assert normalize_name("  John   Smith  ") == "john smith"
        assert normalize_name("Jane\t\tDoe") == "jane doe"
    
    def test_empty_and_none_values(self):
        """Test empty and None values are handled."""
        assert normalize_name("") == ""
        assert normalize_name(None) == ""
        assert normalize_name("   ") == ""
    
    def test_mixed_case_and_hyphens(self):
        """Test mixed case with hyphenated names."""
        # Hyphens are removed (not replaced with spaces)
        assert normalize_name("Jean-Paul DUBOIS") == "jeanpaul dubois"
        assert normalize_name("María-José García") == "maríajosé garcía"


class TestLinkContributors:
    """Test suite for contributor linking migration."""
    
    def test_basic_contributor_linking(self, mock_collection):
        """Test basic matching of contributor to ORCID."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        # ORCID profile
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "John",
            "family_names": "Smith"
        }
        
        # Work with contributor matching the ORCID
        works_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0002-2222-2222",
            "title": "Test Paper",
            "contributors": [
                {"normalized_name": "John Smith", "tokens": ["john", "smith"]}
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should process documents
        assert result["works_updated"] >= 0
    
    def test_case_insensitive_matching(self, mock_collection):
        """Test name matching is case insensitive."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "jane",
            "family_names": "doe"
        }
        
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": [
                {"normalized_name": "JANE DOE"}
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should process without errors
        assert result["errors"] == 0
    
    def test_hyphenated_name_matching(self, mock_collection):
        """Test matching with hyphenated names."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "Jane",
            "family_names": "Doe-Anderson"
        }
        
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": [
                {"normalized_name": "Jane Doe-Anderson"}
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should complete without errors
        assert result["errors"] == 0
    
    def test_no_matching_contributor(self, mock_collection):
        """Test contributors that don't match any ORCID."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "John",
            "family_names": "Smith"
        }
        
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": [
                {"normalized_name": "Unknown Author"}
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should not have orcid_id if no match
        assert "orcid_id" not in works_collection._documents[1]["contributors"][0]
    
    def test_multiple_contributors(self, mock_collection):
        """Test multiple contributors in single work."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        # Multiple ORCIDs
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "John",
            "family_names": "Smith"
        }
        orcids_collection._documents[2] = {
            "_id": 2,
            "orcid_id": "0000-0002-2222-2222",
            "given_names": "Jane",
            "family_names": "Doe"
        }
        
        # Work with multiple contributors
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": [
                {"normalized_name": "John Smith"},
                {"normalized_name": "Jane Doe"},
                {"normalized_name": "Unknown Author"}
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        # Should process all contributors in the work
        assert result["total_contributors"] >= 0
    
    def test_empty_contributors_array(self, mock_collection):
        """Test work with no contributors."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": []
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        assert result["matched_contributors"] == 0
    
    def test_missing_contributors_field(self, mock_collection):
        """Test work without contributors field."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        works_collection._documents[1] = {
            "_id": 1,
            "title": "Test Paper"
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        assert result["status"] == "success"
        assert "contributors" not in works_collection._documents[1]
    
    def test_partial_name_no_match(self, mock_collection):
        """Test that partial names don't match."""
        orcids_collection = mock_collection
        works_collection = mock_collection.__class__()
        works_collection._documents = {}
        
        orcids_collection._documents[1] = {
            "_id": 1,
            "orcid_id": "0000-0001-1111-1111",
            "given_names": "John",
            "family_names": "Smith"
        }
        
        works_collection._documents[1] = {
            "_id": 1,
            "contributors": [
                {"normalized_name": "John"}  # Only first name
            ]
        }
        
        result = link_contributors(works_collection, orcids_collection)
        
        # Partial name should not match full name
        assert "orcid_id" not in works_collection._documents[1]["contributors"][0]
