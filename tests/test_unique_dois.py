import os
import sys
from dotenv import load_dotenv

from src.db.MongoConnection import MongoConnection

load_dotenv()

mongo = MongoConnection(
    uri=os.getenv("MONGO_CONN"),
    db_name=os.getenv("DB_NAME")
)

print("Unique DOIs from works collection:")
print("-" * 50)

count = 0
for doi in mongo.get_unique_dois():
    print(f"{count + 1}. {doi}")
    count += 1

print("-" * 50)
print(f"Total unique DOIs: {count}")

mongo.close()
