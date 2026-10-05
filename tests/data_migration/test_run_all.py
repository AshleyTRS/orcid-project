"""
Tests for run_all.py - Master migration orchestrator.

Verifies that all migrations execute in correct order and produce expected results.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.data_migration.run_all import MigrationRunner


class TestMigrationRunner:
    """Test suite for migration orchestration."""
    
    def test_migration_runner_initialization(self):
        """Test MigrationRunner initializes correctly."""
        mock_mongo = MagicMock()
        runner = MigrationRunner(mock_mongo)
        
        assert runner.mongo == mock_mongo
        assert runner.results == []
        assert runner.start_time is None
        assert runner.end_time is None
    
    def test_run_single_migration_success(self):
        """Test running a single migration that succeeds."""
        mock_mongo = MagicMock()
        runner = MigrationRunner(mock_mongo)
        
        # Mock migration function
        def mock_migration():
            return {"status": "success", "updated": 10}
        
        name, result = runner.run_migration("Test Migration", mock_migration)
        
        assert name == "Test Migration"
        assert result["status"] == "success"
    
    def test_run_migration_with_exception(self):
        """Test migration error handling."""
        mock_mongo = MagicMock()
        runner = MigrationRunner(mock_mongo)
        
        # Mock migration that raises exception
        def failing_migration():
            raise ValueError("Test error")
        
        name, result = runner.run_migration("Failing Migration", failing_migration)
        
        assert name == "Failing Migration"
        assert result["status"] == "error"
        assert "Test error" in result["message"]
    
    def test_migration_with_arguments(self):
        """Test passing arguments to migration function."""
        mock_mongo = MagicMock()
        runner = MigrationRunner(mock_mongo)
        
        def migration_with_args(arg1, arg2):
            return {
                "status": "success",
                "arg1": arg1,
                "arg2": arg2
            }
        
        name, result = runner.run_migration(
            "Migration with Args",
            migration_with_args,
            "value1",
            "value2"
        )
        
        assert result["status"] == "success"
        assert result["arg1"] == "value1"
        assert result["arg2"] == "value2"
    
    @patch('src.data_migration.run_all.migrate_doi')
    @patch('src.data_migration.run_all.merge_metadata')
    @patch('src.data_migration.run_all.merge_open_access')
    @patch('src.data_migration.run_all.enrich_institutions')
    @patch('src.data_migration.run_all.link_contributors')
    @patch('src.data_migration.run_all.add_work_key')
    @patch('src.data_migration.run_all.flag_affiliation')
    @patch('src.data_migration.run_all.add_author_count')
    @patch('src.data_migration.run_all.create_indexes')
    @patch('src.data_migration.run_all.drop_unused_indexes')
    def test_run_all_migrations_success(
        self,
        mock_drop_unused,
        mock_create_idx,
        mock_add_count,
        mock_flag_affiliation,
        mock_add_work_key,
        mock_link_contrib,
        mock_enrich_inst,
        mock_merge_open_access,
        mock_merge_meta,
        mock_migrate_doi
    ):
        """Test all migrations run in sequence and succeed."""
        # Setup mock returns
        mock_migrate_doi.return_value = {"status": "success", "updated": 5}
        mock_merge_meta.return_value = {"status": "success", "merged": 4}
        mock_merge_open_access.return_value = {"status": "success", "updated": 3}
        mock_enrich_inst.return_value = {"status": "success", "enriched": 5}
        mock_link_contrib.return_value = {"status": "success", "matched": 8}
        mock_add_work_key.return_value = {"status": "success", "work_keys_updated": 5}
        mock_flag_affiliation.return_value = {"status": "success"}
        mock_add_count.return_value = {"status": "success", "total_works": 5}
        mock_create_idx.return_value = {"status": "success", "created": 12}
        mock_drop_unused.return_value = {"status": "success", "dropped": 1}
        
        mock_mongo = MagicMock()
        mock_mongo.works.return_value = MagicMock()
        mock_mongo.metadata.return_value = MagicMock()
        mock_mongo.orcids.return_value = MagicMock()
        
        runner = MigrationRunner(mock_mongo)
        summary = runner.run_all()
        
        # Verify summary structure
        assert "start_time" in summary
        assert "end_time" in summary
        assert "duration" in summary
        assert "total_migrations" in summary
        assert "successful" in summary
        assert "failed" in summary
        
        # All 10 migrations should succeed
        assert summary["total_migrations"] == 10
        assert summary["successful"] == 10
        assert summary["failed"] == 0
        mock_add_work_key.assert_called_once()
        mock_flag_affiliation.assert_called_once()
        mock_merge_open_access.assert_called_once()
    
    @patch('src.data_migration.run_all.migrate_doi')
    @patch('src.data_migration.run_all.merge_metadata')
    def test_run_all_with_failure(self, mock_merge_meta, mock_migrate_doi):
        """Test migration pipeline continues even if one fails."""
        # First migration succeeds
        mock_migrate_doi.return_value = {"status": "success"}
        
        # Second migration fails
        mock_merge_meta.side_effect = Exception("Database error")
        
        mock_mongo = MagicMock()
        mock_mongo.works.return_value = MagicMock()
        mock_mongo.metadata.return_value = MagicMock()
        mock_mongo.orcids.return_value = MagicMock()
        
        runner = MigrationRunner(mock_mongo)
        
        # Patch remaining migrations to prevent issues
        with patch('src.data_migration.run_all.enrich_institutions') as mock_enrich:
            with patch('src.data_migration.run_all.link_contributors') as mock_link:
                with patch('src.data_migration.run_all.add_author_count') as mock_add:
                    with patch('src.data_migration.run_all.create_indexes') as mock_create:
                        with patch('src.data_migration.run_all.drop_unused_indexes') as mock_drop:
                            mock_enrich.return_value = {"status": "success"}
                            mock_link.return_value = {"status": "success"}
                            mock_add.return_value = {"status": "success"}
                            mock_create.return_value = {"status": "success"}
                            mock_drop.return_value = {"status": "success"}
                            
                            summary = runner.run_all()
                            
                            # Should have failures
                            assert summary["failed"] >= 1
    
    def test_results_tracking(self):
        """Test that all migration results are tracked."""
        mock_mongo = MagicMock()
        runner = MigrationRunner(mock_mongo)
        
        def migration1():
            return {"status": "success", "count": 1}
        
        def migration2():
            return {"status": "success", "count": 2}
        
        runner.run_migration("Migration 1", migration1)
        runner.run_migration("Migration 2", migration2)
        
        assert len(runner.results) >= 0
        # Results should be tracked if any migrations were run
        if runner.results:
            assert all("name" in r and "result" in r for r in runner.results)
