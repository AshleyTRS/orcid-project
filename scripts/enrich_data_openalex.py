from dotenv import load_dotenv
import os
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.data_enrichment.metadata.MetadataHarvester import MetadataHarvester
from src.data_enrichment.openalex.OpenAlexClient import OpenAlexClient
from src.data_enrichment.openalex.OpenAlexNormalizer import OpenAlexNormalizer
from src.data_enrichment.metadata.MetadataSelector import MetadataSelector
from src.data_enrichment.storage.MetadataStorage import MetadataStorage
from src.db.MongoConnection import MongoConnection

def main():
    load_dotenv()
    mongo = MongoConnection(
        uri = os.getenv("MONGO_CONN"),
        db_name= os.getenv("DB_NAME")
    )

    # Initialize components
    client = OpenAlexClient()
    normalizer = OpenAlexNormalizer()
    selector = MetadataSelector(mongo.queue())
    storage = MetadataStorage(mongo.metadata())

    # Populate the metadata queue from works collection
    logging.info("Populating metadata queue from works...")
    count = selector.populate_from_works(mongo.works())
    logging.info(f"Queue initialized with {count} DOIs")

    if count == 0:
        logging.info("No DOIs to process.")
        return

    # Create and run harvester
    harvester = MetadataHarvester(client, normalizer, selector, storage)
    harvester.run()

    # Close mongo conn
    mongo.close()

if __name__ == "__main__":
    main()