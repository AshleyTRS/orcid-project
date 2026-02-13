from datetime import datetime, timezone
from src.orcid.search.OrcidSearchClient import OrcidSearchClient
from src.orcid.storage.OrcidStorage import OrcidStorage
from src.works.harvest.WorkHarvester import WorkHarvester
from src.works.storage.WorkStorage import WorkStorage
from src.db.MongoConnection import MongoConnection
from dotenv import load_dotenv
import os

def main():
    load_dotenv()
    mongo = MongoConnection(
        uri = os.getenv("MONGO_CONN"),
        db_name= os.getenv("DB_NAME")
    )

    ORCID_ID = "0000-0003-2043-8766"  # test ORCID

    # initialize work collection (storage)
    work_storage = WorkStorage(mongo.works())

    API_ENDPOINT = "https://pub.orcid.org/v3.0"
    API_TOKEN = os.getenv("ACCESS_TOKEN")
    
    # initialize ORCID client
    orcid_client = OrcidSearchClient(API_ENDPOINT, client_id=API_TOKEN)

    # initialize ORCID storage
    orcid_storage = OrcidStorage(mongo.orcids())

    # initialize harvester
    harvester = WorkHarvester(
        client=orcid_client,
        orcid_storage=orcid_storage,
        work_storage=work_storage
    )

    # ---------- RUN ----------
    print(f"Harvesting works for ORCID: {ORCID_ID}")
    harvester.harvest_orcid(ORCID_ID)
    print(f"Finished at: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()
