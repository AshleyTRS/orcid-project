from datetime import datetime
from search_models import OrcidStorage, OrcidSearchClient
from harvest_works_models import WorkStorage, WorkHarvester


def main():
    # ---------- CONFIG ----------
    MONGO_URI = "mongodb://localhost:27017"
    DB_NAME = "orcid_db"

    ORCID_COLLECTION = "orcids"
    WORKS_COLLECTION = "works"

    # ---------- INIT ----------

    orcid_storage = OrcidStorage(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        collection_name=ORCID_COLLECTION
    )

    work_storage = WorkStorage(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        collection_name=WORKS_COLLECTION
    )

    API_ENDPOINT = ""
    
    orcid_client = OrcidSearchClient()

    harvester = WorkHarvester(
        record_client=orcid_client,
        orcid_storage=orcid_storage,
        work_storage=work_storage
    )

    # ---------- FETCH ORCIDS ----------
    print("Fetching ORCIDs from database...")
    orcids = orcid_storage.get_all_orcids()

    print(f"Found {len(orcids)} ORCIDs")

    total_works = 0
    processed_orcids = 0

    # ---------- HARVEST LOOP ----------
    for orcid_doc in orcids:
        orcid = orcid_doc["orcid"]
        print(f"\nHarvesting works for ORCID: {orcid}")

        try:
            count = harvester.harvest(orcid=orcid)
            total_works += count
            processed_orcids += 1

            print(f"  → {count} works harvested")

        except Exception as e:
            print(f"  ✖ Failed for {orcid}: {e}")

    # ---------- SUMMARY ----------
    print("\n========== HARVEST SUMMARY ==========")
    print(f"ORCIDs processed : {processed_orcids}")
    print(f"Total works      : {total_works}")
    print(f"Finished at      : {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    main()
