from datetime import datetime
from dotenv import load_dotenv
import os
from src.db.MongoConnection import MongoConnection
from src.orcid.storage.OrcidStorage import OrcidStorage
from src.orcid.search.OrcidSearchClient import OrcidSearchClient
from src.works.harvest.WorkHarvester import WorkHarvester
from src.works.storage.WorkStorage import WorkStorage

def main():
    load_dotenv()
    mongo = MongoConnection(
        uri = os.getenv("MONGO_CONN"),
        db_name= os.getenv("DB_NAME")
    )

    # Initialize mongo collections
    orcid_storage = OrcidStorage(mongo.orcids())
    work_storage = WorkStorage(mongo.works())

    API_ENDPOINT = "https://pub.orcid.org/v3.0"
    API_TOKEN = os.getenv("ACCESS_TOKEN")
    
    # initialize ORCID client
    orcid_client = OrcidSearchClient(API_ENDPOINT, client_id=API_TOKEN)

    # initialize harvester
    harvester = WorkHarvester(
        client=orcid_client,
        orcid_storage=orcid_storage,
        work_storage=work_storage
    )

    # harvest works
    harvester.harvest_all()

    mongo.close()


if __name__ == "__main__":
    main()
