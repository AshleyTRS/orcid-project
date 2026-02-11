"""
Docstring for harvest_works_models.WorkHarvester
Harvests works for discovered ORCID profiles.
"""

import time
from datetime import datetime
from .Work import Work
from .WorkStorage import WorkStorage
from search_models.OrcidSearchClient import OrcidSearchClient
from search_models.OrcidStorage import OrcidStorage

class WorkHarvester:
    def __init__(
        self,
        record_client : OrcidSearchClient,
        orcid_storage : OrcidStorage,
        work_storage : WorkStorage,
        rate_limit_delay: float = 0.1
    ):
        self.record_client = record_client
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

        summary = self.record_client.iy(orcid_id)
        put_codes = self._extract_put_codes(summary)

        inserted = 0

        for put_code in put_codes:
            work_data = self.record_client.get_work(orcid_id, put_code)
            work = self._parse_work(orcid_id, put_code, work_data)

            if self.work_storage.insert(work.to_dict()):
                inserted += 1

            time.sleep(self.rate_limit_delay)

        self._mark_orcid_harvested(orcid_id, inserted)

        print(f"[DONE] {orcid_id} → {inserted} works")

    # ---------------------------------------------------------------------------
    # Helper functions for extraction of works and related data (i.e. put codes)
    # ---------------------------------------------------------------------------

    def _extract_put_codes(self, works_summary: dict) -> list[int]:
        put_codes = []

        for group in works_summary.get("group", []):
            for summary in group.get("work-summary", []):
                if "put-code" in summary:
                    put_codes.append(summary["put-code"])

        return put_codes

    def _parse_work(self, orcid_id: str, put_code: int, data: dict) -> Work:
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

        return Work(
            orcid_id=orcid_id,
            put_code=put_code,
            title=title,
            journal_title=journal,
            publication_year=year,
            work_type=data.get("type"),
            external_ids=external_ids,
            visibility=data.get("visibility")
        )

    def _mark_orcid_harvested(self, orcid_id: str, works_count: int):
        """
        Mark ORCID as harvested.
        """
        self.orcid_storage.mark_harvested(
            orcid_id,
            works_count=works_count,
            harvested_at=datetime.utcnow()
        )
