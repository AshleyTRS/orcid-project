from pymongo import MongoClient


class MongoConnection:
    def __init__(self, uri: str, db_name: str):
        if not uri:
            raise ValueError("MONGO_CONN environment variable is not set")
        if not db_name:
            raise ValueError("DB_NAME environment variable is not set")
        
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def orcids(self):
        return self.db.orcids

    def partitions(self):
        return self.db.partitions
    
    def works(self):
        return self.db.works

    def close(self):
        self.client.close()