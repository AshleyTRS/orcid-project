from .AbstractReconstructor import AbstractReconstructor
from src.data_enrichment.utils import normalize_doi
import logging


class OpenAlexNormalizer:
    """Convert raw OpenAlex JSON into the internal metadata schema.

    The harvester relies on this class for each record it receives; any
    unexpected structure will be caught and logged, returning an empty
    fallback dictionary to avoid breaking the upstream loop.
    """

    SOURCE = "openalex"

    def normalize(self, raw):
        try:
            pdf_url = None
            if raw.get("best_oa_location"):
                pdf_url = raw["best_oa_location"].get("pdf_url")

            abstract = AbstractReconstructor.reconstruct(
                raw.get("abstract_inverted_index")
            )

            return {
                "source": self.SOURCE,
                "doi": self._extract_doi(raw),
                "openalex_id": raw.get("id"),
                "pdf_url": pdf_url,
                "open_access": raw.get("open_access"),
                "topics": raw.get("topics", []),
                "keywords": raw.get("keywords", []),
                "concepts": raw.get("concepts", []),
                "abstract": abstract,
            }
        except Exception as e:
            logging.error(f"Error normalizing record: {e}")
            # return minimal structure so caller can still attempt to insert
            return {"source": self.SOURCE, "doi": None}

    def _extract_doi(self, raw):
        doi = raw.get("doi")
        if not doi:
            return None
        return normalize_doi(doi)