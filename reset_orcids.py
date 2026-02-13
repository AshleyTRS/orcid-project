from conn.MongoConnection import MongoConnection
from datetime import datetime
from dotenv import load_dotenv
import os


def main():
    load_dotenv()
    
    mongo = MongoConnection(
        uri = os.getenv("MONGO_CONN"),
        db_name= os.getenv("DB_NAME")
    )

    collection = mongo.orcids()

    # fix documents that were marked harvested
    result = collection.update_many(
        {"harvested": True},
        {
            "$set": {
                "harvested": False
            },
            "$unset": {
                "works_count": "",
                "works_harvested_at": ""
            }
        }
    )

    print(f"✔ Reset {result.modified_count} ORCID documents")

    mongo.close()


if __name__ == "__main__":
    main()
