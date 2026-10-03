"""
Tests for merge_open_access (merge_metadata.py) - open-access status and location.

Uses two independent in-memory collections so that the values written to the
works are verified directly.
"""
from src.data_migration.merge_metadata import merge_open_access


def collections(factory, works, metadata):
    works_collection, metadata_collection = factory(), factory()
    for i, work in enumerate(works, 1):
        works_collection._documents[i] = {"_id": i, **work}
    for i, meta in enumerate(metadata, 1):
        metadata_collection._documents[i] = {"_id": i, **meta}
    return works_collection, metadata_collection


class TestMergeOpenAccess:
    def test_copies_status_and_location(self, mock_collection_factory):
        works, metadata = collections(
            mock_collection_factory,
            [{"doi": "10.1/a"}],
            [{"doi": "10.1/a", "open_access": {"is_oa": True, "oa_url": "https://example.org/a.pdf"}}],
        )
        result = merge_open_access(works, metadata)
        assert result["status"] == "success"
        assert result["updated"] == 1
        assert works._documents[1]["is_oa"] is True
        assert works._documents[1]["oa_url"] == "https://example.org/a.pdf"

    def test_closed_access_sets_status_without_location(self, mock_collection_factory):
        works, metadata = collections(
            mock_collection_factory,
            [{"doi": "10.1/b"}],
            [{"doi": "10.1/b", "open_access": {"is_oa": False, "oa_url": None}}],
        )
        merge_open_access(works, metadata)
        assert works._documents[1]["is_oa"] is False
        assert "oa_url" not in works._documents[1]

    def test_work_without_metadata_is_untouched(self, mock_collection_factory):
        works, metadata = collections(mock_collection_factory, [{"doi": "10.1/c"}], [])
        result = merge_open_access(works, metadata)
        assert result["updated"] == 0
        assert "is_oa" not in works._documents[1]

    def test_repeated_run_writes_nothing(self, mock_collection_factory):
        works, metadata = collections(
            mock_collection_factory,
            [{"doi": "10.1/d"}],
            [{"doi": "10.1/d", "open_access": {"is_oa": True, "oa_url": "https://example.org/d"}}],
        )
        merge_open_access(works, metadata)
        second = merge_open_access(works, metadata)
        assert second["updated"] == 0
        assert second["unchanged"] == 1

    def test_changed_metadata_is_applied(self, mock_collection_factory):
        works, metadata = collections(
            mock_collection_factory,
            [{"doi": "10.1/e", "is_oa": False}],
            [{"doi": "10.1/e", "open_access": {"is_oa": True, "oa_url": "https://example.org/e"}}],
        )
        result = merge_open_access(works, metadata)
        assert result["updated"] == 1
        assert works._documents[1]["is_oa"] is True
