# Data Migration Testing Guide

## Overview

This directory contains 64 comprehensive pytest tests for all data migration scripts. All tests use mocked MongoDB collections; thus, no real database connection is required. Tests run in under 1 second on any machine.

## Key Testing Principles

- **No Database Required** - All tests use mocked collections  
- **Fast Execution** - In-memory operations (< 1 second)  
- **Comprehensive** - 64 test cases covering all scenarios  
- **Realistic Data** - Sample documents match actual schema  
- **Error Handling** - Tests verify graceful failure modes  
- **Isolation** - Each test is independent and reusable  

## Prerequisites

### 1. Verify Python Version

The project requires Python 3.12+:

```bash
python --version
# Expected output: Python 3.12.x or higher
```

If you don't have Python 3.12+, install it from [python.org](https://python.org).

### 2. Set Up Virtual Environment

If you haven't already, activate the project virtual environment:

#### Windows (Command Prompt)

```bash
venv\Scripts\activate
```

#### Linux/macOS

```bash
source venv/bin/activate
```

### 3. Install Test Dependencies

The test dependencies should already be in your environment, but you can explicitly install them:

```bash
pip install pytest pytest-cov
```

Verify installation:

```bash
pytest --version
# Expected output: pytest 9.0.0 or higher
```

## Quick Start

### Run All Tests

```bash
# Make sure you're in the project root directory
cd /path/to/orcid-project

# Run all 64 tests with verbose output
python -m pytest tests/data_migration/ -v
```

**Expected output:**

```bash
======================== 64 passed in 0.26s ========================
```

If all 64 tests pass, your environment is correctly set up and migrations are ready to test.

## Running Specific Tests

### Test Specific Migration

```bash
# Test DOI extraction only (7 tests)
python -m pytest tests/data_migration/test_migrate_doi.py -v

# Test metadata merging only (6 tests)
python -m pytest tests/data_migration/test_merge_metadata.py -v

# Test institution enrichment only (5 tests)
python -m pytest tests/data_migration/test_enrich_institutions.py -v

# Test contributor linking only (14 tests)
python -m pytest tests/data_migration/test_link_contributors.py -v

# Test author count computation only (8 tests)
python -m pytest tests/data_migration/test_add_author_count.py -v

# Test index creation only (11 tests)
python -m pytest tests/data_migration/test_create_indexes.py -v

# Test index removal only (7 tests)
python -m pytest tests/data_migration/test_drop_unused_indexes.py -v

# Test migration orchestration only (6 tests)
python -m pytest tests/data_migration/test_run_all.py -v
```

### Generate Coverage Report

To see how much code is covered by tests:

```bash
python -m pytest tests/data_migration/ --cov=src.data_migration --cov-report=html
```

This generates an HTML coverage report:

```bash
# Open the coverage report in your browser
open htmlcov/index.html          # macOS
xdg-open htmlcov/index.html      # Linux
start htmlcov\index.html         # Windows
```

**Coverage with mocked collections:**

- Unit test coverage: ~58% (mocks don't execute all code branches)
- Core migration logic: ~75% (main paths tested)
- Error handling: Covered in fallback scenarios

Full code coverage (>95%) requires integration tests with a real MongoDB database.

### Run Advanced Filtering

```bash
# Run a specific test class
python -m pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI -v

# Run a single test method
python -m pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI::test_extract_doi_from_external_ids -v

# Run tests matching a pattern
python -m pytest tests/data_migration/ -k "test_extract_doi" -v

# Run tests excluding a pattern
python -m pytest tests/data_migration/ -k "not test_run_all" -v
```

## Test Structure Overview

Each test file follows this pattern:

```bash
test_[migration_name].py
├── Class TestMigrationName
│   ├── test_basic_functionality
│   ├── test_edge_case_1
│   ├── test_edge_case_2
│   └── test_error_handling
└── Each test gets mock_collection fixture automatically
```

| File | Tests | Purpose |
| ------ | ------- | --------- |
| `test_migrate_doi.py` | 7 | Extract DOI from external_ids |
| `test_merge_metadata.py` | 6 | Merge OpenAlex metadata into works |
| `test_enrich_institutions.py` | 5 | Add institution info from ORCID |
| `test_link_contributors.py` | 14 | Match contributors to ORCID profiles |
| `test_add_author_count.py` | 8 | Compute author_count field |
| `test_create_indexes.py` | 11 | Create optimized database indexes |
| `test_drop_unused_indexes.py` | 7 | Remove obsolete indexes |
| `test_run_all.py` | 6 | Test migrations orchestration |
| **Total** | **64** | **Complete migration pipeline** |

### Understanding Each Test File

**[test_migrate_doi.py](test_migrate_doi.py)** - DOI Extraction

- Extracts DOI from `external_ids` array into top-level field
- Tests: basic extraction, missing/empty values, case preservation, multiple DOIs

**[test_merge_metadata.py](test_merge_metadata.py)** - Metadata Merging  

- Joins `works_metadata` using DOI match
- Tests: basic merging, partial metadata, missing matches, multiple works

**[test_enrich_institutions.py](test_enrich_institutions.py)** - Institution Enrichment

- Adds institution names from ORCID profiles to works
- Tests: basic mapping, array formatting, multiple works, unknown ORCIDs

**[test_link_contributors.py](test_link_contributors.py)** - Contributor Linking

- Matches contributor names to ORCID profiles
- Tests: name normalization, case-insensitive matching, hyphenated names, multiple contributors

**[test_add_author_count.py](test_add_author_count.py)** - Author Count

- Precomputes `author_count` from contributors array
- Tests: computing from array, empty/missing values, large lists, type handling

**[test_create_indexes.py](test_create_indexes.py)** - Index Creation

- Creates optimized database indexes for queries
- Tests: single indexes, compound indexes, NLP fields, sparse indexes

**[test_drop_unused_indexes.py](test_drop_unused_indexes.py)** - Index Removal  

- Removes obsolete indexes after migration
- Tests: dropping existing indexes, handling missing indexes, preserving others

**[test_run_all.py](test_run_all.py)** - Orchestration

- Tests the complete migration pipeline
- Tests: running migrations in sequence, error handling, result tracking

## How Mock Collections Work

The `mock_collection` fixture provides an in-memory MongoDB simulation:

```python
def test_example(mock_collection):
    # Mock collection starts empty
    mock_collection._documents = {}
    
    # Add test documents
    mock_collection._documents[1] = {
        "_id": 1,
        "orcid_id": "0000-0001-1111-1111",
        "doi": "10.1000/test"
    }
    
    # Call migration function
    result = my_migration(mock_collection)
    
    # Check results
    assert result["status"] == "success"
    assert "doi" in mock_collection._documents[1]
```

### Supported MongoDB Operations

| Operation | Supported | Notes |
| ----------- | ----------- | ------- |
| `find()` | YES | With filtering and projections |
| `insert_one()` | YES | With duplicate key detection |
| `update_one()` | YES | With upsert support |
| `count_documents()` | YES | With filtering |
| `aggregate()` | YES | Basic pipelines only |
| `create_index()` | YES | For index creation tests |
| `drop_index()` | YES | For index removal tests |
| `index_information()` | YES | Returns all created indexes |

### Why Use Mocks?

- **No setup required** - No MongoDB installation needed  
- **Fast** - In-memory operations complete in milliseconds  
- **Isolated** - Each test has its own collection  
- **Deterministic** - Same result every time  
- **Safe** - No real data at risk  

## Common Issues & Solutions

### Issue: `ModuleNotFoundError: No module named 'src'`

**Solution:** Make sure you're running pytest from the project root AND use `python -m pytest`:

```bash
cd /path/to/orcid-project
python -m pytest tests/data_migration/ -v
```

Using `python -m pytest` ensures the virtual environment's Python path is used. Do NOT run `pytest` directly or from the `tests/data_migration/` subdirectory.

### Issue: `ModuleNotFoundError: No module named 'pytest'`

**Solution:** Install pytest in your virtual environment:

```bash
# Activate virtual environment first
pip install pytest pytest-cov

# Verify installation
python -m pytest --version
```

### Issue: Tests fail with `KeyError` or assertion errors

**Solution:** This usually means the mock collection is not initialized correctly. Verify:

1. You're using the fixture: `def test_example(mock_collection):`
2. The fixture parameter name matches: `mock_collection`
3. Check the actual error message: `python -m pytest tests/data_migration/ -v -s`

### Issue: Tests run slowly or timeout

**Solution:** This is unusual - tests should complete in <1 second. Try:

```bash
# Run with timing information
python -m pytest tests/data_migration/ -v --durations=10

# Run with less verbose output
python -m pytest tests/data_migration/ -q
```

## Debugging & Development

### Run with Print Output

By default, pytest captures output. To see print statements:

```bash
# Show all print() output
python -m pytest tests/data_migration/ -v -s

# Show output only for failing tests
python -m pytest tests/data_migration/ -v --tb=short
```

### Debug a Single Test

```bash
# Run one test with output
python -m pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI::test_extract_doi_from_external_ids -v -s
```

### Add Debugging to Your Tests

```python
def test_something(mock_collection):
    # Setup
    mock_collection._documents[1] = {
        "_id": 1,
        "doi": "10.1000/test"
    }
    
    # Run migration
    result = migrate_doi(mock_collection)
    
    # Debug output
    print("\nDocuments:", mock_collection._documents)
    print("Result:", result)
    print("Indexes:", mock_collection._indexes)
    
    # Assert
    assert result["status"] == "success"
```

### Show Stack Traces for Failures

```bash
# Full traceback
python -m pytest tests/data_migration/ -v --tb=long

# Short traceback
python -m pytest tests/data_migration/ -v --tb=short

# Just the assertion error
python -m pytest tests/data_migration/ -v --tb=line
```

## Test Fixtures Reference

All tests use fixtures from [conftest.py](conftest.py):

### `mock_collection` - Mock MongoDB Collection

Provides in-memory MongoDB collection with these operations:

- `find()` - Query documents
- `insert_one()` - Insert with duplicate checking
- `update_one()` - Update or insert documents
- `count_documents()` - Count matching documents
- `aggregate()` - Run aggregation pipelines
- `create_index()` / `drop_index()` - Manage indexes
- `index_information()` - List all indexes

**Usage:**

```python
def test_example(mock_collection):
    # Collection is empty initially
    assert len(mock_collection._documents) == 0
    
    # Add test data
    mock_collection._documents[1] = {"_id": 1, "name": "Test"}
    
    # Use in migration
    result = migrate_doi(mock_collection)
    assert result["status"] == "success"
```

### `sample_orcid_documents`, `sample_works_documents`, `sample_metadata_documents`

Pre-defined sample data matching your actual schema. Used by fixtures to populate mock collections quickly.

## Next Steps After Tests Pass

When all 64 tests pass, you're ready to run migrations on a real database:

1. **Set up test MongoDB** (optional but recommended):

   ```bash
   # Create a free MongoDB Atlas account or use local MongoDB
   # Update .env with test database URI
   ```

2. **Run migrations on test database**:

   ```bash
   python -m src.data_migration.run_all
   ```

3. **Verify results** - Check that data was transformed correctly

4. **Backup production**:

   ```bash
   mongodump --uri="<PROD_URI>" --out=./backup_$(date +%s)
   ```

5. **Run migrations on production**:

   ```bash
   python -m src.data_migration.run_all
   ```

## Getting Help

- **Test details**: See individual test files (e.g., `test_migrate_doi.py`)
- **Migration logic**: See source files in `src/data_migration/`
- **Quick reference**: See [TESTING.md](TESTING.md)
