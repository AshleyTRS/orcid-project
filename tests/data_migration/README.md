# Data Migration Test Suite

## Overview

This directory contains 98 unit tests for the schema migrations in `src/data_migration/` and for the work identity rules in `src/works/work_key.py`. It documents testing only; running the migrations against a database is described in [src/data_migration/README.md](../../src/data_migration/README.md). The tests replace MongoDB collections with in-memory mocks, so they require no database connection and no network access. The complete suite runs in under one second.

The suite verifies the transformation logic of each migration: the fields written, the handling of missing and malformed values, error reporting, and the orchestration of the migration sequence. It does not verify behaviour that depends on a real MongoDB server, such as index usage or the evaluation of complex aggregation pipelines.

## Prerequisites

- Python 3.12 or later, with the project's virtual environment activated.
- `pytest`; `pytest-cov` is required only for coverage reports.

```bash
pip install pytest pytest-cov
```

## Commands

| Purpose | Command |
| --- | --- |
| Run all tests | `python -m pytest tests/data_migration/ -v` |
| Run one file | `python -m pytest tests/data_migration/test_add_work_key.py -v` |
| Run tests matching a name | `python -m pytest tests/data_migration/ -k "doi" -v` |
| Coverage report | `python -m pytest tests/data_migration/ --cov=src.data_migration --cov=src.works.work_key --cov-report=html` |
| Show output of `print` | `python -m pytest tests/data_migration/ -v -s` |

## Running the Tests

Execute the suite from the project root with `python -m pytest`, which places the project root on the module search path so that `src` can be imported:

```bash
python -m pytest tests/data_migration/ -v
```

Expected result:

```txt
98 passed in 0.18s
```

Only `tests/data_migration/` contains unit tests. The other files in `tests/` (`test_mongo_conn.py`, `test_unique_dois.py`, `get_orcid.py`, `harvest_works_test.py`, `search_orcids_test.py`) are manual scripts that connect to the configured database or to the ORCID API when imported. Running `pytest tests/` would execute them as well, so the directory should always be given explicitly.

### Selecting tests

```bash
# One file
python -m pytest tests/data_migration/test_add_work_key.py -v

# One class or one test
python -m pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI -v
python -m pytest tests/data_migration/test_migrate_doi.py::TestMigrateDOI::test_extract_doi_from_external_ids -v

# Tests whose names match an expression
python -m pytest tests/data_migration/ -k "doi" -v
```

### Coverage

```bash
python -m pytest tests/data_migration/ --cov=src.data_migration --cov=src.works.work_key --cov-report=html
```

The report is written to `htmlcov/index.html`. Branches that depend on database behaviour which the mocks do not reproduce are reported as uncovered; complete coverage of those branches requires integration tests against a MongoDB instance.

## Test Files

| File | Tests | Subject |
| --- | --- | --- |
| `test_migrate_doi.py` | 7 | Extraction of the DOI from `external_ids` into the `doi` field |
| `test_merge_metadata.py` | 6 | Copying of OpenAlex `concepts`, `keywords` and `topics` into works |
| `test_merge_open_access.py` | 5 | Copying of open-access status and location; unchanged data writes nothing |
| `test_enrich_institutions.py` | 5 | Copying of ORCID affiliations into works as `institutions` |
| `test_link_contributors.py` | 22 | Shared name normalization, ambiguous names, preservation of existing links, linking verified on the stored documents |
| `test_add_work_key.py` | 20 | Work identity rules and the `add_work_key` migration |
| `test_add_author_count.py` | 8 | Computation of `author_count` |
| `test_create_indexes.py` | 11 | Creation of single, compound and sparse indexes |
| `test_drop_unused_indexes.py` | 7 | Removal of obsolete indexes and handling of absent ones |
| `test_run_all.py` | 7 | Execution order, result reporting and continuation after failures |
| Total | 98 | |

### Work identity tests (`test_add_work_key.py`)

The work identity rules are pure functions and are tested directly, without mocks:

| Class | Verified behaviour |
| --- | --- |
| `TestNormalizeDoi` | Removal of resolver prefixes and the `doi:` label, lower-casing, rejection of values that are not DOIs |
| `TestNormalizeTitle` | Removal of inline markup without splitting words, preservation of word boundaries around tags, independence of accents, case and punctuation |
| `TestComputeWorkKey` | Equal keys for records that differ only in `put_code` or DOI case; DOI read from `external_ids`; long titles merged across researchers; short titles scoped to their owner; fallback key for records without DOI and title |
| `TestAssignWorkKeys` | Linking of a record without a DOI to the same researcher's DOI record; no linking across years, across researchers, or when a title corresponds to two DOIs |
| `TestUniqueWorksStages` | Aggregation stages that keep one document per work, or per owner and work |
| `TestAddWorkKeyMigration` | Reported counts, creation of the indexes on `works` and `orcids`, and the error status when the migration fails |

## Mock Collections

`conftest.py` provides the fixtures used by the tests.

| Fixture | Content |
| --- | --- |
| `mock_collection` | An in-memory collection supporting `find`, `insert_one` (with duplicate key detection), `update_one` (with upsert), `count_documents`, a subset of `aggregate`, `create_index`, `drop_index` and `index_information` |
| `sample_orcid_documents`, `sample_works_documents`, `sample_metadata_documents` | Sample documents with the structure of the production collections |
| `populate_mock_collection` | Fills a mock collection with one of the sample sets |

Documents are held in `mock_collection._documents` and indexes in `mock_collection._indexes`, which tests may inspect directly:

```python
def test_doi_is_extracted(mock_collection):
    mock_collection._documents[1] = {
        "_id": 1,
        "external_ids": [{"type": "doi", "value": "10.1000/test"}],
    }

    result = migrate_doi(mock_collection)

    assert result["status"] == "success"
```

Tests of `add_work_key` replace the database functions `apply_work_keys` and `update_unique_works_counts` with `unittest.mock.patch`, because these functions issue bulk writes and aggregation pipelines that the mock collection does not reproduce.

## Adding a Migration

The code side of a new migration is described in [src/data_migration/README.md](../../src/data_migration/README.md#adding-a-migration). On the test side, two changes keep the suite complete:

1. A test file `test_<migration>.py` covering the fields written, missing or malformed input, and the error status.
2. An additional `@patch` decorator and updated totals in `test_run_all.py::TestMigrationRunner::test_run_all_migrations_success`, which asserts the number of migrations executed.

## Troubleshooting

| Symptom | Cause and remedy |
| --- | --- |
| `ModuleNotFoundError: No module named 'src'` | The tests were started with `pytest` from another directory. Run `python -m pytest tests/data_migration/` from the project root. |
| `ModuleNotFoundError: No module named 'pytest'` | Install `pytest` in the active virtual environment. |
| Tests attempt a database connection | `pytest` was run on `tests/` instead of `tests/data_migration/`. |
| `test_run_all_migrations_success` fails after adding a migration | The new migration is not patched in that test, or the expected total was not updated. |
