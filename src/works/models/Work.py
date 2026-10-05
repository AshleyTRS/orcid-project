from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Work:
    orcid_id: str
    put_code: int
    title: Optional[str]
    journal_title: Optional[str]
    publication_year: Optional[int]
    work_type: Optional[str]
    external_ids: List[Dict]
    contributors: List[Dict] = field(default_factory=list)
    visibility: Optional[str] = None
    # Identity shared by duplicate records of the same work (src/works/work_key.py)
    work_key: Optional[str] = None
    # ORCID's group of this author's entries for the same work (src/works/work_key.py)
    orcid_group: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "orcid_id": self.orcid_id,
            "put_code": self.put_code,
            "title": self.title,
            "journal_title": self.journal_title,
            "publication_year": self.publication_year,
            "type": self.work_type,
            "external_ids": self.external_ids,
            "contributors": self.contributors,
            "visibility": self.visibility,
            "work_key": self.work_key,
            "orcid_group": self.orcid_group
        }
