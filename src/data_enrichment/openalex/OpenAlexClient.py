import requests
import time
import logging
from urllib.parse import quote


class OpenAlexClient:
    """Simple HTTP client for querying the OpenAlex works endpoint.

    Provides a small rate‑limit delay and raises friendly exceptions for
    network or protocol errors. The caller is responsible for catching
    Exceptions and reacting accordingly (the harvester already does so).
    """

    BASE_URL = "https://api.openalex.org/works"
    RATE_LIMIT_DELAY = 0.1  # ~10 req/sec safe limit

    def __init__(self):
        pass

    def fetch_batch_by_doi(self, dois):
        try:
            # URL-encode each DOI to handle special characters like commas
            encoded_dois = [quote(str(doi)) for doi in dois]
            filter_query = "|".join(encoded_dois)
            url = f"{self.BASE_URL}?filter=doi:{filter_query}"

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            time.sleep(self.RATE_LIMIT_DELAY)

            data = response.json()
            return data.get("results", [])
        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP error fetching DOIs {dois}: {e}")
            raise
        except ValueError as e:
            logging.error(f"Invalid JSON from OpenAlex for DOIs {dois}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error querying OpenAlex: {e}")
            raise