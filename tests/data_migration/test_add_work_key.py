"""
Unit tests for work identity (src/works/work_key.py) and the add_work_key migration.

The key rules are pure functions and are tested directly; the migration is
tested with mocked collections.
"""
from unittest.mock import MagicMock, patch

from src.data_migration.add_work_key import add_work_key
from src.works.work_key import (
    assign_work_keys,
    compute_work_key,
    normalize_doi,
    normalize_title,
    self_ids,
    unique_works_stages,
    work_doi,
)

BASE = {"orcid_id": "0000-0000-0000-0001", "put_code": 1, "publication_year": 2020}


class TestNormalizeDoi:
    def test_strips_resolver_prefix_and_lowercases(self):
        assert normalize_doi("https://doi.org/10.1016/J.Hydromet.2020.105456") == "10.1016/j.hydromet.2020.105456"

    def test_strips_doi_label(self):
        assert normalize_doi("doi: 10.5281/ZENODO.1") == "10.5281/zenodo.1"

    def test_rejects_values_that_are_not_dois(self):
        assert normalize_doi("not a doi") is None
        assert normalize_doi("") is None
        assert normalize_doi(None) is None


class TestNormalizeTitle:
    def test_inline_markup_is_removed_without_splitting_words(self):
        marked = "Silver leaching from miargyrite (AgSbS<inf>2</inf>) in S<inf>2</inf>O<inf>3</inf>"
        plain = "Silver leaching from miargyrite (AgSbS2) in S2O3"
        assert normalize_title(marked) == normalize_title(plain)

    def test_markup_between_words_keeps_word_boundaries(self):
        assert normalize_title("Effect of <i>Bacillus</i> strains") == "effect of bacillus strains"

    def test_accents_case_and_punctuation_are_ignored(self):
        assert normalize_title("LA CUARTA TRANSFORMACIÓN POLÍTICA DE MÉXICO") == \
            normalize_title("La cuarta transformación política de México")

    def test_empty_title(self):
        assert normalize_title(None) == ""


class TestComputeWorkKey:
    def test_duplicate_records_with_same_doi_share_a_key(self):
        first = compute_work_key({**BASE, "put_code": 89260028, "doi": "10.1016/j.hydromet.2020.105456"})
        second = compute_work_key({**BASE, "put_code": 89260068, "doi": "10.1016/J.HYDROMET.2020.105456"})
        assert first == second == "doi:10.1016/j.hydromet.2020.105456"

    def test_doi_is_read_from_external_ids(self):
        doc = {**BASE, "external_ids": [{"type": "doi", "value": "10.1/X"}]}
        assert compute_work_key(doc) == "doi:10.1/x"

    def test_long_titles_match_across_authors(self):
        title = "A long and distinctive research article title about soils"
        assert compute_work_key({**BASE, "orcid_id": "A", "title": title}) == \
            compute_work_key({**BASE, "orcid_id": "B", "title": title})

    def test_short_titles_are_scoped_to_the_record_owner(self):
        assert compute_work_key({**BASE, "orcid_id": "A", "title": "Editorial"}) != \
            compute_work_key({**BASE, "orcid_id": "B", "title": "Editorial"})

    def test_record_without_doi_or_title_is_its_own_work(self):
        assert compute_work_key({**BASE, "title": None, "put_code": 7}) == f"put:{BASE['orcid_id']}:7"


class TestAssignWorkKeys:
    def test_no_doi_duplicate_is_linked_to_the_authors_doi_record(self):
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "put_code": 2, "title": "SOIL CARBON IN FORESTS"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2] == "doi:10.9/abc"

    def test_year_within_tolerance_is_linked(self):
        # online-first vs print year
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Soil carbon in forests", "publication_year": 2021},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2] == "doi:10.9/abc"

    def test_missing_year_is_linked(self):
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Soil carbon in forests", "publication_year": None},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2]

    def test_distant_year_is_not_linked(self):
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Soil carbon in forests", "publication_year": 2022},
        ]
        keys = assign_work_keys(docs)
        assert keys[2] != keys[1]

    def test_linking_never_crosses_authors(self):
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "orcid_id": "other", "put_code": 2, "title": "Soil carbon in forests"},
        ]
        keys = assign_work_keys(docs)
        assert keys[2] != keys[1]

    def test_ambiguous_title_with_two_dois_is_not_linked(self):
        docs = [
            {"_id": 1, **BASE, "title": "Results", "doi": "10.1/a"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Results", "doi": "10.1/b"},
            {"_id": 3, **BASE, "put_code": 3, "title": "Results"},
        ]
        keys = assign_work_keys(docs)
        assert keys[3].startswith("title:")
        assert len(set(keys.values())) == 3

    def test_long_title_links_across_authors(self):
        title = "A long and distinctive research article title about soils"
        docs = [
            {"_id": 1, **BASE, "title": title, "doi": "10.9/abc"},
            {"_id": 2, **BASE, "orcid_id": "other", "put_code": 2, "title": title},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2] == "doi:10.9/abc"

    def test_same_title_with_different_dois_stays_separate(self):
        title = "A long and distinctive research article title about soils"
        docs = [
            {"_id": 1, **BASE, "title": title, "doi": "10.9/preprint"},
            {"_id": 2, **BASE, "put_code": 2, "title": title, "doi": "10.9/article"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]

    def test_orcid_group_links_records_with_similar_titles(self):
        docs = [
            {"_id": 1, **BASE, "title": "Population structure and spatial distribution of cacti", "orcid_group": "g1"},
            {"_id": 2, **BASE, "put_code": 2, "orcid_group": "g1",
             "title": "Population structure and spatial distributions of cactus species"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2]

    def test_orcid_group_with_identical_title_links_distant_years(self):
        docs = [
            {"_id": 1, **BASE, "title": "Un primer paso a la simulacion", "orcid_group": "g1", "publication_year": 2016},
            {"_id": 2, **BASE, "put_code": 2, "title": "Un primer paso a la simulación", "orcid_group": "g1",
             "publication_year": 2019},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2]

    def test_orcid_group_alone_does_not_link_different_titles(self):
        # chapters an author grouped by marking the book's ISBN as their own identifier
        docs = [
            {"_id": 1, **BASE, "title": "Religion y migracion el albergue", "orcid_group": "g1"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Infancia y juventud necesidades", "orcid_group": "g1"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]

    def test_record_listing_many_dois_does_not_link_them(self):
        pasted = [{"type": "doi", "value": f"10.1/{c}", "relationship": "self"} for c in "abc"]
        docs = [
            {"_id": 1, **BASE, "title": "The social conditions of preeclampsia", "external_ids": pasted},
            {"_id": 2, **BASE, "put_code": 2, "title": "Cortisol as a predictor", "doi": "10.1/a"},
            {"_id": 3, **BASE, "put_code": 3, "title": "Breastfeeding and diarrhoea", "doi": "10.1/b"},
        ]
        keys = assign_work_keys(docs)
        assert len(set(keys.values())) == 3

    def test_shared_scopus_id_links_records_across_authors(self):
        eid = [{"type": "eid", "value": "2-s2.0-1", "relationship": "self"}]
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon", "external_ids": eid},
            {"_id": 2, **BASE, "orcid_id": "other", "put_code": 2, "title": "Soil carbon!", "external_ids": eid},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2]

    def test_part_of_identifiers_never_link(self):
        book = [{"type": "doi", "value": "10.1/book", "relationship": "part-of"},
                {"type": "isbn", "value": "978-1", "relationship": "part-of"}]
        docs = [
            {"_id": 1, **BASE, "title": "Chapter one on silver recovery", "external_ids": book},
            {"_id": 2, **BASE, "put_code": 2, "title": "Chapter two on silver leaching", "external_ids": book},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]
        assert not keys[1].startswith("doi:")

    def test_typo_level_title_difference_is_linked(self):
        docs = [
            {"_id": 1, **BASE, "title": "Presencia de Spauligodon sp. en algunas especies de Sceloporus"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Presencia de Spauligodon sp en algunas species de Sceloporus"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] == keys[2]

    def test_titles_differing_in_numbers_stay_separate(self):
        docs = [
            {"_id": 1, **BASE, "title": "Gestion del conocimiento perspectiva multidisciplinaria volumen 41"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Gestion del conocimiento perspectiva multidisciplinaria volumen 34"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]

    def test_titles_differing_in_roman_numerals_stay_separate(self):
        docs = [
            {"_id": 1, **BASE, "title": "Las comunidades indigenas en Hidalgo Zimapan vol II"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Las comunidades indigenas en Hidalgo Zimapan vol III"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]

    def test_typo_link_never_crosses_authors(self):
        docs = [
            {"_id": 1, **BASE, "title": "Presencia de Spauligodon sp. en algunas especies de Sceloporus"},
            {"_id": 2, **BASE, "orcid_id": "other", "put_code": 2,
             "title": "Presencia de Spauligodon sp en algunas species de Sceloporus"},
        ]
        keys = assign_work_keys(docs)
        assert keys[1] != keys[2]

    def test_keys_do_not_depend_on_input_order(self):
        docs = [
            {"_id": 1, **BASE, "title": "Soil carbon in forests", "doi": "10.9/abc"},
            {"_id": 2, **BASE, "put_code": 2, "title": "Soil carbon in forests", "publication_year": None},
            {"_id": 3, **BASE, "put_code": 3, "title": "Another work entirely"},
        ]
        assert assign_work_keys(docs) == assign_work_keys(list(reversed(docs)))


class TestSelfIds:
    def test_relationship_missing_counts_as_self(self):
        doc = {"external_ids": [{"type": "doi", "value": "10.1/A"}]}
        assert self_ids(doc) == {("doi", "10.1/a")}

    def test_weak_and_part_of_identifiers_are_ignored(self):
        doc = {"external_ids": [
            {"type": "issn", "value": "1234-5678", "relationship": "part-of"},
            {"type": "doi", "value": "10.1/book", "relationship": "part-of"},
            {"type": "eid", "value": "2-s2.0-9", "relationship": "self"},
        ]}
        assert self_ids(doc) == {("eid", "2-s2.0-9")}
        assert work_doi(doc) is None


class TestUniqueWorksStages:
    def test_groups_by_work_key(self):
        stages = unique_works_stages()
        assert stages[0]["$group"]["_id"] == "$work_key"
        assert stages[1] == {"$replaceRoot": {"newRoot": "$doc"}}

    def test_per_author_groups_by_owner_and_key(self):
        stages = unique_works_stages(per_author=True, fields={"orcid_id": 1, "work_key": 1})
        assert stages[0] == {"$project": {"orcid_id": 1, "work_key": 1}}
        assert stages[1]["$group"]["_id"] == {"author": "$orcid_id", "key": "$work_key"}


class TestAddWorkKeyMigration:
    @patch("src.data_migration.add_work_key.update_unique_works_counts")
    @patch("src.data_migration.add_work_key.apply_work_keys")
    def test_success_reports_counts_and_creates_indexes(self, mock_apply, mock_counts):
        mock_apply.return_value = {"documents": 10, "updated": 4}
        mock_counts.return_value = {"authors": 3, "updated": 2}
        works, orcids = MagicMock(), MagicMock()
        works.distinct.return_value = ["doi:10.1/a"] * 7

        result = add_work_key(works, orcids)

        assert result["status"] == "success"
        assert result["work_keys_updated"] == 4
        assert result["distinct_works"] == 7
        assert result["duplicate_documents"] == 3
        assert result["unique_works_counts_updated"] == 2
        created = [c.args[0] for c in works.create_index.call_args_list]
        assert [("work_key", 1)] in created
        assert [("orcid_id", 1), ("work_key", 1)] in created
        orcids.create_index.assert_called_once_with([("unique_works_count", -1), ("orcid_id", 1)])

    @patch("src.data_migration.add_work_key.apply_work_keys", side_effect=RuntimeError("connection lost"))
    def test_failure_returns_error_status(self, _mock_apply):
        result = add_work_key(MagicMock(), MagicMock())
        assert result == {"status": "error", "message": "connection lost"}
