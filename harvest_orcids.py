from conn.MongoConnection import MongoConnection
from search_models import OrcidStorage, PartitionStorage, OrcidSearchClient, DiscoveryEngine
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

    # Select seed query
    seeds = {
        "1": '(current-institution-affiliation-name:"Universidad Autónoma del Estado de Hidalgo" OR "Universidad Autonoma del Estado de Hidalgo" OR "UNIVERSIDAD AUTÓNOMA DEL ESTADO DE HIDALGO")',
        "2": 'current-institution-affiliation-name:"Centro de Investigacion en Tecnologias de Informacion y Sistemas"',
        "3": 'current-institution-affiliation-name:"Universidad Autónoma del Estado de Hidalgo" AND given-names:Ashley',
        "4" : 'current-institution-affiliation-name:"UAEH'
    }

    print("Select query")

    for key, value in seeds.items():
        print(f"{key}. {value}")


    selected_seed = input()
  
    engine.seed(seeds[selected_seed])
    engine.run()


if __name__ == "__main__":
    main()
