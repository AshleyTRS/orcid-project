"""
Docstring for harvest_works_models.WorkStorage
Handles persistence of ORCID works.
"""
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from typing import List


class WorkStorage:
    def __init__(self, collection):
        self.collection = collection
        self.collection.create_index(
            [("orcid_id", 1), ("put_code", 1)],
            unique=True
        ) # create index to ensure uniqueness

    """
    This function inserts work into MongoDB. If work is successfully inserted, then it return True.
    A False is returned if work is a duplicate key.
    """
    def insert(self, work: dict) -> bool:
        try:
            work["harvested_at"] = datetime.now(timezone.utc)
            self.collection.insert_one(work)
            return True
        except DuplicateKeyError:
            return False

    def count_by_orcid(self, orcid_id: str) -> int:
        return self.collection.count_documents({"orcid_id": orcid_id})

    def find_by_orcid(self, orcid_id: str) -> List[dict]:
        return list(
            self.collection.find(
                {"orcid_id": orcid_id},
                {"_id": 0}
            )
        )
