"""
Unit tests for src/orcid/affiliation.py and the flag_affiliation migration.
"""
from unittest.mock import MagicMock

from src.data_migration.flag_affiliation import flag_affiliation, verify_unmatched_authors
from src.orcid.affiliation import (
    flag_affiliated_authors,
    flag_uaeh_works,
    is_uaeh_affiliated,
    is_uaeh_institution,
    uaeh_institutions_from_activities,
)


class TestIsUaehInstitution:
    def test_spellings_found_in_the_data(self):
        for name in [
            "Universidad Autónoma del Estado de Hidalgo",
            "UNIVERSIDAD AUTÓNOMA DEL ESTADO DE HIDALGO, Instituto de Ciencias de la Salud",
            "Universida Autonoma del Estado de Hidalgo",
            "Universidad Autonoma Estado Hidalgo",
            "Universidad Autónoma de Hidalgo",
            "Autonomous University of Hidalgo State",
            "Instituto de Ciencias Básicas e Ingeniería, Universidad Autónoma del Estado de Hidalgo",
            "UAEH",
        ]:
            assert is_uaeh_institution(name), name

    def test_other_hidalgo_institutions_do_not_count(self):
        for name in [
            "Universidad Michoacana de San Nicolás de Hidalgo",
            "El Colegio del Estado de Hidalgo",
            "Universidad Politécnica Metropolitana de Hidalgo",
            "Tecnológico de Monterrey Campus Hidalgo",
            "Servicios de Salud de Hidalgo",
            "Centro de Investigación y de Estudios Avanzados del Instituto Politécnico Nacional",
        ]:
            assert not is_uaeh_institution(name), name

    def test_any_institution_is_enough(self):
        assert is_uaeh_affiliated(["UNAM", "Universidad Autónoma del Estado de Hidalgo"])
        assert not is_uaeh_affiliated([])
        assert not is_uaeh_affiliated(None)


def collection(docs, distinct=None):
    coll = MagicMock()
    coll.find.return_value = docs
    coll.distinct.return_value = distinct or []
    return coll


def written(coll):
    ops = [op for call in coll.bulk_write.call_args_list for op in call.args[0]]
    return {op._filter["_id"]: op._doc["$set"] for op in ops}


class TestFlagAffiliatedAuthors:
    def test_sets_flag_only_where_it_changes(self):
        orcids = collection([
            {"_id": 1, "institution_names": ["UAEH"]},
            {"_id": 2, "institution_names": ["CINVESTAV"]},
            {"_id": 3, "institution_names": [], "uaeh_affiliated": False},
        ])
        result = flag_affiliated_authors(orcids)
        assert written(orcids) == {1: {"uaeh_affiliated": True}, 2: {"uaeh_affiliated": False}}
        assert result == {"authors": 3, "affiliated": 1, "updated": 2}


class TestFlagUaehWorks:
    def test_a_uaeh_owner_or_contributor_on_any_record_marks_the_whole_work(self):
        works = collection([
            {"_id": 1, "work_key": "doi:a", "orcid_id": "OUT", "contributors": []},
            {"_id": 2, "work_key": "doi:a", "orcid_id": "IN", "contributors": []},
            {"_id": 3, "work_key": "doi:b", "orcid_id": "OUT", "contributors": [{"orcid_id": "IN"}]},
            {"_id": 4, "work_key": "doi:c", "orcid_id": "OUT", "contributors": [{"orcid_id": "OTHER"}]},
        ])
        orcids = collection([], distinct=["IN"])
        result = flag_uaeh_works(works, orcids)
        assert written(works) == {1: {"uaeh_work": True}, 2: {"uaeh_work": True},
                                  3: {"uaeh_work": True}, 4: {"uaeh_work": False}}
        assert result["uaeh_documents"] == 3


ACTIVITIES = {
    "employments": {"affiliation-group": [{"summaries": [{"employment-summary": {
        "organization": {"name": "Universidad Autónoma del Estado de Hidalgo"}, "department-name": "ICBI"}}]}]},
    "educations": {"affiliation-group": [{"summaries": [{"education-summary": {
        "organization": {"name": "UNAM"}}}]}]},
}


class TestLiveCheck:
    def test_extracts_uaeh_organisations(self):
        assert uaeh_institutions_from_activities(ACTIVITIES) == ["Universidad Autónoma del Estado de Hidalgo, ICBI"]

    def test_adds_uaeh_institutions_of_unmatched_authors(self):
        orcids = collection([
            {"_id": 1, "orcid_id": "A", "institution_names": []},
            {"_id": 2, "orcid_id": "B", "institution_names": ["UAEH"]},
        ])
        result = verify_unmatched_authors(orcids, lambda orcid: ACTIVITIES)
        assert result == {"checked": 1, "found": 1, "failed": []}
        orcids.update_one.assert_called_once_with(
            {"_id": 1}, {"$addToSet": {"institution_names": {"$each": ["Universidad Autónoma del Estado de Hidalgo, ICBI"]}}})

    def test_migration_reports_error_status(self):
        works, orcids = MagicMock(), MagicMock()
        orcids.find.side_effect = RuntimeError("connection lost")
        assert flag_affiliation(works, orcids) == {"status": "error", "message": "connection lost"}
