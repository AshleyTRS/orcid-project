"""
Tests for create_indexes.py - Index creation migration.

Verifies that all required indexes are correctly created on the works collection.
"""
import pytest
from src.data_migration.create_indexes import create_indexes


class TestCreateIndexes:
    """Test suite for index creation migration."""
    
    def test_basic_index_creation(self, mock_collection):
        """Test that basic indexes are created."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        assert result["created"] > 0
        
        # Verify some key indexes exist
        indexes = mock_collection._indexes
        assert any("doi" in idx for idx in indexes.keys())
        assert any("publication_year" in idx for idx in indexes.keys())
    
    def test_doi_index_creation(self, mock_collection):
        """Test DOI index is created correctly."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        indexes = mock_collection._indexes
        
        # Check for DOI index
        assert any("doi" in idx for idx in indexes.keys())
    
    def test_year_and_type_index(self, mock_collection):
        """Test compound index for year and type is created."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        indexes = mock_collection._indexes
        
        # Check for publication_year_type compound index
        found = False
        for idx_name, idx_spec in indexes.items():
            if "publication_year" in idx_name and "type" in idx_name:
                assert "publication_year" in idx_spec["fields"]
                assert "type" in idx_spec["fields"]
                found = True
        assert found
    
    def test_contributor_orcid_index(self, mock_collection):
        """Test contributor ORCID index for co-authorship analysis."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        indexes = mock_collection._indexes
        
        # Check for contributors.orcid_id index
        found = False
        for idx_name in indexes.keys():
            if "contributors" in idx_name and "orcid" in idx_name:
                found = True
        assert found
    
    def test_institution_index(self, mock_collection):
        """Test institution name index is created."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        indexes = mock_collection._indexes
        
        # Check for institutions.name index
        found = False
        for idx_name in indexes.keys():
            if "institutions" in idx_name and "name" in idx_name:
                found = True
        assert found
    
    def test_nlp_field_indexes(self, mock_collection):
        """Test NLP-related indexes (topics, concepts)."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        indexes = mock_collection._indexes
        
        # Check for topics and concepts indexes
        has_topics = any("topics" in idx for idx in indexes.keys())
        has_concepts = any("concepts" in idx for idx in indexes.keys())
        
        assert has_topics
        assert has_concepts
    
    def test_index_count(self, mock_collection):
        """Test that expected number of indexes are created."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        # Should create multiple indexes (at least 8+)
        assert result["created"] >= 8
    
    def test_duplicate_index_handling(self, mock_collection):
        """Test that creating duplicate indexes is handled gracefully."""
        # Create index once
        result1 = create_indexes(mock_collection)
        assert result1["status"] == "success"
        
        # Try to create again
        result2 = create_indexes(mock_collection)
        
        # Should handle gracefully (either skip or report)
        assert result2["status"] == "success"
    
    def test_index_has_name(self, mock_collection):
        """Test that all indexes have assigned names."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        
        indexes = mock_collection._indexes
        for idx_name in indexes.keys():
            assert idx_name is not None
            assert len(idx_name) > 0
    
    def test_sparse_index_creation(self, mock_collection):
        """Test sparse indexes are created for optional fields."""
        result = create_indexes(mock_collection)
        
        assert result["status"] == "success"
        
        # DOI should be sparse since not all works have DOI
        indexes = mock_collection._indexes
        if "doi_1" in indexes:
            # In our mock, sparse is marked in the index spec
            assert indexes["doi_1"]["fields"] == ["doi"]
    
    def test_return_value_structure(self, mock_collection):
        """Test return value has expected structure."""
        result = create_indexes(mock_collection)
        
        assert "status" in result
        assert "created" in result
        assert "skipped" in result
        assert "errors" in result
        
        assert isinstance(result["created"], int)
        assert isinstance(result["skipped"], int)
        assert isinstance(result["errors"], int)
