"""
Unit tests for src/coauthorship/constellation.py with an in-memory stand-in for MongoDB.
"""
from unittest.mock import patch

from src.coauthorship.constellation import _component, get_constellation

A, B, C, D, E = (f"0000-0000-0000-000{i}" for i in range(1, 6))


class FakeCursor(list):
    def limit(self, _):
        return self


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        wanted = set(query["orcid_id"]["$in"])
        return FakeCursor(d for d in self.docs if d["orcid_id"] in wanted)

    def aggregate(self, pipeline, allowDiskUse=False):
        match = pipeline[0]["$match"]
        if "work_key" in match:  # metadata lookups
            keys = set(match["work_key"]["$in"])
            docs = [d for d in self.docs if d["work_key"] in keys]
            if "$facet" in pipeline[-1]:
                return iter([{"topics": [], "types": [{"_id": "journal-article", "count": len({d["work_key"] for d in docs})}]}])
            grouped = {}
            for d in docs:
                grouped.setdefault(d["work_key"], {**d, "_id": d["work_key"], "credits": [d.get("contributors")],
                                                    "topics": [t["display_name"] for t in d.get("topics", [])]})
            return iter(grouped.values())
        return iter(self.docs)  # network pass: filters are applied by build_works_match in the real DB


class FakeDB:
    def __init__(self, works, orcids):
        self.works = FakeCollection(works)
        self.orcids = FakeCollection(orcids)


def work(key, owner, year, *coauthors, topics=()):
    return {"work_key": key, "orcid_id": owner, "publication_year": year, "title": key, "type": "journal-article",
            "contributors": [{"orcid_id": c, "credit_name": f"Name {c[-1]}"} for c in coauthors],
            "topics": [{"display_name": t} for t in topics]}


WORKS = [
    work("w1", A, 2021, B, topics=["Soils"]),
    work("w2", B, 2022, C, topics=["Soils", "Water"]),
    work("w3", A, 2023, B, topics=["Water"]),
    work("w4", D, 2020, E),          # a separate constellation
    work("w5", A, 2024),             # A on their own
]
ORCIDS = [
    {"orcid_id": A, "given_names": "Ana", "family_names": "Alvarez", "institution_names": ["UAEH"], "uaeh_affiliated": True},
    # Harvested but not affiliated with UAEH: named, but has no author page
    {"orcid_id": B, "given_names": "Bea", "family_names": "Bravo", "institution_names": ["UNAM"], "uaeh_affiliated": False},
]


def constellation(orcid):
    with patch("src.coauthorship.constellation.build_works_match", return_value={}):
        return get_constellation(FakeDB(WORKS, ORCIDS), orcid, 2020, 2026)


class TestComponent:
    def test_reaches_co_authors_of_co_authors(self):
        authors = {"w1": {A, B}, "w2": {B, C}, "w4": {D, E}}
        assert _component(A, authors) == {A, B, C}

    def test_researcher_without_co_authors_is_alone(self):
        assert _component(A, {"w5": {A}}) == {A}


class TestGetConstellation:
    def test_members_pairs_and_shared_works(self):
        result = constellation(A)
        assert {m["orcid_id"] for m in result["members"]} == {A, B, C}
        assert result["stats"] == {"members": 3, "links": 2, "shared_works": 3, "collaborations": 3,
                                   "first_year": 2021, "last_year": 2023}
        strongest = result["pairs"][0]
        assert (strongest["source"], strongest["target"], strongest["weight"]) == (A, B, 2)
        assert strongest["first_year"] == 2021 and strongest["last_year"] == 2023
        assert [w["key"] for w in result["works"]] == ["w3", "w2", "w1"]  # newest first; solo work w5 excluded

    def test_member_counts_and_names(self):
        members = {m["orcid_id"]: m for m in constellation(A)["members"]}
        assert members[A]["name"] == "Ana Alvarez" and members[A]["in_dataset"]
        assert (members[A]["works"], members[A]["shared_works"], members[A]["collaborators"]) == (3, 2, 1)
        assert members[B]["name"] == "Bea Bravo" and not members[B]["in_dataset"]
        # Not harvested: named after how they are credited on works
        assert members[C]["name"] == "Name 3" and not members[C]["in_dataset"]

    def test_focus_member_is_listed_first(self):
        assert constellation(B)["members"][0]["orcid_id"] == B

    def test_unknown_researcher_returns_none(self):
        assert constellation("0000-0000-0000-0009") is None
