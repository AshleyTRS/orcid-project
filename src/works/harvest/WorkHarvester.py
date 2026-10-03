"""
Docstring for harvest_works_models.WorkHarvester
Harvests works for discovered ORCID profiles.
"""

import time
from datetime import datetime, timezone
from ..models.Work import Work
from ..storage.WorkStorage import WorkStorage
from src.orcid.search.OrcidSearchClient import OrcidSearchClient
from src.orcid.storage.OrcidStorage import OrcidStorage
from src.works.names import normalize_person_name
from src.works.work_key import apply_work_keys, compute_work_key, update_unique_works_counts

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
        total_harvested = 0
        for orcid in orcids:
            try:
                self.harvest_orcid(orcid["orcid_id"])
                total_harvested += 1
                # works_count = ORCID records stored for this author (unique works are counted separately)
                self.mark_orcid_harvested(orcid["orcid_id"], self.work_storage.count_by_orcid(orcid["orcid_id"]))
            except Exception as e:
                print(f"[ERROR] {orcid['orcid_id']}: {e}")

        print(f"Total works harvested: {total_harvested}")                

    def harvest_orcid(self, orcid_id: str):
        print(f"[INFO] Harvesting works for {orcid_id}")

        record = self.client.get_record(orcid_id)
        put_codes = self.extract_put_codes(record)

        print(f"Number of extracted put codes {len(put_codes)}")

        inserted = 0

        for put_code in put_codes:
            try:
                work_data = self.client.get_work(orcid_id, put_code)
                work = self.parse_work(orcid_id, put_code, work_data)

                if self.work_storage.insert(work.to_dict()):
                    inserted += 1

                time.sleep(self.rate_limit_delay)

            except Exception as e:
                print(f"[WARN] {orcid_id} put-code {put_code}: {e}")

        # Link this author's duplicate records (e.g. a no-DOI copy of a DOI work)
        # and refresh their unique works count
        apply_work_keys(self.work_storage.collection, [orcid_id])
        update_unique_works_counts(self.work_storage.collection, self.orcid_storage.collection, [orcid_id])

        print(f"[DONE] {orcid_id} → {inserted} works")

    # ---------------------------------------------------------------------------
    # Helper functions for extraction of works and related data (i.e. put codes)
    # ---------------------------------------------------------------------------

    def extract_put_codes(self, record: dict) -> list[int]:
        put_codes = []

        works = record.get("activities-summary", {}).get("works", {})
        for group in works.get("group", []):
            for summary in group.get("work-summary", []):
                if "put-code" in summary:
                    put_codes.append(summary["put-code"])

        return put_codes

    def parse_work(self, orcid_id: str, put_code: int, data: dict) -> Work:
        title = (
            (data.get("title") or {})
                .get("title") or {}
        ).get("value")

        journal = (data.get("journal-title") or {}).get("value")

        year = (
            ((data.get("publication-date") or {})
                .get("year") or {})
                .get("value")
        )
        year = int(year) if year else None

        external_ids = []
        ext_container = data.get("external-ids") or {}
        ext_list = ext_container.get("external-id") or []

        for ext in ext_list:
            external_ids.append({
                "type": ext.get("external-id-type"),
                "value": ext.get("external-id-value")
            })

        contributors = []
        contrib_container = data.get("contributors") or {}
        contrib_list = contrib_container.get("contributor") or []

        for c in contrib_list:
            credit_name = (c.get("credit-name") or {}).get("value")
            if not credit_name:
                continue

            normalized = self.normalize_name(credit_name)
            tokens = normalized.split() if normalized else []

            contributor_orcid = (
                (c.get("contributor-orcid") or {})
                .get("path")
            )

            attrs = c.get("contributor-attributes") or {}

            contributors.append({
                "credit_name": credit_name,
                "normalized_name": normalized,
                "tokens": tokens,
                "orcid_id": contributor_orcid,
                "role": attrs.get("contributor-role"),
                "sequence": attrs.get("contributor-sequence")
            })

        work = Work(
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
        work.work_key = compute_work_key(work.to_dict())
        return work

    """
    Mark ORCID as harvested in orcids collection.
    """
    def mark_orcid_harvested(self, orcid_id: str, works_count: int):
        self.orcid_storage.mark_harvested(
            orcid_id,
            works_count=works_count,
            harvested_at=datetime.now(timezone.utc)
        )

    def normalize_name(self, name: str) -> str:
        # Shared with contributor linking so that both sides of a name comparison match
        return normalize_person_name(name)