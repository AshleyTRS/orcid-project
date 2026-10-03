"""
Tests for link_contributors.py - Contributor linking migration.

Verifies that contributors are matched with ORCID profiles by normalized name,
that both sides of the comparison are normalized identically (accents and
hyphens included), that ambiguous names are skipped and that existing links
are preserved. Linking is checked on the stored documents, not only on the
returned counts.
"""
from src.data_migration.link_contributors import (
    build_name_index,
    link_contributors,
    normalize_name,
    plan_contributor_links,
)

JOHN = {"orcid_id": "0000-0001-1111-1111", "given_names": "John", "family_names": "Smith"}
JANE = {"orcid_id": "0000-0002-2222-2222", "given_names": "Jane", "family_names": "Doe"}


def collections(factory, profiles, works):
    """Two independent in-memory collections filled with the given documents."""
    orcids, works_collection = factory(), factory()
    for i, profile in enumerate(profiles, 1):
        orcids._documents[i] = {"_id": i, **profile}
    for i, work in enumerate(works, 1):
        works_collection._documents[i] = {"_id": i, **work}
    return orcids, works_collection


def linked_ids(works_collection, work_id=1):
    return [c.get("orcid_id") for c in works_collection._documents[work_id]["contributors"]]


class TestNormalizeName:
    """Name normalization shared with the works harvester."""

    def test_basic_normalization(self):
        assert normalize_name("John Smith") == "john smith"
        assert normalize_name("JANE DOE") == "jane doe"

    def test_hyphens_become_spaces(self):
        assert normalize_name("Jane Doe-Anderson") == "jane doe anderson"
        assert normalize_name("Mary-Jane Smith-Brown") == "mary jane smith brown"

    def test_accents_are_removed(self):
        assert normalize_name("María-José García") == "maria jose garcia"
        assert normalize_name("Bernardo Angeles Santillán") == "bernardo angeles santillan"

    def test_whitespace_normalization(self):
        assert normalize_name("  John   Smith  ") == "john smith"
        assert normalize_name("Jane\t\tDoe") == "jane doe"

    def test_empty_and_none_values(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""
        assert normalize_name("   ") == ""

    def test_profile_and_contributor_forms_agree(self):
        """Regression: both sides of the comparison must produce the same string."""
        profile_side = normalize_name("Bernardo Angeles Santillán")
        contributor_side = normalize_name(normalize_name("Bernardo Angeles Santillán"))
        assert profile_side == contributor_side


class TestBuildNameIndex:
    def test_maps_unique_names(self):
        index, ambiguous = build_name_index([JOHN, JANE])
        assert index == {"john smith": JOHN["orcid_id"], "jane doe": JANE["orcid_id"]}
        assert ambiguous == set()

    def test_shared_names_are_ambiguous_and_excluded(self):
        twin = {**JOHN, "orcid_id": "0000-0009-9999-9999"}
        index, ambiguous = build_name_index([JOHN, twin, JANE])
        assert "john smith" not in index
        assert ambiguous == {"john smith"}

    def test_null_name_fields_are_tolerated(self):
        index, _ = build_name_index([{"orcid_id": "0000-0003-3333-3333", "given_names": None, "family_names": "Prince"}])
        assert index == {"prince": "0000-0003-3333-3333"}


class TestPlanContributorLinks:
    def test_existing_link_is_never_overwritten(self):
        works = [{"_id": 1, "contributors": [{"normalized_name": "john smith", "orcid_id": "0000-0008-8888-8888"}]}]
        links, stats = plan_contributor_links(works, {"john smith": JOHN["orcid_id"]})
        assert links == {}
        assert stats["already_linked"] == 1

    def test_credit_name_is_used_when_normalized_name_is_missing(self):
        works = [{"_id": 1, "contributors": [{"credit_name": "John Smith"}]}]
        links, _ = plan_contributor_links(works, {"john smith": JOHN["orcid_id"]})
        assert links == {1: {0: JOHN["orcid_id"]}}


class TestLinkContributors:
    def test_basic_contributor_linking(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN],
                                    [{"contributors": [{"normalized_name": "john smith"}]}])
        result = link_contributors(works, orcids)
        assert result["status"] == "success"
        assert result["matched_contributors"] == 1
        assert linked_ids(works) == [JOHN["orcid_id"]]

    def test_case_insensitive_matching(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [{**JANE, "given_names": "jane", "family_names": "doe"}],
                                    [{"contributors": [{"normalized_name": "JANE DOE"}]}])
        link_contributors(works, orcids)
        assert linked_ids(works) == [JANE["orcid_id"]]

    def test_accented_and_hyphenated_names_match(self, mock_collection_factory):
        """Regression for the defect fixed in October 2026."""
        profile = {"orcid_id": "0000-0004-4444-4444", "given_names": "María José", "family_names": "García-López"}
        # contributor names are stored as the harvester normalizes them
        orcids, works = collections(mock_collection_factory, [profile],
                                    [{"contributors": [{"credit_name": "María José García-López",
                                                        "normalized_name": "maria jose garcia lopez"}]}])
        result = link_contributors(works, orcids)
        assert result["matched_contributors"] == 1
        assert linked_ids(works) == ["0000-0004-4444-4444"]

    def test_ambiguous_name_is_not_linked(self, mock_collection_factory):
        twin = {**JOHN, "orcid_id": "0000-0009-9999-9999"}
        orcids, works = collections(mock_collection_factory, [JOHN, twin],
                                    [{"contributors": [{"normalized_name": "john smith"}]}])
        result = link_contributors(works, orcids)
        assert result["ambiguous_names"] == 1
        assert linked_ids(works) == [None]

    def test_no_matching_contributor(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN],
                                    [{"contributors": [{"normalized_name": "unknown author"}]}])
        link_contributors(works, orcids)
        assert "orcid_id" not in works._documents[1]["contributors"][0]

    def test_multiple_contributors(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN, JANE],
                                    [{"contributors": [{"normalized_name": "john smith"},
                                                       {"normalized_name": "jane doe"},
                                                       {"normalized_name": "unknown author"}]}])
        result = link_contributors(works, orcids)
        assert result["total_contributors"] == 3
        assert result["matched_contributors"] == 2
        assert result["works_updated"] == 1
        assert linked_ids(works) == [JOHN["orcid_id"], JANE["orcid_id"], None]

    def test_existing_links_are_preserved(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN],
                                    [{"contributors": [{"normalized_name": "john smith", "orcid_id": "0000-0008-8888-8888"}]}])
        result = link_contributors(works, orcids)
        assert result["already_linked"] == 1
        assert linked_ids(works) == ["0000-0008-8888-8888"]

    def test_repeated_run_changes_nothing(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN],
                                    [{"contributors": [{"normalized_name": "john smith"}]}])
        link_contributors(works, orcids)
        second = link_contributors(works, orcids)
        assert second["matched_contributors"] == 0
        assert second["works_updated"] == 0

    def test_empty_contributors_array(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN], [{"contributors": []}])
        result = link_contributors(works, orcids)
        assert result["status"] == "success"
        assert result["matched_contributors"] == 0

    def test_missing_contributors_field(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN], [{"title": "Test Paper"}])
        result = link_contributors(works, orcids)
        assert result["status"] == "success"
        assert "contributors" not in works._documents[1]

    def test_partial_name_no_match(self, mock_collection_factory):
        orcids, works = collections(mock_collection_factory, [JOHN],
                                    [{"contributors": [{"normalized_name": "john"}]}])
        link_contributors(works, orcids)
        assert "orcid_id" not in works._documents[1]["contributors"][0]
