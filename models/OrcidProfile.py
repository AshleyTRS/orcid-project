from dataclasses import dataclass
from typing import List, Optional

@dataclass
class OrcidProfile:
    """Data class to hold ORCID profile information."""
    orcid_id: str
    given_names: Optional[str]
    family_names: Optional[str]
    credit_name: Optional[str]
    other_names: List[str]
    emails: List[str]
    institution_names: List[str]