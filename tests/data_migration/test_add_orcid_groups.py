"""
Unit tests for the add_orcid_groups migration and the harvester's group extraction.
"""
from unittest.mock import MagicMock

from src.data_migration.add_orcid_groups import add_orcid_groups, parse_work_groups
from src.works.harvest.WorkHarvester import WorkHarvester

ORCID = "0000-0000-0000-0001"


def summary(put_code, *ids):
    return {"put-code": put_code, "external-ids": {"external-id": [
        {"external-id-type": t, "external-id-value": v, "external-id-relationship": r} for t, v, r in ids
    ]}}


WORKS_JSON = {"group": [
    {"work-summary": [summary(20, ("doi", "10.1/A", "self")), summary(10, ("doi", "10.1/a", "self"))]},
    {"work-summary": [summary(30, ("issn", "1234-5678", "part-of"))]},
]}


class TestParseWorkGroups:
    def test_group_is_named_by_owner_and_smallest_put_code(self):
        groups = parse_work_groups(ORCID, WORKS_JSON)
        assert groups[10]["orcid_group"] == groups[20]["orcid_group"] == f"{ORCID}:10"
        assert groups[30]["orcid_group"] == f"{ORCID}:30"

    def test_relationships_are_keyed_case_insensitively(self):
        groups = parse_work_groups(ORCID, WORKS_JSON)
        assert groups[30]["relationships"] == {("issn", "1234-5678"): "part-of"}

    def test_empty_record(self):
        assert parse_work_groups(ORCID, {"group": []}) == {}


class TestAddOrcidGroups:
    def make_works(self, docs):
        works = MagicMock()
        works.distinct.return_value = [ORCID]
        works.find.return_value = docs
        return works

    def test_sets_group_and_relationships(self):
        works = self.make_works([
            {"_id": 1, "put_code": 10, "external_ids": [{"type": "doi", "value": "10.1/a"}]},
            {"_id": 2, "put_code": 30, "external_ids": [{"type": "issn", "value": "1234-5678"}]},
        ])
        result = add_orcid_groups(works, lambda _: WORKS_JSON)

        ops = works.bulk_write.call_args.args[0]
        sets = {op._filter["_id"]: op._doc["$set"] for op in ops}
        assert sets[1]["orcid_group"] == f"{ORCID}:10"
        assert sets[1]["external_ids"][0]["relationship"] == "self"
        assert sets[2]["external_ids"][0]["relationship"] == "part-of"
        assert result["updated"] == 2
        assert result["status"] == "success"

    def test_unchanged_documents_are_not_written(self):
        works = self.make_works([
            {"_id": 1, "put_code": 30, "orcid_group": f"{ORCID}:30",
             "external_ids": [{"type": "issn", "value": "1234-5678", "relationship": "part-of"}]},
        ])
        result = add_orcid_groups(works, lambda _: WORKS_JSON)
        works.bulk_write.assert_not_called()
        assert result["updated"] == 0

    def test_records_removed_from_orcid_are_counted(self):
        works = self.make_works([{"_id": 1, "put_code": 99, "external_ids": []}])
        result = add_orcid_groups(works, lambda _: WORKS_JSON)
        assert result["not_on_orcid"] == 1

    def test_fetch_failure_is_reported_and_skipped(self):
        def fail(_):
            raise RuntimeError("404")
        works = self.make_works([])
        result = add_orcid_groups(works, fail)
        assert result["failed_authors"] == [ORCID]
        assert result["status"] == "partial"


class TestHarvesterGroups:
    def test_extract_put_codes_returns_orcid_group(self):
        harvester = WorkHarvester(MagicMock(), MagicMock(), MagicMock())
        record = {"activities-summary": {"works": WORKS_JSON}}
        assert harvester.extract_put_codes(record, ORCID) == [
            (20, f"{ORCID}:10"), (10, f"{ORCID}:10"), (30, f"{ORCID}:30"),
        ]

    def test_parse_work_keeps_identifier_relationship(self):
        harvester = WorkHarvester(MagicMock(), MagicMock(), MagicMock())
        work = harvester.parse_work(ORCID, 30, {
            "title": {"title": {"value": "A chapter"}},
            "external-ids": {"external-id": [
                {"external-id-type": "isbn", "external-id-value": "978-1", "external-id-relationship": "part-of"},
            ]},
        })
        assert work.external_ids == [{"type": "isbn", "value": "978-1", "relationship": "part-of"}]
