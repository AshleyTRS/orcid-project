from datetime import datetime, timezone
import logging


class MetadataStorage:
    """Handles persistence of normalized metadata documents.

    Documents are upserted into a `works_metadata` collection keyed by DOI
    and source. Failures are logged and cause `insert_metadata` to return
    False rather than raising, allowing callers to react accordingly.
    """

    def __init__(self, collection):

        self.collection = collection

        self.collection.create_index(
            [("doi", 1), ("source", 1)],
            unique=True
        )

    def insert_metadata(self, metadata):
        try:
            metadata["harvested_at"] = datetime.now(timezone.utc)

            self.collection.update_one(
                {
                    "doi": metadata["doi"],
                    "source": metadata["source"]
                },
                {"$set": metadata},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error inserting metadata for DOI {metadata.get('doi', 'unknown')}: {str(e)}")
            return False
        return True