import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

mongo_conn = os.getenv("MONGO_CONN")

try:
    client = MongoClient(mongo_conn, serverSelectionTimeoutMS=5000)

    client.admin.command("ping")

    print("Successfully connected to MongoDB!")

except ConnectionFailure as e:
    print("Failed to connect to MongoDB.")
    print(e)

