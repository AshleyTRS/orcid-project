# UAEH Researchers Network: Scholarly Data Harvesting, Enrichment and Analysis

## Overview

This project implements an API-based system for the retrieval, enrichment, storage and analysis of researcher profiles and scholarly publications associated with the Universidad Autónoma del Estado de Hidalgo (UAEH). The system operates in four stages:

1. **Harvesting.** Researcher profiles and their scholarly works are retrieved from the ORCID public API.
2. **Enrichment.** Works that carry a DOI are enriched with metadata from the OpenAlex API (topics, concepts, keywords and open-access status).
3. **Preparation.** A sequence of schema migrations transforms the raw records into an analysis-ready dataset, including the identification of duplicate records that describe the same publication.
4. **Analysis and presentation.** MongoDB aggregation pipelines compute publication statistics, and a Flask web application presents researcher search, individual author profiles and an interactive co-authorship network.

The architecture separates query management, retrieval, parsing, normalization, persistence and presentation into independent modules. The objective is a structured and reproducible workflow for collecting and analysing institution-level scholarly output while respecting the usage policies of the external APIs.

The project is developed for academic purposes and collects data exclusively through public API endpoints.

### Background

**ORCID.** An ORCID iD (Open Researcher and Contributor ID) is a free, persistent 16-digit identifier for researchers. It distinguishes researchers with similar names, provides each researcher with a portable profile, and links that profile to their scholarly works. The [ORCID](https://orcid.org/) registry allows institutions to follow the contributions of their researchers with less administrative effort and fewer transcription errors.

**DOI.** A Digital Object Identifier is a persistent identifier assigned to a scholarly object such as a journal article, book chapter or conference paper. It resolves through <https://doi.org/> to the current location of the object, independently of changes in hosting. In this project the DOI is the key that links ORCID works to OpenAlex metadata, and the primary criterion for recognising two records as the same publication.

**OpenAlex.** [OpenAlex](https://openalex.org/) is an open catalogue of scholarly works, authors and institutions. The system queries it by DOI to obtain subject classifications, keywords and open-access locations.

### Motivation

ORCID and OpenAlex are global registries. Their scope introduces considerable overhead when an institution needs to analyse only the output of its own academic community, because neither registry is organized around institutional boundaries. Institution-level analysis therefore requires the selective retrieval and processing of records.

This project provides a structured, API-based system through which an institution can independently collect, process and store data about its researchers and their works, and then analyse that data locally for reporting and evaluation, while relying on the standardized identifiers that ORCID and DOI provide.

---

## Requirements

### Software

| Component | Version | Purpose |
| --- | --- | --- |
| Python | 3.12 or later (developed with 3.13.2) | Runtime |
| `requests` | 2.32.5 | HTTP communication with the ORCID and OpenAlex APIs |
| `pymongo` | 4.16.0 | MongoDB access |
| `dnspython` | 2.8.0 | DNS resolution for MongoDB Atlas connection strings |
| `python-dotenv` | 1.2.1 | Loading of environment variables |
| `Flask` | 3.0.0 | Web application and HTTP API |
| `Flask-CORS` | 4.0.0 | Cross-origin request headers for the HTTP API |

The web pages load Chart.js 4.4.0 and D3.js 7 from public CDNs, so a browser with internet access is required to display charts and the network graph.

### Database

All persistent data is stored in a MongoDB Atlas cluster. Connection parameters are supplied through environment variables and are never written into the source code. Apart from optional backups and reports, the system writes no application data to the local filesystem.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/AshleyTRS/orcid-project.git
cd orcid-project
```

### 2. Create a virtual environment

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```bash
ACCESS_TOKEN=<ORCID API access token>
MONGO_CONN=<MongoDB connection string>
DB_PASSWORD=<MongoDB password>
DB_NAME=<MongoDB database name>
```

`ACCESS_TOKEN` is required only by the harvesting scripts. The web application and the migrations require `MONGO_CONN` and `DB_NAME`.

---

## Execution

All commands are executed from the project root so that the `src` package resolves correctly. The stages are listed in the order in which a complete dataset is produced.

### Stage 1. Harvest ORCID profiles

```bash
python -m scripts.harvest_orcids
```

Discovers researcher profiles through partitioned ORCID search queries and stores them in the `orcids` collection.

### Stage 2. Harvest scholarly works

```bash
python -m scripts.harvest_works
```

Retrieves every work listed on each stored profile that has not yet been harvested and stores one document per ORCID work entry (`put_code`) in the `works` collection. Each document receives a `work_key` at insertion time, and after each profile is harvested the duplicate records of that profile are linked and its unique works count is refreshed (see [Work identity](#work-identity-and-deduplication)).

### Stage 3. Enrich works with OpenAlex metadata

```bash
python -m scripts.enrich_data_openalex
```

Queues the distinct DOIs of harvested works, queries OpenAlex for each, normalizes the responses and stores them in the `works_metadata` collection. Requests are spaced by 0.1 seconds (at most ten per second). A failed lookup is recorded and does not interrupt the run.

### Stage 4. Prepare the data for analysis

```bash
python -m src.data_migration.run_all
```

Executes the schema migrations in a fixed order:

| Step | Migration | Effect |
| --- | --- | --- |
| 1 | `migrate_doi` | Copies the DOI from the nested `external_ids` array into a top-level `doi` field |
| 2 | `merge_metadata` | Copies OpenAlex `concepts`, `keywords` and `topics` into each work, matched by DOI |
| 3 | `merge_open_access` | Copies the open-access status and location (`is_oa`, `oa_url`) into each work, matched by DOI |
| 4 | `enrich_institutions` | Copies the researcher's ORCID affiliations into each work as `institutions` |
| 5 | `link_contributors` | Links contributors to stored ORCID profiles by normalized name |
| 6 | `add_work_key` | Assigns `work_key` to every work and computes `unique_works_count` for every researcher |
| 7 | `add_author_count` | Stores the number of contributors of each work as `author_count` |
| 8 | `create_indexes` | Creates the indexes used by the analytical queries |
| 9 | `drop_unused_indexes` | Removes indexes made obsolete by earlier steps |

Each migration logs its progress and returns a status summary. A failed migration is reported and the remaining migrations still run. Every migration can be re-executed safely.

One maintenance function, `check_works_count`, which reconciles the stored works counts, is not part of the sequence. The migrations, their dependencies, the commands for running individual steps and the maintenance function are documented in [src/data_migration/README.md](src/data_migration/README.md).

### Stage 5. Run the web application

```bash
python run.py
```

Starts the Flask development server in debug mode at <http://127.0.0.1:5000>. Python files and templates reload automatically when they change. The server is stopped with `Ctrl+C`.

| Page | Address | Description |
| --- | --- | --- |
| Search | `/` | Search researchers and works, with filters and summary charts |
| Author profile | `/author/<orcid>` | Profile, statistics and complete list of an author's works |
| Co-authorship network | `/network` | Filtered collaboration graph, built on request |
| API viewer | `/json_view` | Raw JSON output of the co-authorship endpoint |

The HTTP endpoints used by these pages are documented in [API_REFERENCE.md](API_REFERENCE.md).

### Auxiliary scripts

| Command | Purpose |
| --- | --- |
| `python scripts/analyze_publications.py` | Prints publication statistics and writes them to `reports/publication_analysis.json` |
| `python scripts/db_dumps/dump_database.py` | Creates a `mongodump` backup in `backups/` (requires the MongoDB Database Tools) |
| `python scripts/db_dumps/dump_database_pymongo.py` | Creates a JSON backup of every collection in `backups/` |
| `python -m scripts.reset_orcids` | Marks all profiles as not harvested so that Stage 2 retrieves their works again |
| `python scripts/coauthorship_api.py` | Standalone server for the co-authorship network; superseded by `run.py`, which serves the same endpoints together with the other pages |

Backups are described in [scripts/db_dumps/DUMP_README.md](scripts/db_dumps/DUMP_README.md).

---

## Repository Structure

```txt
run.py                       Entry point of the web application
src/
  app/                       Flask application: page routes and HTTP API
  analytics/                 Aggregation pipelines (search, statistics, author profiles)
  coauthorship/              Co-authorship network model and construction
  data_enrichment/           OpenAlex enrichment pipeline
    metadata/                Enrichment orchestration and DOI queue
    openalex/                OpenAlex client, normalization, abstract reconstruction
    storage/                 Persistence of enriched metadata
  data_migration/            Schema migrations (see Stage 4)
  db/                        MongoDB connection
  orcid/                     ORCID profile discovery
    search/                  Search client, query partitioning, discovery engine
    models/                  Researcher profile model
    storage/                 Persistence of profiles and query partitions
  works/                     ORCID works harvesting
    harvest/                 Work retrieval and parsing
    models/                  Work model
    storage/                 Persistence of works
    work_key.py              Work identity rules shared by harvesting, migrations and queries
templates/                   HTML pages (Jinja2) and the shared header
static/
  styles/main.css            Shared stylesheet and design tokens
  js/uaeh-institutes.js      List of UAEH institutes used by the sub-institution filters
scripts/                     Command-line workflows (harvesting, enrichment, reports, backups)
tests/
  data_migration/            Unit tests for the migrations and work identity
```

---

## Data Model

The database contains five collections.

| Collection | Documents (3 October 2026) | Content |
| --- | --- | --- |
| `orcids` | 5,386 | Researcher profiles: names, affiliations, harvest state, `works_count`, `unique_works_count` |
| `works` | 34,662 | One document per ORCID work entry, enriched by the migrations |
| `works_metadata` | 12,632 | OpenAlex metadata, one document per DOI and source |
| `metadata_queue` | 13,473 | DOIs pending or processed for enrichment |
| `partitions` | 26 | State of the partitioned ORCID search queries |

### Fields added to `works` by the pipeline

| Field | Added by | Description |
| --- | --- | --- |
| `doi` | `migrate_doi` | DOI taken from `external_ids`, for direct lookup and joins |
| `concepts`, `keywords`, `topics` | `merge_metadata` | OpenAlex classifications, copied to avoid joins during analysis |
| `is_oa`, `oa_url` | `merge_open_access` | Open-access status and the best open-access location |
| `institutions` | `enrich_institutions` | Affiliations of the record owner, as objects with a `name` field |
| `contributors[].normalized_name`, `contributors[].orcid_id` | `link_contributors` | Normalized names and links to stored profiles |
| `work_key` | harvester and `add_work_key` | Identity shared by all records of the same publication |
| `author_count` | `add_author_count` | Number of contributors |

### Fields of `orcids` used for counts

| Field | Meaning |
| --- | --- |
| `works_count` | Number of work records stored for the profile, duplicates included |
| `unique_works_count` | Number of distinct works of the researcher: works on the researcher's own ORCID record together with works on other records that list the researcher as a linked contributor, each counted once |

### Work identity and deduplication

The `works` collection holds one document per ORCID work entry. The same publication therefore appears several times: once on the record of every co-author who has an ORCID iD, and frequently several times on a single record, because ORCID keeps one entry for each source that imported the work (each with its own `put_code`). In the current dataset 5,667 documents repeat a work already present on the same researcher's record, and 34,662 documents describe 21,770 distinct works.

Every document carries a `work_key`, and all statistics count distinct keys rather than documents. The rules, implemented in `src/works/work_key.py`, are applied in order:

1. `doi:<doi>`: the DOI from `doi` or `external_ids`, without resolver prefix and in lower case.
2. A record without a DOI whose normalized title and year match exactly one DOI record of the same researcher receives that DOI key.
3. `title:<title>|<year>`: the normalized title (markup, accents, case and punctuation removed) and the year. Titles shorter than 40 characters are scoped to the record owner, so that generic titles such as "Editorial" are never merged across researchers.
4. `put:<orcid>:<put_code>`: a record with neither DOI nor title is its own work.

Documents are never deleted: the `put_code` is ORCID's identifier, and a later harvest would recreate any deleted entry. A detailed account of the problem, the measurements and the alternatives considered is given in [ARCHITECTURE.md](ARCHITECTURE.md#3-work-identity).

---

## Testing

```bash
python -m pytest tests/data_migration/ -v
```

The suite contains 98 unit tests for the migrations and the work identity rules. It uses mocked collections, requires no database and completes in under one second. Details are given in [tests/data_migration/README.md](tests/data_migration/README.md).

---

## Scope and Design Considerations

### Data sources

- The system uses only the official public APIs of ORCID and OpenAlex. No web crawling or HTML scraping is performed.
- Request rates are limited by fixed delays between requests (0.1 seconds for both APIs).

### Architecture

- ORCID discovery partitions its search queries to control request volume.
- Persistence is handled by dedicated storage classes, separate from retrieval and orchestration.
- DOIs are normalized consistently so that harvested works and OpenAlex metadata match reliably.
- Work identity is defined once, in `src/works/work_key.py`, and used by the harvester, the migrations, the web application and the report functions.

### Extensibility

- The enrichment pipeline accepts additional metadata sources through the same normalization and storage interfaces.
- Storage and API clients are separate classes, so an implementation can be replaced without changing the orchestration logic.

---

## Limitations

### Data completeness

- 9,439 of the 34,662 work records (27.2 percent) have no DOI. These works cannot be matched to OpenAlex and carry no topics, keywords or open-access information. Analyses of subjects or open access describe only the DOI-bearing subset.
- 19,878 records (57.3 percent) carry OpenAlex topics.
- 3,079 of the 5,386 harvested profiles list no works on ORCID and appear with a count of zero.
- 411 records have no publication year and one record has the year 0. Year-based statistics exclude them; the earliest plausible year in the dataset is 1969.

### Temporal validity

The dataset is a snapshot. ORCID records and OpenAlex metadata continue to change after harvesting, and corrections made at the source are reflected only after a new harvest and enrichment.

### Work identity

- Matching by title and year requires an exact match after normalization. Two records of the same work whose titles differ in wording, or whose years differ, remain separate.
- Records of one work occasionally disagree on the publication year. Year-based counts assign such a work to the latest of its years within the requested range, so the count of a given year can vary slightly with the range requested.
- Distinct versions of a work that carry distinct DOIs (for example, a preprint and the published article, or the version DOI and the concept DOI of a Zenodo record) are counted as distinct works.

### Institutional affiliation

The `institutions` field reproduces the affiliations listed on the researcher's ORCID profile at harvest time. It does not record the affiliation stated on each individual publication and does not track changes of affiliation over time. Most profiles name the university without the institute or school, so filters by sub-institution return the subset of works whose affiliation text names that unit.

### Contributor linking

Collaboration statistics consider only contributors who are linked to a stored ORCID profile. Co-authors without an ORCID iD, or whose profile was not harvested, do not appear in the co-authorship network.

Linking is performed by exact comparison of normalized names. A contributor credited in a different form, such as initials or inverted order, remains unlinked, and names shared by two stored profiles are not used. Until October 2026 names containing accents or hyphens never matched, because the two sides of the comparison were normalized differently. After the correction, the share of profiles with such names that are linked as contributors rose from 24.4 to 48.3 percent, and the number of linked contributor entries from 19,961 to 37,601. The procedure and the complete before-and-after figures are given in [src/data_migration/README.md](src/data_migration/README.md#5-link_contributors).

### Open-access information

Open-access fields are updated by step 3 of the migration sequence from the most recent OpenAlex enrichment. About 37 percent of the stored open-access links point directly to a PDF or download; the remainder point to publisher or DOI landing pages.

---

## Documentation

| Document | Content |
| --- | --- |
| [README.md](README.md) | Overview, installation, execution, data model and limitations |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, work identity, web application design and design decisions |
| [API_REFERENCE.md](API_REFERENCE.md) | HTTP endpoints of the web application |
| [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) | Index of all project documents |
| [src/data_migration/README.md](src/data_migration/README.md) | Schema migrations: order, effects, commands and maintenance functions |
| [src/analytics/README.md](src/analytics/README.md) | Aggregation and author profile functions |
| [src/coauthorship/README.md](src/coauthorship/README.md) | Co-authorship network construction |
| [tests/data_migration/README.md](tests/data_migration/README.md) | Unit test suite |
| [scripts/db_dumps/DUMP_README.md](scripts/db_dumps/DUMP_README.md) | Database backup and restoration |
