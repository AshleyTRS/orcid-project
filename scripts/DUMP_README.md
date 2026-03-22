# Database Dump Scripts

Two scripts for creating MongoDB database backups:

---

## Option 1: `dump_database.py`

Uses the standard MongoDB `mongodump` tool for efficient, native backups. This is the recommended script for backups.

### Prerequisites

Install MongoDB tools:

Using macOS:

```bash
brew install mongodb-community
```

Using Linux:

```bash
# Linux - Ubuntu/Debian
sudo apt-get install mongodb-org-tools
```

Using Windows:

Download from <https://docs.mongodb.com/database-tools/installation/>

### Usage

From project root run:

```bash
python scripts/dump_database.py
```

### Output

Creates timestamped backup in `./backups/` directory:

```bash
backups/
└── orcid_backup_20260319_143022/
    └── orcid/
        ├── works.bson
        ├── orcids.bson
        ├── works.metadata.json
        └── ... (all collections)
```

### Advantages

The built-in MongoDB tool is a standard method. All data types are preserved. Because it is a native tool, it is efficient for backing up large databases.

---

## Option 2: `dump_database_pymongo.py`

Uses PyMongo to create JSON backups. No external dependencies needed. This is a portable and pythonic method.

### Prerequisites

PyMongo is already installed (check requirements.txt).

### Usage

Run this from project root:

```bash
python scripts/dump_database_pymongo.py
```

### Output

Creates timestamped backup in `./backups/` directory:

```bash
backups/
└── orcid_backup_pymongo_20260319_143022/
    ├── metadata.json      (collection names, document count)
    ├── works.json
    ├── orcids.json
    ├── works_metadata.json
    └── ... (all collections as JSON files)
```

### Advantages

There are no external dependencies, format is human readable because it is backed up in JSON format, and it works anywhere Python runs.

### Disadvantages

This method can be slower for larger databases as JSON serialization takes longer. File sizes are bigger - JSON is more verbose than BSON. Not all data types are preserved. For examples, ObjectIds become strings.
  
---

## Comparison

| Feature | mongodump | PyMongo |
| --------- | ----------- | --------- |
| Speed | Fast | Slow |
| File size | Small (BSON) | Large (JSON) |
| Dependencies | MongoDB tools required | PyMongo only |
| Human-readable | Binary format | JSON |
| Restore | Use mongorestore | Custom script needed |
| Large databases | Recommended | Not ideal |

---

## Backup Locations

Both scripts create timestamped backups in `./backups/`:

```bash
./backups/
├── orcid_backup_20260319_140000/        (mongodump)
├── orcid_backup_20260319_143022/        (mongodump)
└── orcid_backup_pymongo_20260319_144000/ (PyMongo)
```

---

## Restoring Backups

### From mongodump backup

```bash
# Restore entire database
mongorestore --uri="<MONGO_URI>" --db=<DB_NAME> ./backups/orcid_backup_20260319_140000/orcid

# Restore specific collection
mongorestore --uri="<MONGO_URI>" --db=<DB_NAME> --collection=works \
  ./backups/orcid_backup_20260319_140000/orcid/works.bson
```

### From PyMongo backup

It is necessary to write a restoration script. Example:

```python
import json
from pymongo import MongoClient

# Load backup
with open('backups/.../works.json') as f:
    documents = json.load(f)

# Insert into database
client = MongoClient("<MONGO_URI>")
db = client["<DB_NAME>"]
db.works.insert_many(documents)
```
