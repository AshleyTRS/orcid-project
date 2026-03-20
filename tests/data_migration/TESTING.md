# Running Data Migration Tests

## Quick Start

```bash
# Run all data migration tests
pytest tests/data_migration/ -v

# Run with coverage report
pytest tests/data_migration/ --cov=src.data_migration --cov-report=html

# Run specific test file
pytest tests/data_migration/test_migrate_doi.py -v

# Run specific test
pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI::test_extract_doi_from_external_ids -v
```

## Test Summary

✅ **64 tests covering all 7 migration scripts**

**Test Coverage:**

- [test_migrate_doi.py](test_migrate_doi.py) - 7 tests
  - DOI extraction from external_ids
  - Handling missing/empty DOIs
  - Case preservation
  
- [test_merge_metadata.py](test_merge_metadata.py) - 6 tests
  - Metadata merging from OpenAlex
  - Partial metadata handling
  - Multiple works processing

- [test_enrich_institutions.py](test_enrich_institutions.py) - 5 tests
  - Institution enrichment from ORCID profiles
  - Array formatting
  - Institution mapping

- [test_link_contributors.py](test_link_contributors.py) - 14 tests
  - Name normalization (case, hyphens, whitespace)
  - Contributor-to-ORCID matching
  - Multiple contributors per work

- [test_add_author_count.py](test_add_author_count.py) - 8 tests
  - Author count precomputation
  - Edge cases (empty, missing, invalid contributors)
  - Large contributor lists

- [test_create_indexes.py](test_create_indexes.py) - 11 tests
  - Index creation for all query types
  - Single and compound indexes
  - NLP and co-authorship indexes

- [test_drop_unused_indexes.py](test_drop_unused_indexes.py) - 7 tests
  - Removing obsolete indexes  
  - Graceful handling of missing indexes
  - Preserving needed indexes

- [test_run_all.py](test_run_all.py) - 6 tests
  - Migration orchestration
  - Error handling
  - Result tracking

## Key Features

✓ **No Real Database** - All tests use in-memory mocked collections  
✓ **Fast** - Full suite runs in <1 second  
✓ **Comprehensive** - 64 test cases covering all edge cases  
✓ **Safe** - Test any time before running on production  

## Running Before Production

```bash
# 1. Run all tests locally
pytest tests/data_migration/ -v

# 2. Set up test database (MongoDB Atlas free tier)
# Update .env with test database credentials

# 3. Run migrations on test database
python -m src.data_migration.run_all

# 4. Backup production database
mongodump --uri="<PROD_URI>" --out=./backup_$(date +%s)

# 5. Run migrations on production
python -m src.data_migration.run_all
```

## Testing Each Migration Independently

```bash
# Test DOI extraction only
python -m src.data_migration.migrate_doi

# Test metadata merging only
python -m src.data_migration.merge_metadata

# Test institution enrichment only
python -m src.data_migration.enrich_institutions

# ... etc for other migrations
```

## Troubleshooting

**Import errors?** Make sure you're in the project root:

```bash
cd /path/to/orcid-project
```

**Tests failing?** Check Python version (requires 3.12+):

```bash
python --version
```

**Need more detail?** See [README.md](README.md) for comprehensive testing guide.
