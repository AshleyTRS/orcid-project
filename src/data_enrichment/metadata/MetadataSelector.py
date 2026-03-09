from datetime import datetime, timezone
import logging
from src.data_enrichment.utils import normalize_doi


class MetadataSelector:
    """Manage a queue of DOI metadata tasks.

    Tasks are inserted with `enqueue` and retrieved in batches via
    `get_batch`. Status updates (`done`/`failed`) are also handled. All
    database operations are guarded so that a failure does not raise
    unhandled exceptions and will be logged instead.
    """

    def __init__(self, collection):

        self.queue = collection

        self.queue.create_index(
            [("doi", 1), ("source", 1)],
            unique=True
        )

        self.queue.create_index(
            [("status", 1), ("source", 1)]
        )

    def enqueue(self, doi, source="openalex"):
        try:
            self.queue.insert_one({
                "doi": doi,
                "source": source,
                "status": "pending",
                "attempts": 0,
                "created_at": datetime.now(timezone.utc)
            })
        except Exception as e:
            logging.warning(f"Failed to enqueue DOI {doi} ({source}): {e}")

    def get_batch(self, source="openalex", size=25):
        try:
            tasks = list(
                self.queue.find(
                    {"status": "pending", "source": source}
                ).limit(size)
            )

            if not tasks:
                return []

            ids = [t["_id"] for t in tasks]

            self.queue.update_many(
                {"_id": {"$in": ids}},
                {"$set": {"status": "processing"}}
            )

            return tasks
        except Exception as e:
            logging.error(f"Error retrieving batch from selector: {e}")
            return []

    def mark_done(self, task_id):
        try:
            self.queue.update_one(
                {"_id": task_id},
                {"$set": {"status": "done"}}
            )
        except Exception as e:
            logging.error(f"Failed to mark task {task_id} done: {e}")

    def mark_failed(self, task_id):
        try:
            self.queue.update_one(
                {"_id": task_id},
                {
                    "$set": {"status": "failed"},
                    "$inc": {"attempts": 1}
                }
            )
        except Exception as e:
            logging.error(f"Failed to mark task {task_id} failed: {e}")

    def populate_from_works(self, works_collection, source="openalex"):
        """Extract unique DOIs from works collection and enqueue them.
        
        Useful for initializing the metadata queue with all DOIs from
        harvested works that need metadata enrichment.
        
        Handles edge cases:
        - Works with no external_ids field are skipped
        - Works with external_ids but no DOI are skipped with a warning
        - Works with multiple identifiers are checked for DOI type only
        - Duplicate DOIs are handled by the unique index
        - DOI normalization: removes URL prefixes, lowercase, strip whitespace
        """
        try:
            # Query all works to check for external_ids
            works = works_collection.find({}, {"external_ids": 1})
            
            dois_seen = set()
            count = 0
            skipped_no_doi = 0
            
            for work in works:
                doi = None
                
                # Check if external_ids exists and is not empty
                external_ids = work.get("external_ids", [])
                if not external_ids:
                    skipped_no_doi += 1
                    continue
                
                # Extract DOI from external_ids array
                for ext_id in external_ids:
                    if ext_id.get("type") == "doi":
                        doi = ext_id.get("value")
                        break
                
                # Skip if no DOI found
                if not doi:
                    skipped_no_doi += 1
                    continue
                
                # Normalize DOI (remove prefixes, lowercase, strip)
                doi = normalize_doi(doi)
                
                # Skip if already processed in this batch
                if doi in dois_seen:
                    continue
                    
                dois_seen.add(doi)
                
                try:
                    self.queue.insert_one({
                        "doi": doi,
                        "source": source,
                        "status": "pending",
                        "attempts": 0,
                        "created_at": datetime.now(timezone.utc)
                    })
                    count += 1
                except Exception:
                    # Silently skip duplicates (unique index will reject them)
                    pass
            
            if skipped_no_doi > 0:
                logging.warning(f"Skipped {skipped_no_doi} works without DOI identifiers")
            
            logging.info(f"Enqueued {count} DOIs for metadata enrichment")
            return count
        except Exception as e:
            logging.error(f"Failed to populate metadata queue from works: {e}")
            return 0
