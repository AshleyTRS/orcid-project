# Analytics Module Documentation

## Overview

The `src/analytics/` module provides MongoDB aggregation pipelines for computing publication statistics, institutional analysis, author metrics, and comprehensive reports over the scholarly works database.

All functions are designed to:

- Return results as Python lists/dicts for easy integration with visualization tools
- Support optional year range filtering for temporal analysis
- Include comprehensive logging for debugging and monitoring
- Handle missing/null values gracefully
- Leverage MongoDB indexes for optimal query performance

## Quick Start

```python
from src.analytics.aggregations import publications_per_year, top_authors
from src.db.MongoConnection import MongoConnection
import os
from dotenv import load_dotenv

# Setup
load_dotenv()
mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))

# Get publication trends
yearly_pubs = publications_per_year(mongo.db)
for stat in yearly_pubs:
    print(f"{stat['year']}: {stat['count']} publications")

# Get top 5 most prolific authors
top_5 = top_authors(mongo.db, limit=5)
for author in top_5:
    print(f"{author['orcid_id']}: {author['count']} publications")

mongo.close()
```

## API Reference

### Core Functions

#### 1. `publications_per_year(db, start_year=None, end_year=None)`

**Purpose**: Aggregate publication counts by publication year.

**Parameters**:

- `db` (MongoDB database): Database object from MongoConnection
- `start_year` (int, optional): Filter results from this year onwards
- `end_year` (int, optional): Filter results up to this year inclusive

**Returns**: List of dictionaries

```python
[
    {"year": 2020, "count": 120},
    {"year": 2021, "count": 150},
    {"year": 2022, "count": 200}
]
```

**Use Cases**:

- Visualize publication trends over time
- Identify growth/decline in research output
- Time-series analysis for institutional reporting

**Example**:

```python
# All years
all_years = publications_per_year(mongo.db)

# Recent 5 years
recent = publications_per_year(mongo.db, start_year=2020, end_year=2025)

# Plot with matplotlib
import matplotlib.pyplot as plt
years = [s['year'] for s in recent]
counts = [s['count'] for s in recent]
plt.plot(years, counts, marker='o')
plt.title('Publication Trend (2020-2025)')
plt.show()
```

---

#### 2. `publications_per_institution_per_year(db, start_year=None, end_year=None)`

**Purpose**: Aggregate publication counts by institution and year.

**Parameters**:

- `db` (MongoDB database): Database object
- `start_year` (int, optional): Filter from this year
- `end_year` (int, optional): Filter to this year

**Returns**: List of dictionaries

```python
[
    {"institution": "Universidad Nacional Autónoma de México", "year": 2020, "count": 45},
    {"institution": "Instituto Politécnico Nacional", "year": 2020, "count": 38},
    {"institution": "Universidad Nacional Autónoma de México", "year": 2021, "count": 52}
]
```

**Use Cases**:

- Institutional benchmark reporting
- Comparative analysis between organizations
- Identify institutional research leaders
- Stacked area charts showing institutional contributions over time

**Example**:

```python
# Compare Mexican institutions 2020-2025
results = publications_per_institution_per_year(mongo.db, start_year=2020)

# Group by institution for summary
by_institution = {}
for record in results:
    inst = record['institution']
    if inst not in by_institution:
        by_institution[inst] = []
    by_institution[inst].append(record)

# Find top institutions
top_institutions = sorted(
    by_institution.items(),
    key=lambda x: sum(r['count'] for r in x[1]),
    reverse=True
)[:10]

for inst_name, records in top_institutions:
    total = sum(r['count'] for r in records)
    print(f"{inst_name}: {total} publications")
```

---

#### 3. `publications_per_type(db, start_year=None, end_year=None)`

**Purpose**: Aggregate publication counts by publication type.

**Parameters**:

- `db` (MongoDB database): Database object
- `start_year` (int, optional): Filter from this year
- `end_year` (int, optional): Filter to this year

**Returns**: List of dictionaries (sorted by count descending)

```python
[
    {"type": "journal-article", "count": 5000},
    {"type": "conference-paper", "count": 1200},
    {"type": "book-chapter", "count": 300},
    {"type": "book", "count": 50}
]
```

**Supported Types** (ORCID standard):

- `journal-article` - Peer-reviewed journal articles
- `conference-paper` - Conference proceedings
- `book` - Published books
- `book-chapter` - Chapters in edited books
- `dissertation` - Theses and dissertations
- `report` - Technical and research reports
- `data-set` - Data publications
- And others per ORCID specification

**Use Cases**:

- Understand research output distribution
- Pie or donut charts showing publication type breakdown
- Publication portfolio analysis

**Example**:

```python
# Get publication type distribution
type_dist = publications_per_type(mongo.db)

# Create pie chart
import matplotlib.pyplot as plt
labels = [t['type'] for t in type_dist]
sizes = [t['count'] for t in type_dist]
plt.pie(sizes, labels=labels, autopct='%1.1f%%')
plt.title('Publication Type Distribution')
plt.show()

# Calculate proportions
total = sum(t['count'] for t in type_dist)
for pub_type in type_dist:
    pct = (pub_type['count'] / total * 100)
    print(f"{pub_type['type']}: {pct:.1f}%")
```

---

#### 4. `top_authors(db, limit=10, start_year=None, end_year=None)`

**Purpose**: Identify most prolific authors by publication count (primary author only).

**Parameters**:

- `db` (MongoDB database): Database object
- `limit` (int): Maximum authors to return (default: 10)
- `start_year` (int, optional): Filter from this year
- `end_year` (int, optional): Filter to this year

**Returns**: List of dictionaries (sorted by count descending)

```python
[
    {"orcid_id": "0000-0001-2345-6789", "count": 87},
    {"orcid_id": "0000-0002-3456-7890", "count": 74},
    {"orcid_id": "0000-0003-4567-8901", "count": 65}
]
```

**Notes**:

- This counts only works where `orcid_id` field is populated (primary author)
- Does not include authors appearing only as contributors
- Use `author_contributor_analysis()` for comprehensive author metrics

**Use Cases**:

- Identify institutional research leaders
- Understand author productivity distribution
- Create author leaderboards for reporting

**Example**:

```python
# Top 20 authors overall
top_20 = top_authors(mongo.db, limit=20)

# Top 5 authors from last 3 years
recent_leaders = top_authors(mongo.db, limit=5, start_year=2022)

# Display with rank
for rank, author in enumerate(top_20, 1):
    print(f"{rank:2}. {author['orcid_id']}: {author['count']:3} publications")

# Analyze productivity distribution
from statistics import mean, median, stdev
counts = [a['count'] for a in top_authors(mongo.db, limit=100)]
print(f"Mean: {mean(counts):.1f}")
print(f"Median: {median(counts):.1f}")
print(f"StdDev: {stdev(counts):.1f}")
```

---

#### 5. `author_contributor_analysis(db, limit=10, start_year=None, end_year=None)`

**Purpose**: Identify top contributors including co-authors by publication count.

**Parameters**:

- `db` (MongoDB database): Database object
- `limit` (int): Maximum contributors to return (default: 10)
- `start_year` (int, optional): Filter from this year
- `end_year` (int, optional): Filter to this year

**Returns**: List of dictionaries (sorted by publication_count descending)

```python
[
    {
        "orcid_id": "0000-0001-2345-6789",
        "name": "Dr. Jane Smith",
        "publication_count": 127
    },
    {
        "orcid_id": "0000-0002-3456-7890",
        "name": "Prof. John Doe",
        "publication_count": 105
    }
]
```

**Notes**:

- Includes all publications where person appears as contributor
- Requires contributor ORCID IDs to be populated
- Counts each publication once per person (not cumulative with primary author)
- Returns contributor name from `credit_name` field

**Use Cases**:

- Comprehensive author performance analysis
- Collaboration network analysis
- Identify most active researchers regardless of authorship position
- Coauthor statistics

**Example**:

```python
# Get top 25 active contributors
active = author_contributor_analysis(mongo.db, limit=25)

# Create ranked list with names
for rank, contrib in enumerate(active, 1):
    print(f"{rank:2}. {contrib['name']:<30} ({contrib['orcid_id']})")
    print(f"    {contrib['publication_count']} publications\n")

# Identify collaborators for a specific author
target_orcid = "0000-0001-2345-6789"
all_contributors = author_contributor_analysis(mongo.db, limit=500)
collaborators = [c for c in all_contributors if c['orcid_id'] != target_orcid]
print(f"Top collaborators with {target_orcid}:")
for collab in collaborators[:10]:
    print(f"  - {collab['name']}")
```

---

#### 6. `publication_metrics_summary(db, start_year=None, end_year=None)`

**Purpose**: Generate comprehensive summary statistics for the publication dataset.

**Parameters**:

- `db` (MongoDB database): Database object
- `start_year` (int, optional): Filter from this year
- `end_year` (int, optional): Filter to this year

**Returns**: Dictionary with summary metrics

```python
{
    "total_publications": 10234,
    "total_institutions": 156,
    "avg_authors_per_publication": 3.45,
    "min_authors": 1,
    "max_authors": 42,
    "publication_types": 8,
    "year_range": {
        "min": 2010,
        "max": 2025
    },
    "computed_at": "2026-03-20T15:30:45.123456"
}
```

**Use Cases**:

- Dashboard summary cards
- Institutional reporting headers
- Data quality assessment
- Dataset characterization for machine learning

**Example**:

```python
# Get overall statistics
summary = publication_metrics_summary(mongo.db)

# Get recent 5-year statistics
recent = publication_metrics_summary(mongo.db, start_year=2020)

# Display summary
print(f"📊 Publication Database Summary")
print(f"   Total Publications: {summary['total_publications']:,}")
print(f"   Institutions: {summary['total_institutions']}")
print(f"   Publication Types: {summary['publication_types']}")
print(f"   Average Authors/Pub: {summary['avg_authors_per_publication']:.2f}")
print(f"   Author Range: {summary['min_authors']}-{summary['max_authors']}")
print(f"   Years: {summary['year_range']['min']}-{summary['year_range']['max']}")

# Calculate changes
pct_change = ((recent['total_publications'] / summary['total_publications']) - 1) * 100
print(f"\n   Publications 2020-2025: {recent['total_publications']:,} ({pct_change:+.1f}%)")
```

---

## Advanced Usage

### Combining Results for Visualization

```python
import json
from src.analytics.aggregations import *

db = mongo.db

# Comprehensive data export for D3.js visualization
data = {
    "summary": publication_metrics_summary(db),
    "yearly_trends": publications_per_year(db),
    "institutional_analysis": publications_per_institution_per_year(db),
    "type_distribution": publications_per_type(db),
    "top_authors": top_authors(db, limit=25),
    "top_contributors": author_contributor_analysis(db, limit=25)
}

# Export as JSON for frontend
with open('publications_data.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)
```

### Year-over-Year Growth Analysis

```python
def analyze_growth(db):
    yearly = publications_per_year(db)
    
    print("Year-over-Year Growth:")
    for i in range(1, len(yearly)):
        prev = yearly[i-1]
        curr = yearly[i]
        growth = ((curr['count'] / prev['count']) - 1) * 100
        print(f"  {prev['year']} → {curr['year']}: {growth:+.1f}%")

analyze_growth(db)
```

### Institutional Benchmarking

```python
def benchmark_institutions(db, institutions_list):
    results = publications_per_institution_per_year(db, start_year=2020)
    
    benchmark = {}
    for result in results:
        if result['institution'] in institutions_list:
            if result['institution'] not in benchmark:
                benchmark[result['institution']] = 0
            benchmark[result['institution']] += result['count']
    
    # Rank and compare
    ranked = sorted(benchmark.items(), key=lambda x: x[1], reverse=True)
    
    # Calculate percentiles
    counts = [count for _, count in ranked]
    mean_count = sum(counts) / len(counts)
    
    for inst, count in ranked:
        pct_of_mean = (count / mean_count - 1) * 100
        print(f"{inst}: {count} publications ({pct_of_mean:+.0f}% vs average)")

# Usage
target_institutions = [
    "Universidad Nacional Autónoma de México",
    "Instituto Politécnico Nacional",
    "Universidad de São Paulo"
]
benchmark_institutions(db, target_institutions)
```

### Export for Data Mining

```python
import pandas as pd

def export_to_dataframe(db):
    """Export aggregation results to pandas DataFrames for analysis."""
    
    yearly = publications_per_year(db)
    yearly_df = pd.DataFrame(yearly)
    
    institution_year = publications_per_institution_per_year(db, start_year=2015)
    inst_df = pd.DataFrame(institution_year)
    
    types = publications_per_type(db)
    types_df = pd.DataFrame(types)
    
    return {
        'yearly': yearly_df,
        'institutions': inst_df,
        'types': types_df
    }

# Usage
dfs = export_to_dataframe(db)

# Analyze trends
dfs['yearly'].plot(x='year', y='count', kind='line')

# Pivot for heatmap
pivot_table = dfs['institutions'].pivot_table(
    values='count',
    index='institution',
    columns='year'
)

# Find top institutions by 5-year average
top_5_avg = dfs['institutions'].groupby('institution')['count'].mean().nlargest(10)
```

## Performance Considerations

### Index Utilization

The aggregation pipelines leverage the following indexes for optimal performance:

```
db.works.indexes:
  - publication_year (ascending)
  - type (ascending)
  - orcid_id (ascending)
  - institutions.name (ascending)
  - contributors.orcid_id (ascending)
```

### Query Performance Tips

1. **Use year filters** when possible to reduce document scans:

   ```python
   recent = publications_per_year(db, start_year=2015)  # Faster
   ```

2. **Limit results** for co-author analysis:

   ```python
   top_100 = author_contributor_analysis(db, limit=100)  # Faster than limit=10000
   ```

3. **Materialize views** for frequently accessed reports:
   - Save aggregation results as separate collections
   - Update via scheduled batch jobs

### Scalability

- **Small datasets** (<1M docs): All queries execute in milliseconds
- **Medium datasets** (1-100M docs): Year filtering strongly recommended
- **Large datasets** (>100M docs): Consider hourly/daily materialized views

## Error Handling

All functions include try-catch blocks and logging:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    results = top_authors(db, limit=10)
except Exception as e:
    logger.error(f"Failed to compute top authors: {str(e)}")
    # Handle gracefully...
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty results | Check year range filters; verify data exists for criteria |
| Slow queries | Add year_range filter; check index usage with `explain()` |
| Missing contributors | Some works may have null contributor IDs; use main API for those |
| Null institutions | Some works may not have institutional affiliation; use filter if needed |

## Example: Complete Analytics Report

See [scripts/analyze_publications.py](../scripts/analyze_publications.py) for a complete example script that:

1. Generates summary statistics
2. Produces yearly trends visualization data
3. Identifies institutional leaders
4. Ranks top authors
5. Exports results to JSON for reporting

Run with:

```bash
python scripts/analyze_publications.py
```
