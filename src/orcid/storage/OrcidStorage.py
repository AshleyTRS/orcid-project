from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from typing import List
from ..models.OrcidProfile import OrcidProfile


class OrcidStorage:
    def __init__(self, collection):
        self.collection = collection
        self.collection.create_index("orcid_id", unique=True) # no duplicate orcids are saved
        self.collection.create_index("harvested")

    def save_orcids(self, profiles: List[OrcidProfile]):
        for profile in profiles:
            try:
                self.collection.insert_one({
                    "orcid_id": profile.orcid_id,
                    "given_names": profile.given_names,
                    "family_names": profile.family_names,
                    "credit_name": profile.credit_name,
                    "other_names": profile.other_names,
                    "emails": profile.emails,
                    "institution_names": profile.institution_names,
                    "discovered_at": datetime.now(timezone.utc),
                    "harvested": False
                })
            except DuplicateKeyError:
                pass  # already stored
    
    def find_unharvested(self, limit=None):
        cursor = self.collection.find(
            {"harvested": False},
            {"orcid_id": 1}
        )
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)


    def mark_harvested(self, orcid_id: str, works_count: int, harvested_at):
        self.collection.update_one(
            {"orcid_id": orcid_id},
            {
                "$set": {
                    "harvested": True,
                    "works_harvested_at": harvested_at,
                    "works_count": works_count
                }
            }
        )