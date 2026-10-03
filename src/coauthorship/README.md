# Co-authorship Network

## Overview

The `src/coauthorship` package builds the co-authorship network of the researchers in the database. A node represents a researcher identified by an ORCID iD; an edge joins two researchers who share at least one publication. Node size corresponds to the number of publications of the researcher within the selection, and edge weight to the number of publications the two researchers share.

The network is served by the web application through `GET /api/coauthorship` and `GET /api/stats` (see [API_REFERENCE.md](../../API_REFERENCE.md#co-authorship-network)) and drawn on the `/network` page.

## Components

| Module | Class or function | Responsibility |
| --- | --- | --- |
| `models.py` | `Publication` | A unique publication and the set of ORCID iDs of its authors |
| | `Node`, `Edge`, `NetworkData` | Graph elements and their JSON serialization; `NetworkData.get_stats()` computes summary statistics |
| | `Author` | ORCID-identified author (equality by ORCID iD) |
| `network_builder.py` | `MongoDBNetworkExtractor` | Selects the works that satisfy the filters and passes them to the builder |
| | `CoauthorshipNetworkBuilder` | Merges records into publications and computes node counts and edge weights |
| `coauthorship_aggregator.py` | `CoauthorshipAggregator` | Entry point: validates the year range, builds the network and returns it as a dictionary |
| | `get_coauthorship_data()` | Function form of the entry point, kept for compatibility |

## Construction

1. **Selection.** `MongoDBNetworkExtractor.extract_network()` matches works with `build_works_match()` from `src/analytics/aggregations.py`, the same filter definition used by the works search. It accepts a year range and optional lists of publication types, subjects, keywords and institutes. Only the fields needed for the graph are read: `work_key`, `doi`, `orcid_id`, `publication_year` and `contributors.orcid_id`.
2. **Merging into publications.** `CoauthorshipNetworkBuilder.add_document()` merges records by `work_key`. A publication is stored once per co-author with an ORCID iD and frequently several times on one ORCID record, so merging by `work_key` is required for correct counts (see [ARCHITECTURE.md](../../ARCHITECTURE.md#3-work-identity)).
3. **Authors.** The authors of a publication are the owners of its records together with every contributor whose ORCID iD is linked. Contributors without an ORCID iD are not represented in the graph.
4. **Counts and weights.** Each publication adds one to the count of each of its authors. Each publication with two or more authors adds one to the weight of the edge between every pair of its authors; pairs are formed from the sorted list of authors, so each edge is counted once regardless of order.

Researchers whose publications in the selection are all single-authored appear as nodes without edges; `get_stats()` reports their number as `solo_authors`.

## Usage

```python
import os
from dotenv import load_dotenv
from src.db.MongoConnection import MongoConnection
from src.coauthorship.coauthorship_aggregator import CoauthorshipAggregator

load_dotenv()
mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))

network = CoauthorshipAggregator(mongo.db).get_network_data(
    2020, 2025,
    subjects=["Computer Science"],
    types=["journal-article"],
)
print(len(network["nodes"]), "researchers,", len(network["edges"]), "collaborating pairs")

mongo.close()
```

`get_network_data()` raises `ValueError` if the start year is later than the end year or if either year lies outside 1900 to 2100.

Output format:

```json
{
  "nodes": [{"id": "0000-0001-2345-6789", "publications": 5}],
  "edges": [{"source": "0000-0001-2345-6789", "target": "0000-0002-3456-7890", "weight": 3}]
}
```

## Performance

The cost of a request grows with the number of selected works and, for publications with many authors, with the square of the number of authors, because every pair of authors forms an edge. One publication in the dataset lists 231 linked authors and alone contributes 26,565 pairs.

Two corrections reduced the time of the unfiltered network for 2020 to 2025 from 34 seconds to approximately 3.5 seconds without altering its content:

- `NetworkData.get_stats()` previously determined authors without collaborations by scanning all edges for every node. It now collects the identifiers of connected authors in a set, which makes the computation linear in the number of nodes and edges.
- The extraction projects only `contributors.orcid_id` instead of complete contributor objects.

Networks restricted by subject, type or keyword are built in under one second; the Computer Science network for 2020 to 2026 took 0.3 seconds on 3 October 2026. The web page therefore builds the network only on request, after the user has chosen filters.

## Standalone Server

`scripts/coauthorship_api.py` is an earlier standalone Flask server for the network. It is superseded by `run.py`, which serves the network endpoints together with the other pages and the current filters.

## Limitations

- Researchers are identified only through ORCID iDs. Co-authors without an ORCID iD, or whose profile was not harvested and linked, are absent from the graph.
- Records of one publication that do not share a `work_key` (for example, distinct DOIs for a preprint and the published article) are treated as separate publications.
- Nodes carry ORCID iDs only; researcher names are not part of the response.
