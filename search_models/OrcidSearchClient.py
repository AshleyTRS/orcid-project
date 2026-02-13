"""
Docstring for models.OrcidSearchClient

OrcidSearchClient class is a client for the ORCID Public API.
Since the ORCID Public API has a result limit of 10,000, this class takes that into account.
Responsibilities:
1) Build requests
2) Execute search
3) Handle paging and rate limits
3) Return result  count and ORCIDs
"""

import requests
import time
import json
from typing import List, Optional
from .QueryPartition import QueryPartition
from .OrcidProfile import OrcidProfile


class OrcidSearchClient:
    def __init__(self, endpoint: str, client_id: str, rate_limit_delay: float = 0.1):
        self.rate_limit_delay = rate_limit_delay
        self.endpoint = endpoint
        self.headers = {
            "Accept": "application/json", # request in json format
            "User-Agent": f"orcid-harvester/{client_id}"
        }

    """
    Lightweight request to check how many results exist.
    """
    def estimate_count(self, partition: QueryPartition) -> int:
        params = {
            "q": partition.to_query_string(),
            "rows": 0
        }

        response = requests.get(self.endpoint, headers=self.headers, params=params)
        response.raise_for_status()

        return response.json().get("num-found", 0)

    """
    Fetch all ORCID profiles for a safe partition (≤ 10^4).
    Returns complete profile data including names, emails, and institutions.
    """
    def fetch_orcids(self, partition: QueryPartition, rows: int = 1000) -> List[OrcidProfile]:
        start = 0
        profiles = []

        while True:
            params = {
                "q": partition.to_query_string(),
                "start": start,
                "rows": rows
            }

            response = requests.get(self.endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("expanded-result", [])
            if not results:
                break

            for r in results:
                profile = OrcidProfile(
                    orcid_id=r.get("orcid-id", ""),
                    given_names=r.get("given-names"),
                    family_names=r.get("family-names"),
                    credit_name=r.get("credit-name"),
                    other_names=r.get("other-name", []) if r.get("other-name") else [],
                    emails=r.get("email", []) if r.get("email") else [],
                    institution_names=r.get("institution-name", []) if r.get("institution-name") else []
                )
                profiles.append(profile)

            if len(results) < rows:
                break

            start += rows
            time.sleep(self.rate_limit_delay)

        return profiles

    """
    Fetch a single ORCID Record.
    Returns raw JSON responses.
    """
    def get_record(self, orcid_id: str) -> dict:
        url = self.endpoint + "/" + orcid_id + "/record"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        time.sleep(self.rate_limit_delay)

        data = response.json()
        # print(data)
        return data

    """
        Fetch a single work record for a given ORCID and put-code.
        Returns the raw JSON response.
    """
    def get_work(self, orcid_id: str, put_code: int) -> dict:
        url = self.endpoint + "/" + str(orcid_id) + "/work/" + str(put_code)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        time.sleep(self.rate_limit_delay)

        data = response.json()

        # print(json.dumps(data, indent=2))

        return response.json()

