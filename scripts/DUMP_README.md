# Database Dump Scripts

Two scripts for creating MongoDB database backups:

## Option 1: `dump_database.py` (Recommended - Uses mongodump)

Uses the standard MongoDB `mongodump` tool for efficient, native backups.

### Prerequisites

Install MongoDB tools:

```bash
# macOS
brew install mongodb-community

# Linux - Ubuntu/Debian
sudo apt-get install mongodb-org-tools

# Windows
# Download from: https://docs.mongodb.com/database-tools/installation/
# Or use Chocolatey: choco install mongodb-database-tools
```

### Usage

```bash
# From project root
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

- **Built-in MongoDB tool** - Standard method  
- **Binary format** - Preserves all data types  
- **Fast** - Efficient for large databases  
- **Can restore with mongorestore** - Standard tooling  

---

## Option 2: `dump_database_pymongo.py` (Portable - Pure Python)

Uses PyMongo to create JSON backups. No external dependencies needed.

### Prerequisites

PyMongo is already installed (check requirements.txt).

### Usage

```bash
# From project root
python scripts/dump_database_pymongo.py
```

### Output

Creates timestamped backup in `./backups/` directory:

```
backups/
└── orcid_backup_pymongo_20260319_143022/
    ├── metadata.json      (collection names, document count)
    ├── works.json
    ├── orcids.json
    ├── works_metadata.json
    └── ... (all collections as JSON files)
```

### Advantages

✓ **No external dependencies** - Pure Python  
✓ **Human-readable** - JSON format  
✓ **Easy to inspect** - Open JSON files directly  
✓ **Portable** - Works anywhere Python runs  
✓ **Git-friendly** - Can version control in git (if small)  

### Disadvantages

✗ **Slower** - JSON serialization takes longer  
✗ **Larger files** - JSON is more verbose than BSON  
✗ **Type conversion** - ObjectIds become strings  

---

## Comparison

| Feature | mongodump | PyMongo |
|---------|-----------|---------|
| Speed | ⭐⭐⭐ Fast | ⭐ Slow |
| File size | ⭐⭐⭐ Small (BSON) | ⭐ Large (JSON) |
| Dependencies | MongoDB tools required | PyMongo only |
| Human-readable | ⭐ Binary format | ⭐⭐⭐ JSON |
| Restore | Use mongorestore | Custom script needed |
| Large databases | ⭐⭐⭐ Recommended | ⭐ Not ideal |

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

You would need to write a restoration script. Example:

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

---

## Scheduling Regular Backups

### Using cron (Linux/macOS)

```bash
# Backup daily at 2 AM
0 2 * * * cd /path/to/orcid-project && python scripts/dump_database.py
```

### Using Task Scheduler (Windows)

Create a batch file:

```batch
@echo off
cd C:\Users\ashle\OneDrive\Desktop\tesis\orcid-project
python scripts\dump_database.py
```

Then schedule in Task Scheduler to run at desired times.

---

## Tips

- **Regular backups** - Run daily or before major migrations
- **Store backups** - Keep copies in cloud storage (AWS S3, Google Cloud, etc.)
- **Monitor size** - Large databases produce large backups
- **Test restoration** - Periodically test restoring from backups
- **Keep old backups** - Implement retention policy (e.g., keep last 30 backups)

---

## Example: Backup Before Migration

```bash
# Create backup before running migrations
python scripts/dump_database.py

# Run migrations
python -m src.data_migration.run_all

# If something goes wrong, restore from backup
mongorestore --uri="<PROD_URI>" --db=orcid ./backups/orcid_backup_<timestamp>/orcid
```
