"""
Docstring for harvest_works_models.WorkHarvester
Harvests works for discovered ORCID profiles.
"""

import time
from datetime import datetime, timezone
from .Work import Work
from .WorkStorage import WorkStorage
from search_models.OrcidSearchClient import OrcidSearchClient
from search_models.OrcidStorage import OrcidStorage
import unicodedata

class WorkHarvester:
    def __init__(
        self,
        client : OrcidSearchClient,
        orcid_storage : OrcidStorage,
        work_storage : WorkStorage,
        rate_limit_delay: float = 0.1
    ):
        self.client = client
        self.orcid_storage = orcid_storage
        self.work_storage = work_storage
        self.rate_limit_delay = rate_limit_delay

    # ------------------------------------
    # Harvest works for ORCIDs saved
    # ------------------------------------

    """
    Harvest works for all ORCIDs not yet harvested.
    """
    def harvest_all(self, limit: int | None = None):
        orcids = self.orcid_storage.find_unharvested(limit)

        for orcid in orcids:
            try:
                self.harvest_orcid(orcid["orcid_id"])
            except Exception as e:
                print(f"[ERROR] {orcid['orcid_id']}: {e}")

    def harvest_orcid(self, orcid_id: str):
        print(f"[INFO] Harvesting works for {orcid_id}")

        record = self.client.get_record(orcid_id)
        put_codes = self.extract_put_codes(record)

        inserted = 0

        for put_code in put_codes:
            work_data = self.client.get_work(orcid_id, put_code)
            work = self.parse_work(orcid_id, put_code, work_data)

            if self.work_storage.insert(work.to_dict()):
                inserted += 1

            time.sleep(self.rate_limit_delay)

        self.mark_orcid_harvested(orcid_id, inserted)

        print(f"[DONE] {orcid_id} → {inserted} works")

    # ---------------------------------------------------------------------------
    # Helper functions for extraction of works and related data (i.e. put codes)
    # ---------------------------------------------------------------------------

    def extract_put_codes(self, record: dict) -> list[int]:
        put_codes = []

        for group in record.get("group", []):
            for summary in group.get("work-summary", []):
                if "put-code" in summary:
                    put_codes.append(summary["put-code"])

        return put_codes

    def parse_work(self, orcid_id: str, put_code: int, data: dict) -> Work:
        title = (
            data.get("title", {})
                .get("title", {})
                .get("value")
        )

        journal = data.get("journal-title", {}).get("value")

        year = (
            data.get("publication-date", {})
                .get("year", {})
                .get("value")
        )
        year = int(year) if year else None

        external_ids = []
        for ext in data.get("external-ids", {}).get("external-id", []):
            external_ids.append({
                "type": ext.get("external-id-type"),
                "value": ext.get("external-id-value")
            })

        contributors = []
        for c in data.get("contributors", {}).get("contributor", []):
            credit_name = (
                c.get("credit-name", {})
                .get("value")
            )

            if not credit_name:
                continue  # skip unusable contributors

            contributor_orcid = (
                c.get("contributor-orcid", {})
                .get("path")
            )

            attrs = c.get("contributor-attributes", {})

            contributors.append({
                "credit_name": credit_name,
                "normalized_name": self._normalize_name(credit_name),
                "orcid_id": contributor_orcid,
                "role": attrs.get("contributor-role"),
                "sequence": attrs.get("contributor-sequence")
            })
        return Work(
            orcid_id=orcid_id,
            put_code=put_code,
            title=title,
            journal_title=journal,
            publication_year=year,
            work_type=data.get("type"),
            external_ids=external_ids,
            contributors=contributors,
            visibility=data.get("visibility")
        )

    """
    Mark ORCID as harvested in orcids collection.
    """
    def mark_orcid_harvested(self, orcid_id: str, works_count: int):
        self.orcid_storage.mark_harvested(
            orcid_id,
            works_count=works_count,
            harvested_at=datetime.now(timezone.utc)
        )

    def _normalize_name(self, name: str) -> str:
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))
        return name.lower().strip()