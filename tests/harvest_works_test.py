from datetime import datetime
from search_models import OrcidSearchClient
from harvest_works_models import WorkHarvester, WorkStorage
from conn.MongoConnection import MongoConnection
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
    work_storage = WorkStorage(mongo.partitions())

    API_ENDPOINT = "https://pub.orcid.org/v3.0/0000-0003-2043-8766/works"
    API_TOKEN = os.getenv("ACCESS_TOKEN")
    # initialize ORCID client
    orcid_client = OrcidSearchClient(API_ENDPOINT, client_id=API_TOKEN)

    # initialize harvester
    harvester = WorkHarvester(
        orcid_client=orcid_client,
        work_storage=work_storage
    )

    # ---------- RUN ----------
    print(f"Harvesting works for ORCID: {ORCID_ID}")
    harvested_count = harvester.harvest_orcid(orcid=ORCID_ID)

    print("---------- RESULT ----------")
    print(f"Works harvested: {harvested_count}")
    print(f"Finished at: {datetime.utcnow().isoformat()}")

if __name__ == "__main__":
    main()
