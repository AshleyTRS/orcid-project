# Co-authorship Network - OOP Refactored Version

## Overview

This is a refactored, object-oriented implementation of a co-authorship network pipeline that builds dynamic graphs from MongoDB publication data. The system correctly handles the complexity of publications appearing multiple times in the database (once per author with an ORCID) and provides accurate metrics for author productivity and collaboration strength.

## Architecture

### Core Components

#### 1. **Domain Models** (`models.py`)

Defines the core data structures:

- `Author`: Represents an author with ORCID
- `Publication`: Represents a unique work with its authors
- `Node`: Graph node representing an author with publication count
- `Edge`: Graph edge representing a collaboration with weight
- `NetworkData`: Complete network containing nodes and edges

#### 2. **Network Builder** (`network_builder.py`)

Contains the business logic:

- `CoauthorshipNetworkBuilder`: Constructs the graph from document data
  - Deduplicates publications by DOI
  - Extracts all authors per publication
  - Computes author productivity (publication counts)
  - Generates collaboration edges with weights

- `MongoDBNetworkExtractor`: Handles MongoDB queries and extraction
  - Executes aggregation pipeline
  - Filters by year range
  - Delegates to builder for graph construction

#### 3. **Aggregator** (`coauthorship_aggregator.py`)

Main interface for the system:

- `CoauthorshipAggregator`: High-level API for network computation
- `get_coauthorship_data()`: Legacy function for backward compatibility

#### 4. **API Server** (`coauthorship_api.py`)

Flask-based REST API:

- `GET /api/coauthorship?startYear=X&endYear=Y`: Returns network data
- `GET /api/stats?startYear=X&endYear=Y`: Returns network statistics
- `GET /health`: Health check endpoint

## Key Features

### Correct Deduplication

Publications appearing multiple times in MongoDB (once per author) are correctly deduplicated by DOI. Each publication is counted only once.

### Accurate Productivity Metrics

Author publication counts reflect the number of **unique publications** they contributed to, not the number of database documents.

### Proper Edge Weights

Collaboration edges represent the number of **unique shared publications** between two authors.

### Handles Missing ORCIDs

Authors without ORCID IDs (contributors with `orcid_id: null`) are excluded from the graph, as required for network analysis.

### Solo and Collaborative Works

- Solo-author publications contribute to node weights (productivity)
- Multi-author publications contribute to both node weights AND edge weights
- The system correctly handles mixed scenarios

## Data Flow

```
MongoDB Documents
    ↓
MongoDBNetworkExtractor (queries by year range)
    ↓
CoauthorshipNetworkBuilder (processes documents)
    ↓
    1. Group by DOI → Unique Publications
    2. Extract ORCIDs → Author Sets
    3. Count publications per author → Node Weights
    4. Generate pairwise collaborations → Edge Weights
    ↓
NetworkData (nodes + edges)
    ↓
JSON API Response
```

## Example Usage

### Using the Aggregator Directly

```python
from coauthorship_aggregator import CoauthorshipAggregator
from pymongo import MongoClient

# Connect to database
client = MongoClient("mongodb://localhost:27017")
db = client["your_database"]

# Create aggregator
aggregator = CoauthorshipAggregator(db)

# Get network data
network_data = aggregator.get_network_data(
    start_year=2020,
    end_year=2026
)

print(f"Nodes: {len(network_data['nodes'])}")
print(f"Edges: {len(network_data['edges'])}")
```

### Using the API

```bash
# Get network data
curl "http://localhost:5000/api/coauthorship?startYear=2020&endYear=2026"

# Get statistics
curl "http://localhost:5000/api/stats?startYear=2020&endYear=2026"

# Health check
curl "http://localhost:5000/health"
```

### API Response Format

```json
{
  "nodes": [
    {
      "id": "0000-0001-2345-6789",
      "publications": 5
    }
  ],
  "edges": [
    {
      "source": "0000-0001-2345-6789",
      "target": "0000-0002-3456-7890",
      "weight": 3
    }
  ]
}
```

## MongoDB Data Structure

The system expects documents in the `works` collection with the following structure:

```json
{
  "_id": "...",
  "orcid_id": "0000-0001-2345-6789",
  "doi": "10.1234/example.doi",
  "publication_year": 2025,
  "title": "Example Publication",
  "contributors": [
    {
      "credit_name": "Author Name",
      "orcid_id": "0000-0002-3456-7890",
      "role": "author"
    },
    {
      "credit_name": "Another Author",
      "orcid_id": null,
      "role": "author"
    }
  ]
}
```

**Important Notes:**

- Each publication may appear multiple times (once per author with ORCID)
- The `doi` field is used for deduplication
- The `orcid_id` field at document level represents the main author
- The `contributors` array may contain authors with or without ORCIDs
- Authors without ORCIDs are excluded from the graph

## Testing

Run the comprehensive test suite:

```bash
python test_network.py
```

The test suite verifies:

1. ✅ Deduplication of publications by DOI
2. ✅ Extraction of all authors with ORCID IDs
3. ✅ Correct publication count computation
4. ✅ Proper edge generation and weight calculation
5. ✅ Handling of solo vs. collaborative publications

### Test Results

All tests pass successfully:

```
================================================================================
VERIFICATION RESULTS
================================================================================

1. PUBLICATION DEDUPLICATION:
   - Documents processed: 3
   - Unique publications (by DOI): 1
   - Expected: 1 ✓ PASS

2. AUTHOR EXTRACTION:
   - Match: ✓ PASS

3. PUBLICATION COUNTS:
   - All authors have 1 publication: ✓ PASS

4. COLLABORATION EDGES:
   - Edge pairs match: ✓ PASS
   - All edge weights are 1: ✓ PASS
```

## Installation

### Requirements

```bash
pip install -r requirements.txt
```

Required packages:

- Flask >= 2.0.0
- pymongo >= 4.0.0
- python-dotenv >= 0.19.0

### Environment Configuration

Create a `.env` file:

```env
MONGO_CONN=mongodb://localhost:27017
DB_NAME=your_database_name
```

### Running the API Server

```bash
python coauthorship_api.py
```

The server will start on `http://0.0.0.0:5000`

## Comparison with Original Implementation

### Original Issues

1. **Overcounting**: The original code incremented author counts for each document, leading to publications being counted multiple times
2. **No deduplication**: Publications weren't properly grouped by DOI
3. **Procedural approach**: Logic was scattered across functions

### Improvements in OOP Version

1. **Correct counting**: Publications are deduplicated by DOI before counting
2. **Clean architecture**: Separation of concerns with clear class responsibilities
3. **Testable**: Easy to unit test with mock data
4. **Maintainable**: Changes to logic are isolated in specific classes
5. **Extensible**: Easy to add new features (filters, weights, metrics)

## Future Enhancements

Potential improvements that can be added:

1. **Institution Filtering**: Filter by author institutions
2. **Citation Weights**: Weight edges by citation counts
3. **Temporal Analysis**: Track network evolution over time
4. **Community Detection**: Identify research communities
5. **Author Enrichment**: Add author names, affiliations, etc.
6. **Caching**: Cache network data for frequently requested ranges
7. **Graph Export**: Export to GraphML, GEXF, or other formats

## License

MIT License

## Authors

Refactored OOP implementation by Claude
Original concept based on user requirements
