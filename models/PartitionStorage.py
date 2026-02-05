"""
Docstring for models.PartitionStorage

"""
class PartitionStorage:
    def __init__(self, collection):
        self.collection = collection
        self.collection.create_index(
            [("base_query", 1), ("prefix", 1)],
            unique=True
        )
        self.collection.create_index("status")

    def add_partition(self, partition):
        self.collection.update_one(
            {
                "base_query": partition.base_query,
                "prefix": partition.prefix
            },
            {
                "$setOnInsert": {
                    "depth": partition.depth,
                    "status": "pending"
                }
            },
            upsert=True
        )

    def fetch_next_pending(self):
        return self.collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "processing"}}
        )

    def mark_done(self, partition_doc):
        self.collection.update_one(
            {"_id": partition_doc["_id"]},
            {"$set": {"status": "done"}}
        )
