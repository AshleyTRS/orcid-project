# ORCID Data Harvesting System

## Overview

This project implements an API-based system for the retrieval, processing, and storage of researcher information and scholarly publications from the ORCID platform.  
The system is designed following a modular architecture that separates query management, data retrieval, parsing, and persistence. Its primary objective is to provide a structured and reproducible workflow for collecting ORCID-related data while respecting API constraints and good software engineering practices.
The project is intended for academic use and uses public API endpoints to ethically collect ORCID related data.

### What is the ORCID platform?

An ORCID (Open Research and Contributor ID) is a free, unique, 16-digit persistent digital identifier for research professionals and students that solves the problem of distinguishing reserachers and their works throughout their careers. ORCID prevents confusion caused by name ambuity, creates a portable profile for each researcher that owns one, connects to other research repositories, and ensures authors get proper attribution for published works. The [ORCID](https://orcid.org/) platform permits universities and research institutions stay up to date with their researcher's contributions and publications, reducing the administrative burden and input errors and improving the discoverability of reseachers, employees, and students.

### Motivation

The motivation for this project arises from the difficulty of establishing a clear and reliable association between a specific academic institution and the scholarly output of its researchers. Although ORCID serves as a global registry that aggregates researcher identities and scholarly works worldwide, its comprehensive scope introduces significant overhead when an institution seeks to extract and analyze information relevant only to its own academic community.

In practice, institutional-level analysis requires the selective retrieval and processing of ORCID data, as the platform is not inherently organized around institutional boundaries. This project addresses that challenge by providing a structured, API-based system that enables individual institutions to independently collect, process, and store data related to their researchers and associated scholarly works.

By facilitating institution-focused data harvesting, the system supports localized analysis, reporting, and evaluation, while leveraging the global coverage and standardized identifiers provided by ORCID.

---

## Tools and Versions

### Programming Language

- Python 3.12 or later (tested with Python 3.13)

### External Libraries

- `requests==2.32.5`  
  Used for HTTP communication with the ORCID public API.
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
ORCID_API_TOKEN = <your-access-token>
MONGO_URI = <your-mongo-db-uri>
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

### Reset ORCID Data

```bash
python -m scripts.reset_orcids
```

This utility script clears ORCID-related collections from the database to allow clean re-execution of the harvesting workflows.

---

## Project Structure

The project follows a layered structure that separates execution logic from core functionality:

```txt
src/        Core application logic and domain components
scripts/    Executable workflows and entry points
tests/      Automated test scripts
```

This separation supports modularity, testing, and future extensibility.

---

## Documentation

Detailed documentation describing the system architecture, workflow, and internal components is available in the project Wiki.
The Wiki provides conceptual explanations intended to complement the source code and facilitate academic evaluation.
