from src.db.MongoConnection import MongoConnection
from src.orcid.storage.OrcidStorage import OrcidStorage
from src.orcid.storage.PartitionStorage import PartitionStorage
from src.orcid.search.OrcidSearchClient import OrcidSearchClient
from src.orcid.search.DiscoveryEngine import DiscoveryEngine
from dotenv import load_dotenv
import os

def main():
    load_dotenv()
    mongo = MongoConnection(
        uri = os.getenv("MONGO_CONN"),
        db_name= os.getenv("DB_NAME")
    )

    orcid_storage = OrcidStorage(mongo.orcids())
    partition_storage = PartitionStorage(mongo.partitions())

    API_TOKEN = os.getenv("ACCESS_TOKEN")
    API_ENDPOINT = "https://pub.orcid.org/v3.0/expanded-search/"

    client = OrcidSearchClient(API_ENDPOINT, client_id=API_TOKEN)

    engine = DiscoveryEngine(
        client=client,
        orcid_storage=orcid_storage,
        partition_storage=partition_storage
    )

    # Select seed query. The field name must cover every spelling: in
    # 'field:"A" OR "B"' only "A" is limited to the field and "B" matches any
    # text on a profile, which is how unaffiliated researchers got in before.
    # Researchers are also checked when saved (src/orcid/affiliation.py).
    seeds = {
        "1": 'affiliation-org-name:("Universidad Autónoma del Estado de Hidalgo" OR "Universidad Autonoma del Estado de Hidalgo" OR "UAEH")',
        "2": 'current-institution-affiliation-name:"Centro de Investigacion en Tecnologias de Informacion y Sistemas"',
        "3": 'current-institution-affiliation-name:"Universidad Autónoma del Estado de Hidalgo" AND given-names:Ashley',
        "4" : 'current-institution-affiliation-name:"UAEH"'
    }

    print("Select query")

    for key, value in seeds.items():
        print(f"{key}. {value}")


    selected_seed = input()
  
    engine.seed(seeds[selected_seed])
    engine.run()

    mongo.close()


if __name__ == "__main__":
    main()
