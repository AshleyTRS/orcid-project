from pymongo import MongoClient


class MongoConnection:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def orcids(self):
        return self.db.orcids

    def partitions(self):
        return self.db.partitions
