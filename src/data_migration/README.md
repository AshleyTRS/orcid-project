# Schema Migrations

## Overview

The `src/data_migration` package transforms the records produced by harvesting and enrichment into the analysis-ready form used by the analytics functions and the web application. Each migration adds or corrects fields in the `works` and `orcids` collections, or maintains indexes.

This document is the single guide to running and extending the migrations. Their unit tests are documented separately in [tests/data_migration/README.md](../../tests/data_migration/README.md).

## Principles

- **Fixed order.** Later migrations depend on fields written by earlier ones, so the complete sequence is always executed through `run_all.py`.
- **Uniform interface.** Every migration is a function that receives the collections it needs and returns a status dictionary (`{"status": "success", ...}` or `{"status": "error", "message": ...}`). The runner logs each result and continues after a failure.
- **Idempotency.** Every migration can be executed again on data it has already processed without corrupting it.
- **Non-destructive changes.** Migrations add or update fields and indexes. No migration deletes documents.

## Running the Migrations

All commands are executed from the project root with the virtual environment active. They modify the database named by `DB_NAME` in `.env`; a backup should be created first (see [scripts/db_dumps/DUMP_README.md](../../scripts/db_dumps/DUMP_README.md)).

### Complete sequence

```bash
python -m src.data_migration.run_all
```

The sequence should be executed after every harvest or enrichment run, before the data is analysed.

### Procedure for a change to a migration

The unit tests verify the transformation logic with mocked collections; a trial on real data is required in addition. The recommended procedure is:

1. Run the unit tests: `python -m pytest tests/data_migration/ -v`.
2. Create a backup.
3. Point `DB_NAME` in `.env` to a test copy of the database and execute `python -m src.data_migration.run_all`.
4. Inspect the results, restore `DB_NAME`, and execute the sequence against the production database.

### Individual migrations

Each module can be executed on its own with `python -m src.data_migration.<module>`. This is intended for repeating a single step, for example after a correction; the dependencies listed below must already be satisfied.

| Command | Runs |
| --- | --- |
| `python -m src.data_migration.migrate_doi` | `migrate_doi` |
| `python -m src.data_migration.enrich_institutions` | `enrich_institutions` |
| `python -m src.data_migration.link_contributors` | `link_contributors` |
| `python -m src.data_migration.add_work_key` | `add_work_key` |
| `python -m src.data_migration.add_author_count` | `add_author_count` |
| `python -m src.data_migration.create_indexes` | `create_indexes` |
| `python -m src.data_migration.drop_unused_indexes` | `drop_unused_indexes` |
| `python -m src.data_migration.merge_metadata` | `check_works_count` (not `merge_metadata`; see below) |

The module `merge_metadata` contains steps 2 and 3, which have no command of their own; they run as part of the complete sequence.

---

## The Sequence

| Step | Migration | Reads | Writes | Depends on |
| --- | --- | --- | --- | --- |
| 1 | `migrate_doi` | `works.external_ids` | `works.doi` | Harvested works |
| 2 | `merge_metadata` | `works_metadata` | `works.concepts`, `works.keywords`, `works.topics` | Step 1, enrichment |
| 3 | `merge_open_access` | `works_metadata.open_access` | `works.is_oa`, `works.oa_url` | Step 1, enrichment |
| 4 | `enrich_institutions` | `orcids.institution_names` | `works.institutions` | Harvested profiles |
| 5 | `link_contributors` | `orcids` names, `works.contributors` | `works.contributors[].orcid_id` | Harvested profiles |
| 6 | `add_work_key` | `works`, `orcids` | `works.work_key`, `orcids.unique_works_count`, indexes | Steps 1 and 5 |
| 7 | `add_author_count` | `works.contributors` | `works.author_count` | Harvested works |
| 8 | `create_indexes` | none | Indexes on `works` | Steps 1 to 7 |
| 9 | `drop_unused_indexes` | none | Removes obsolete indexes | Step 8 |

### 1. `migrate_doi`

Copies the value of the first entry of type `doi` in `external_ids` into a top-level `doi` field, so that DOIs can be indexed and matched without traversing the array. The value is copied as stored; normalization for matching takes place in `add_work_key`.

### 2. `merge_metadata`

For each work with a DOI, copies `concepts`, `keywords` and `topics` from the corresponding `works_metadata` document. Analytical queries can then filter and group by subject without joining collections. Works without a DOI, and works whose DOI was not found in OpenAlex, receive no metadata.

### 3. `merge_open_access`

For each work with a DOI, copies `is_oa` and, when present, `oa_url` from the `open_access` object of the `works_metadata` document with the same DOI. The metadata is read in one query and only works whose values change are written, in bulk; on the current data the step takes about 3 seconds, and a repeated execution writes nothing. The step joined the sequence in October 2026; before that, open-access information was updated only when the function was called by hand.

### 4. `enrich_institutions`

Copies the affiliations listed on the record owner's ORCID profile (`institution_names`) into each work as `institutions`, an array of objects with a `name` field. The field describes the researcher's affiliations at harvest time, not the affiliation stated on the publication.

### 5. `link_contributors`

Builds a map from normalized researcher names (given and family names of each stored profile) to ORCID iDs and assigns the matching ORCID iD to contributors that do not yet have one. Both sides of the comparison are normalized by `src/works/names.py`, the function the harvester applies to contributor names: accents are removed, case is folded, hyphens and commas become spaces, and other punctuation is dropped, so "García-López" and "Garcia Lopez" match. If no `normalized_name` is stored for a contributor, the credited name is normalized instead.

Three rules prevent incorrect links:

- A name shared by two or more profiles is ambiguous and is not used. The current data contains 30 such names, each shared by two profiles; in 26 pairs the two profiles share an affiliation and in 25 one of them lists no works, which suggests that most pairs are one researcher holding two ORCID iDs.
- A contributor that already carries an ORCID iD, for example one supplied by ORCID itself, is never changed.
- Matching requires the complete normalized name; a partial name such as a given name alone does not match.

Matching remains exact on the normalized name. A contributor credited in a different form (for example "Ramírez-Cruz, E.S.") is not linked, and a researcher outside the stored profiles who has exactly the same name as a stored researcher would be linked to that researcher.

Before October 2026 the profile side kept accents and deleted hyphens while the contributor side removed accents and replaced hyphens with spaces, so names with accents or hyphens never matched. Applying the corrected migration on 3 October 2026 produced the following changes (complete backup taken beforehand):

| Measure | Before | After |
| --- | --- | --- |
| Contributor entries linked to a profile | 19,961 | 37,601 |
| Work records with a linked contributor | 9,710 | 15,444 |
| Distinct works with a linked contributor | 6,372 | 9,783 |
| Profiles linked as a contributor | 1,561 | 2,236 |
| Profiles with accented or hyphenated names linked | 688 of 2,822 (24.4 percent) | 1,363 of 2,822 (48.3 percent) |
| Profiles with unaccented names linked | 873 of 2,564 (34.0 percent) | 873 of 2,564 (34.0 percent) |
| Sum of `unique_works_count` over all profiles | 29,639 | 31,440 |
| Co-authorship network 2020 to 2026: researchers | 4,656 | 4,883 |
| Co-authorship network 2020 to 2026: collaborations | 42,676 | 44,256 |

All new links concern profiles with accented or hyphenated names; the figures for unaccented names are unchanged. Writes are batched, and a repeated execution on unchanged data changes nothing.

### 6. `add_work_key`

Assigns to every work a `work_key` that identifies the publication it describes, creates the indexes `work_key` and (`orcid_id`, `work_key`) on `works` and (`unique_works_count` descending, `orcid_id`) on `orcids`, and recomputes `orcids.unique_works_count`. The rules are implemented in `src/works/work_key.py` and explained in [ARCHITECTURE.md](../../ARCHITECTURE.md#3-work-identity). Only documents whose key or count changes are written, so a repeated execution on unchanged data reports zero updates. The step must follow step 5, because unique works counts include works on which a researcher is a linked contributor.

### 7. `add_author_count`

Stores the length of the `contributors` array as `author_count`, so that aggregations can filter and average by number of contributors without computing array sizes.

### 8. `create_indexes`

Creates the indexes used by the analytical queries on `works`: `doi`, `publication_year`, `type`, `author_count`, (`publication_year`, `type`), (`orcid_id`, `publication_year`), `contributors.orcid_id`, (`contributors.orcid_id`, `publication_year`), `institutions.name`, `topics.display_name`, `concepts.display_name` and `orcid_id`. Most are sparse, so documents without the field are not indexed.

### 9. `drop_unused_indexes`

Removes the index on `contributors.normalized_name`, which no query uses after contributor linking. Indexes that do not exist are skipped.

---

## Maintenance Function Outside the Sequence

`check_works_count(orcids, works)` in `merge_metadata.py` sets `orcids.works_count` to the number of stored records of each profile and then recomputes `unique_works_count` for every researcher. It is not part of `run_all.py` and runs with:

```bash
python -m src.data_migration.merge_metadata
```

---

## Adding a Migration

1. Create `src/data_migration/<name>.py` with a function that receives the required collections and returns a status dictionary, following the existing modules. Add a `__main__` block if the step should be executable on its own.
2. Register the function in `MigrationRunner.run_all()` in `run_all.py` at the position its dependencies require, and update the numbered list in the module docstring.
3. Add `tests/data_migration/test_<name>.py`, and update `test_run_all.py` as described in [tests/data_migration/README.md](../../tests/data_migration/README.md#adding-a-migration).
4. Update the sequence table in this document and the corresponding table in [README.md](../../README.md#stage-4-prepare-the-data-for-analysis).

## Troubleshooting

| Symptom | Cause and remedy |
| --- | --- |
| `ModuleNotFoundError: No module named 'src'` | The command was executed outside the project root, or without `-m`. Execute `python -m src.data_migration.<module>` from the project root. |
| `Missing MONGO_CONN or DB_NAME environment variables` | The `.env` file is absent or incomplete. |
| One step reports `error` and the others succeed | The runner continues after failures by design. Correct the cause given in the log and execute the failed step on its own, or the complete sequence again. |
| Unique works counts are outdated after a harvest | Execute the complete sequence, or `python -m src.data_migration.add_work_key`. |
| Open-access buttons do not reflect a new enrichment | Execute the complete sequence, which includes `merge_open_access` as step 3. |
