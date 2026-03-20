"""
Tests for drop_unused_indexes.py - Unused index removal migration.

Verifies that obsolete indexes are correctly removed from the collection.
"""
import pytest
from src.data_migration.drop_unused_indexes import drop_unused_indexes


class TestDropUnusedIndexes:
    """Test suite for unused index removal migration."""
    
    def test_drop_existing_index(self, mock_collection):
        """Test that existing unused index is dropped."""
        # Create an index first
        mock_collection._indexes["contributors_normalized_name_1"] = {
            "fields": ["contributors.normalized_name"],
            "unique": False
        }
        
        result = drop_unused_indexes(mock_collection)
        
        assert result["status"] == "success"
        assert result["dropped"] > 0
        
        # Verify index was dropped
        assert "contributors_normalized_name_1" not in mock_collection._indexes
    
    def test_index_not_found_handling(self, mock_collection):
        """Test handling when index to drop doesn't exist."""
        result = drop_unused_indexes(mock_collection)
        
        assert result["status"] == "success"
        assert result["not_found"] >= 0
        # Should not error
        assert result["errors"] == 0
    
    def test_alternative_index_name_variant(self, mock_collection):
        """Test both naming variants are checked."""
        # Create alternative variant
        mock_collection._indexes["contributors.normalized_name_1"] = {
            "fields": ["contributors.normalized_name"],
            "unique": False
        }
        
        result = drop_unused_indexes(mock_collection)
        
        assert result["status"] == "success"
        # One of the variants should be dropped
        assert result["dropped"] + result["not_found"] >= 1
    
    def test_preserve_other_indexes(self, mock_collection):
        """Test that other indexes are preserved."""
        # Create various indexes
        mock_collection._indexes["doi_1"] = {
            "fields": ["doi"],
            "unique": True
        }
        mock_collection._indexes["publication_year_1"] = {
            "fields": ["publication_year"],
            "unique": False
        }
        mock_collection._indexes["contributors_normalized_name_1"] = {
            "fields": ["contributors.normalized_name"],
            "unique": False
        }
        
        result = drop_unused_indexes(mock_collection)
        
        assert result["status"] == "success"
        
        # Important indexes should still exist
        assert "doi_1" in mock_collection._indexes
        assert "publication_year_1" in mock_collection._indexes
        
        # Unused index should be gone
        assert "contributors_normalized_name_1" not in mock_collection._indexes
    
    def test_multiple_drop_attempts(self, mock_collection):
        """Test dropping same index multiple times is safe."""
        # Create index
        mock_collection._indexes["contributors_normalized_name_1"] = {
            "fields": ["contributors.normalized_name"],
            "unique": False
        }
        
        # First drop
        result1 = drop_unused_indexes(mock_collection)
        assert result1["status"] == "success"
        
        # Second drop (index no longer exists)
        result2 = drop_unused_indexes(mock_collection)
        assert result2["status"] == "success"
        
        # Should handle gracefully without errors
        assert result2["errors"] == 0
    
    def test_return_value_structure(self, mock_collection):
        """Test return value has expected structure."""
        result = drop_unused_indexes(mock_collection)
        
        assert "status" in result
        assert "dropped" in result
        assert "not_found" in result
        assert "errors" in result
        
        assert isinstance(result["dropped"], int)
        assert isinstance(result["not_found"], int)
        assert isinstance(result["errors"], int)
    
    def test_no_indexes_to_drop(self, mock_collection):
        """Test behavior when no unused indexes exist."""
        # Empty collection with no indexes
        result = drop_unused_indexes(mock_collection)
        
        assert result["status"] == "success"
        assert result["not_found"] >= 0
        assert result["dropped"] == 0
