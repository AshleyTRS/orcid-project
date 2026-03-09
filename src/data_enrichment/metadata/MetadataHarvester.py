"""
Docstring for metadata.MetadataHarvester
Orchestrates the harvesting and storage of metadata documents.

The harvester pulls pending DOI tasks from a selector, fetches metadata
from the OpenAlex API, normalizes the raw records, and inserts them into
the metadata storage collection.  Tasks are marked done or failed based
on the success of each operation and all exceptions are handled to allow
continuous processing of subsequent items.
"""
import logging

from src.data_enrichment.openalex.OpenAlexClient import OpenAlexClient
from src.data_enrichment.openalex.OpenAlexNormalizer import OpenAlexNormalizer
from src.data_enrichment.metadata.MetadataSelector import MetadataSelector
from src.data_enrichment.storage.MetadataStorage import MetadataStorage
from src.data_enrichment.utils import normalize_doi


class MetadataHarvester:
    # class constructor
    def __init__(
        self,
        client: OpenAlexClient,
        normalizer: OpenAlexNormalizer,
        selector: MetadataSelector,
        storage: MetadataStorage):

        self.client = client
        self.normalizer = normalizer
        self.selector = selector
        self.storage = storage

    def run(self):

        while True:
            tasks = self.selector.get_batch()
            
            if not tasks:
                logging.info("No pending tasks.")
                break
           
            dois = [t["doi"] for t in tasks]
            doi_to_task = {t["doi"].lower(): t for t in tasks}

            try:
                results = self.client.fetch_batch_by_doi(dois)
                successful_task_ids = []

                for raw in results:
                    doi = normalize_doi(raw.get("doi"))
                    if not doi:
                        logging.warning(f"No DOI found in OpenAlex result")
                        continue
                        
                    task = doi_to_task.get(doi)
                    if not task:
                        logging.warning(f"No task found for DOI {doi}")
                        continue
                    
                    try:
                        normalized = self.normalizer.normalize(raw)
                        success = self.storage.insert_metadata(normalized)
                        if success:
                            successful_task_ids.append(task["_id"])
                        else:
                            logging.error(f"Failed to insert metadata for DOI {doi}")
                            self.selector.mark_failed(task["_id"])
                    except Exception as e:
                        logging.error(f"Error processing DOI {doi}: {e}")
                        self.selector.mark_failed(task["_id"])

                # Mark successful tasks as done
                for task_id in successful_task_ids:
                    self.selector.mark_done(task_id)

                # Mark tasks not in results as failed (assuming all requested DOIs should have results if valid)
                processed_dois = {raw.get("doi", "").replace("https://doi.org/", "").lower() for raw in results}
                for doi, task in doi_to_task.items():
                    if doi not in processed_dois:
                        logging.warning(f"No result for DOI {doi}")
                        self.selector.mark_failed(task["_id"])

            except Exception as e:
                logging.error(f"Batch failed: {e}")
                for task in tasks:
                    self.selector.mark_failed(task["_id"])