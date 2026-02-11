"""
Docstring for harvest_works_models.Work
Dataclass to normalize data before inserting document into mongo collection.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Work:
    orcid_id: str
    put_code: int
    title: Optional[str]
    journal_title: Optional[str]
    publication_year: Optional[int]
    work_type: Optional[str]
    external_ids: List[Dict]  # like DOI
    visibility: Optional[str]

    def to_dict(self) -> dict:
        return {
            "orcid_id": self.orcid_id,
            "put_code": self.put_code,
            "title": self.title,
            "journal_title": self.journal_title,
            "publication_year": self.publication_year,
            "type": self.work_type,
            "external_ids": self.external_ids,
            "visibility": self.visibility
        }