# Scholarly Data Harvesting and Enrichment System

## Overview

This project implements a multi-stage API-based system for the retrieval, processing, enrichment, and storage of researcher information and scholarly publications. The system operates in two primary stages:

1. **Data Harvesting**: Retrieves researcher profiles and associated scholarly works from the ORCID platform.
2. **Metadata Enrichment**: Augments harvested works with comprehensive metadata from the OpenAlex API.

The system is designed following a modular architecture that separates query management, data retrieval, parsing, normalization, and persistence. Its primary objective is to provide a structured and reproducible workflow for collecting and enriching ORCID-related data while respecting API constraints and good software engineering practices.

The project is intended for academic purposes and uses public API endpoints to ethically collect and process scholarly data.

### What is the ORCID platform?

An ORCID (Open Research and Contributor ID) is a free, unique, 16-digit persistent digital identifier for research professionals and students that solves the problem of distinguishing reserachers and their works throughout their careers. ORCID prevents confusion caused by name ambuity, creates a portable profile for each researcher that owns one, connects to other research repositories, and ensures authors get proper attribution for published works. The [ORCID](https://orcid.org/) platform permits universities and research institutions stay up to date with their researcher's contributions and publications, reducing the administrative burden and input errors and improving the discoverability of reseachers, employees, and students.

### What is DOI?

A DOI (Digital Object Identifier) is a standardized, persistent alphanumeric string assigned to digital scholarly content such as journal articles, book chapters, and conference papers. It provides a permanent and reliable way to identify and locate academic works on the internet, regardless of changes in their URL or hosting platform.

The DOI system ensures that each publication can be uniquely referenced and accessed through a consistent resolution mechanism, typically via the <https://doi.org/> resolver. This makes DOIs essential for citation, data integration, and interoperability between scholarly systems.

In the context of this project, DOIs serve as the primary key for linking data between the ORCID platform and OpenAlex metadata, enabling accurate enrichment of publications and consolidation of information across multiple sources.

### Motivation

The motivation for this project arises from the difficulty of establishing a clear and reliable association between a specific academic institution and the scholarly output of its researchers. Although ORCID and OpenAlex serve as a global registry that aggregates researcher identities and scholarly works worldwide, its comprehensive scope introduces significant overhead when an institution seeks to extract and analyze information relevant only to its own academic community.

In practice, institutional-level analysis requires the selective retrieval and processing of scholarly data, as the platform is not inherently organized around institutional boundaries. This project addresses that challenge by providing a structured, API-based system that enables individual institutions to independently collect, process, and store data related to their researchers and associated scholarly works.

By facilitating institution-focused data harvesting, the system supports localized analysis, reporting, and evaluation, while leveraging the global coverage and standardized identifiers provided by ORCID.

---

## Tools and Versions

### Programming Language

- Python 3.12 or later (tested with Python 3.13)

### External Libraries

- `requests==2.32.5`  
  Used for HTTP communication with external APIs (ORCID and OpenAlex).
- `pymongo==4.16.0`  
  Used for data persistence in MongoDB.
- `dnspython==2.8.0`  
  Required for DNS resolution when using MongoDB Atlas.
- `python-dotenv==1.2.1`  
  Used to manage environment variables.

### Database System

This project uses MongoDB Atlas as its database backend. All persistent data generated during execution is stored in a cloud-hosted MongoDB instance. No application data is written to or persisted on the local filesystem, aside from temporary runtime artifacts.

Database connection parameters are managed through environment variables and are not hardcoded into the source code.

---

## Development Environment Configuration

### 1. Repository Setup

Clone the repository and navigate to the project root:

```bash
git clone https://github.com/AshleyTRS/orcid-project.git
cd orcid-project
```

### 2. Python Virtual Environment

A virtual environment is recommended to isolate project dependencies.

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Dependency Installation

Install the required libraries using the provided requirements file:

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the project root directory with the following structure:

```bash
ACCESS_TOKEN = <your-ORCID-API-access-token>
MONGO_CONN = <your-mongo-db-uri>
DB_PASSWORD = <your-mongo-db-password>
DB_NAME = <your-mongo-db-name>
```

The values may be adjusted depending on the execution environment and database configuration.

---

## Execution

The system is implemented entirely in Python and is executed using the Python interpreter. Proper execution depends on correct environment configuration and dependency installation.

Overmore, all executable workflows are located in the `scripts/` directory.
Scripts must be executed from the project root to ensure correct module resolution.

### Harvest ORCID Profiles

```bash
python -m scripts.harvest_orcids
```

This script retrieves ORCID researcher profiles and stores them in the database.

### Harvest Scholarly Works

```bash
python -m scripts.harvest_works
```

This script retrieves research contributions or published works associated with previously stored ORCID profiles.

### Enrich Metadata from OpenAlex

```bash
python -m scripts.enrich_data
```

This script enriches harvested scholarly works with comprehensive metadata from the OpenAlex API. It orchestrates a multi-step enrichment pipeline:

1. Extracts unique DOIs from previously harvested works
2. Queries the OpenAlex API for detailed metadata
3. Normalizes and processes API responses
4. Persists enriched metadata to the database

The enrichment pipeline includes robust error handling to ensure continuous processing even when individual DOI lookups fail, and respects OpenAlex API rate limits (~10 requests per second).

### Prepare Data for Analysis (Schema Migration)

```bash
python src/data_migration/run_all.py
```

This script executes a series of schema transformation migrations to prepare the raw harvested and enriched data for analytical workloads:

1. **migrate_doi** - Extracts DOI from nested external_ids array for efficient lookup
2. **merge_metadata** - Copies OpenAlex concepts, keywords, and topics into works documents
3. **enrich_institutions** - Maps researcher institutional affiliations to works
4. **link_contributors** - Normalizes contributor names and establishes ORCID links
5. **add_author_count** - Precomputes author counts to eliminate array traversal during aggregations
6. **create_indexes** - Builds optimized indexes for common analytical queries
7. **drop_unused_indexes** - Removes indexes no longer needed after transformations

All migrations execute sequentially and log their progress. This process should be run after completing data harvesting and enrichment, and before beginning analytical work.

### Create Database Backup

```bash
python scripts/dump_database_pymongo.py
```

This utility creates a timestamped JSON backup of all MongoDB collections. Backups are stored in the `backups/` directory with metadata tracking. Use this before executing destructive operations or as part of regular backup procedures.

### Reset ORCID Data

```bash
python -m scripts.reset_orcids
```

This utility script clears ORCID-related collections from the database to allow clean re-execution of the harvesting workflows.

---

## Project Structure

The project follows a layered architecture that separates execution logic, domain components, and data processing stages:

```txt
src/
  ├── orcid/              ORCID API interaction and harvesting
  │   ├── search/        Query infrastructure and discovery
  │   ├── models/        Domain models for researcher profiles
  │   └── storage/       Persistence layer for ORCID data
  ├── works/             Scholarly works harvesting
  │   ├── harvest/       Work retrieval and extraction
  │   ├── models/        Work domain models
  │   └── storage/       Persistence for works data
  ├── data_enrichment/    Metadata enrichment pipeline
  │   ├── metadata/      Enrichment orchestration and task queuing
  │   ├── openalex/      OpenAlex API client and normalization
  │   └── storage/       Persistence for enriched metadata
  ├── data_migration/     Schema transformation and data preparation
  │   ├── migrate_doi.py          Extract DOI from external_ids
  │   ├── merge_metadata.py       Join OpenAlex metadata via DOI
  │   ├── enrich_institutions.py  Add institutional affiliations
  │   ├── link_contributors.py    Normalize and link contributor profiles
  │   ├── add_author_count.py     Precompute author counts
  │   ├── create_indexes.py       Build query optimization indexes
  │   ├── drop_unused_indexes.py  Remove obsolete indexes
  │   └── run_all.py              Orchestrate all migrations sequentially
  ├── data_analysis/      Statistical analysis and reporting utilities
  └── db/                 Database connectivity and utilities

scripts/                  Executable workflows and entry points
  ├── harvest_orcids.py             Retrieve ORCID researcher profiles
  ├── harvest_works.py              Retrieve scholarly works from profiles
  ├── enrich_data_openalex.py       Enrich metadata from OpenAlex API
  ├── dump_database_pymongo.py      Create timestamped database backups
  └── reset_orcids.py               Clear ORCID collections for re-execution

tests/                    Automated test suite and development utilities
  └── data_migration/     Unit tests and integration tests for schema migrations
```

This layered structure supports clear separation of concerns, enabling independent testing, maintenance, and evolution of each stage in the harvesting, enrichment, and analysis pipeline. The data migration layer specifically enables reproducible schema transformations that prepare the raw harvested data for analytical workloads.

### Migration Pipeline

The data migration subsystem (`src/data_migration/`) provides a deterministic, reproducible approach to schema transformation:

- **Sequence Control**: All migrations execute in a defined order to respect data dependencies
- **Idempotency**: Migrations can be safely re-executed without corrupting data
- **Logging and Monitoring**: Each migration logs relevant statistics for process visibility
- **Error Handling**: Individual migration failures do not block subsequent migrations; manual recovery is possible

---

## Documentation

Detailed documentation describing the system architecture, workflow, and internal components is available in the project Wiki.
The Wiki provides conceptual explanations intended to complement the source code and facilitate academic evaluation.

---

## Scope and Design Considerations

### Data Sources

- The system relies exclusively on official public APIs: ORCID and OpenAlex.
- No web crawling or HTML scraping is performed.
- All data collection respects institutional rate limits and API usage policies.

### Architecture

- Query partitioning is used to control request volume and improve scalability during ORCID harvesting.
- Data persistence is handled through dedicated storage modules to ensure separation of concerns.
- The enrichment pipeline incorporates batch processing and graceful error handling to maximize throughput while maintaining data integrity.
- DOI normalization is applied consistently across all pipeline stages to ensure reliable matching between harvested works and API-sourced metadata.

### Extensibility

- The modular design allows for future integration of additional metadata sources beyond OpenAlex.
- Storage and API interfaces are abstracted to facilitate swapping implementations without affecting orchestration logic.

---

## Schema Modifications for Data Analysis and Mining

The MongoDB schema has been intentionally modified and enriched to support aggregation queries, statistical analysis, and machine learning pipelines. The following changes transform the raw data into an analysis-ready dataset while introducing certain limitations that should be understood.

### Structural Changes

#### 1. DOI Extraction and Normalization

- **Field Added**: `doi` (top-level field in `works` collection)
- **Source**: Extracted from nested `external_ids` array
- **Purpose**: Enables efficient DOI-based lookups and joins with external data sources without array traversal
- **Benefit for Analysis**: Provides reliable entity matching across systems; supports metadata enrichment and research network analysis

#### 2. Flattened Metadata Integration

- **Fields Added**: `concepts`, `keywords`, `topics` (in `works` collection)
- **Source**: Populated from `works_metadata` collection via DOI matching
- **Purpose**: Eliminates need for cross-collection joins during analytical queries
- **Benefit for Analysis**: Enables field-level aggregations on research topics; supports classification and clustering tasks

#### 3. Institution Enrichment

- **Field Added**: `institution` (in `works` collection)
- **Purpose**: Maps researcher affiliation to scholarly works for institutional-level analysis
- **Benefit for Analysis**: Aggregations at institutional level; enables comparative studies across organizations

#### 4. Normalized Contributor Information

- **Field Modified**: `contributors` array (in `works` collection)
- **Normalization Applied**: Names standardized; ORCID profile links established
- **Purpose**: Improves accuracy of contributor-based analysis; enables researcher tracking across publications
- **Benefit for Analysis**: Reduces duplicate detection errors in collaboration networks; supports author disambiguation

#### 5. Precomputed Author Counts

- **Field Added**: `author_count` (in `works` collection)
- **Purpose**: Avoids expensive array length calculations during aggregations
- **Benefit for Analysis**: Faster aggregations for author statistics; enables efficient filtering by publication scale

#### 6. Optimized Indexing Strategy

The schema now includes 12+ strategically placed indexes:

- **Compound indexes** on (doi, institution) for institutional research discovery
- **Text indexes** on subjects, keywords for full-text search and topic mining
- **Numeric indexes** on author_count for range queries and stratification
- **Sorted indexes** on dates for time-series analysis and trend detection

### Limitations and Constraints

#### 1. Data Completeness

- **DOI Availability**: Not all works in ORCID have associated DOIs. Works without DOIs cannot be matched to OpenAlex metadata and remain unrich enriched.
- **Impact**: Approximately 10% of works may lack comprehensive metadata enrichment. Statistical analyses should account for this selection bias.

#### 2. Temporal Limits

- **Snapshot Nature**: The dataset represents a point-in-time snapshot of researcher profiles and works. ORCID and OpenAlex data continue to evolve.
- **Impact**: Historical analyses may not reflect corrections or updates made to original source records after harvesting.

#### 3. Deduplica of Metadata

- **DOI Collisions**: In rare cases, multiple works may share identical DOIs due to versioning or data errors in source systems.
- **Impact**: Aggregations by DOI may inadvertently combine unrelated works. Manual verification is recommended for sensitive analyses.

#### 4. Flattening Loss

- **Historical Context**: Original nested `external_ids` and `metadata_queue` structures are preserved but may become stale. Flattened fields (`doi`, `concepts`, `keywords`) reflect enrichment state at migration time.
- **Impact**: Re-running migrations does not retroactively update previously enriched records. Full re-enrichment requires dataset reset.

#### 5. Institutional Affiliation Reliability

- **Single Affiliation**: Current implementation maps only the primary institution per researcher at the time of profile harvest. Historical institutional changes are not tracked.
- **Impact**: Longitudinal institutional analyses may misattribute works to incorrect organizations. Multi-affiliation scenarios are not fully represented.

#### 6. Scalability Constraints

- **Aggregation Performance**: Complex aggregations with multiple stages may exceed MongoDB memory limits on very large datasets (>100M documents).
- **Recommendations**: For analysis of complete global datasets, consider materialized views or data export for external processing tools (e.g., Spark, Pandas).

### Recommended Analysis Workflows

Given these schema modifications and limitations, the following analytical approaches are recommended:

1. **Topic and Skills Mining**
   - Leverage flattened `concepts`, `keywords`, `topics` fields for unsupervised clustering
   - Group by institution and research focus for comparative analysis
   - Limitation: Filter out works with missing DOI to avoid bias

2. **Collaboration Network Analysis**
   - Use normalized `contributors` data to construct researcher networks
   - Limitation: Rely on ORCID IDs for linking; some contributors may lack ORCID profiles

3. **Institutional Productivity Assessment**
   - Aggregate by `institution` and time period using precomputed `author_count`
   - Limitation: Be aware of single-affiliation constraint when interpreting multi-institutional collaborations

4. **Metadata Distribution Analysis**
   - Analyze OpenAlex fields (concepts, keywords) for research landscape characterization
   - Limitation: Only works with DO are enriched; non-DOI works will appear as missing values

<!-- ### Data Mining Considerations

For machine learning and classification tasks:

- **Feature Engineering**: The flattened schema supports direct feature extraction without complex preprocessing. Precomputed fields (`author_count`) can serve as numeric features.
- **Training Data Quality**: The dataset is suitable for supervised learning tasks where the outcome variable is derived from text fields (e.g., topic classification) or numeric fields (e.g., authorship prediction).
- **Class Imbalance**: Consider stratification by `institution` or `author_count` to avoid biased models.
- **Feature Completeness**: Implement handling for missing values in enriched fields, as non-DOI works will have null metadata fields. -->

---
