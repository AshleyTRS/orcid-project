# Database Backup and Restoration

Two scripts create backups of the database named by `DB_NAME` in `.env`. Both write to a timestamped subdirectory of `backups/` in the project root, which is excluded from version control. A backup should be taken before running migrations or any operation that modifies many documents.

| Script | Method | Format |
| --- | --- | --- |
| `dump_database.py` | MongoDB Database Tools (`mongodump`) | BSON with metadata |
| `dump_database_pymongo.py` | PyMongo | JSON, one file per collection |

`dump_database.py` is the recommended method. `dump_database_pymongo.py` is an alternative for environments in which the Database Tools cannot be installed.

---

## `dump_database.py`

### Prerequisites of the mongodump method

The MongoDB Database Tools must be installed and `mongodump` must be on the system path.

| Platform | Installation |
| --- | --- |
| Windows | Installer from <https://www.mongodb.com/docs/database-tools/installation/> |
| macOS | `brew install mongodb-database-tools` |
| Ubuntu or Debian | `sudo apt-get install mongodb-database-tools` (from the MongoDB package repository) |

### Usage of the mongodump method

```bash
python scripts/db_dumps/dump_database.py
```

### Output of the mongodump method

```txt
backups/
  <DB_NAME>_backup_<YYYYMMDD_HHMMSS>/
    <DB_NAME>/
      works.bson
      works.metadata.json
      orcids.bson
      ...
```

The script invokes `mongodump --db=<DB_NAME> --out=<backup directory>` and does not write the connection string to its log.

### Properties of the mongodump method

`mongodump` preserves every BSON type (for example `ObjectId` and dates) together with index definitions, produces compact files, and is suited to large databases. Restoration uses `mongorestore`.

---

## `dump_database_pymongo.py`

### Prerequisites of the PyMongo method

None beyond the project dependencies.

### Usage of the PyMongo method

```bash
python scripts/db_dumps/dump_database_pymongo.py
```

### Output of the PyMongo method

```txt
backups/
  <DB_NAME>_backup_pymongo_<YYYYMMDD_HHMMSS>/
    metadata.json          collection names and document counts
    works.json
    orcids.json
    works_metadata.json
    ...
```

### Properties of the PyMongo method

The files are human-readable and require no external tools. JSON is larger than BSON and slower to produce for large collections, and it does not preserve BSON types: `ObjectId` values and dates are written as strings. Index definitions are not saved, and restoration requires a custom script.

---

## Comparison

| Property | `mongodump` | PyMongo |
| --- | --- | --- |
| Speed on large collections | Higher | Lower |
| File size | Smaller (BSON) | Larger (JSON) |
| External dependency | MongoDB Database Tools | None |
| Human-readable | No | Yes |
| BSON types and indexes preserved | Yes | No |
| Restoration | `mongorestore` | Custom script |

---

## Restoration

### From a `mongodump` backup

```bash
# Entire database
mongorestore --uri="<MONGO_CONN>" --db=<DB_NAME> ./backups/<DB_NAME>_backup_<timestamp>/<DB_NAME>

# One collection
mongorestore --uri="<MONGO_CONN>" --db=<DB_NAME> --collection=works \
  ./backups/<DB_NAME>_backup_<timestamp>/<DB_NAME>/works.bson
```

Adding `--drop` replaces existing collections instead of inserting into them.

### From a PyMongo backup

The JSON files are restored with a short script. Identifiers and dates are restored as strings unless they are converted explicitly.

```python
import json
from pymongo import MongoClient

with open("backups/<backup directory>/works.json", encoding="utf-8") as f:
    documents = json.load(f)

client = MongoClient("<MONGO_CONN>")
client["<DB_NAME>"].works.insert_many(documents)
```

The indexes used by the application are recreated by `python -m src.data_migration.run_all`.
