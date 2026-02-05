from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from typing import List
from .OrcidProfile import OrcidProfile


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
