# Analytics Module

## Overview

The `src/analytics` package contains the MongoDB aggregation pipelines of the project. It serves three consumers:

- the HTTP API of the web application (`src/app`), which uses the search, author profile and filter option functions;
- the report script `scripts/analyze_publications.py`, which uses the report functions;
- interactive analysis in Python, for which every function returns plain lists and dictionaries.

| Module | Content |
| --- | --- |
| `aggregations.py` | Search helpers, report functions, paginated listings and filter option counts |
| `author_profile.py` | Profile, statistics and works of a single researcher |

## Counting Principle

The `works` collection stores one document per ORCID work entry. A publication therefore appears once on the record of each co-author with an ORCID iD, and frequently several times on one record, once for each source that imported it. All functions in this package count distinct works by the `work_key` field rather than documents. The field and its rules are defined in `src/works/work_key.py` and described in [ARCHITECTURE.md](../../ARCHITECTURE.md#3-work-identity).

Pipelines that need whole documents collapse duplicates with `unique_works_stages()` from `src/works/work_key.py`, which keeps one document per `work_key`, or per pair of `orcid_id` and `work_key` when counts are attributed to record owners.

Every document receives a `work_key` from the harvester or from the `add_work_key` migration. Should a document lack one, the search, filter option, per-year and network queries exclude it, and the author profile queries treat it as a work of its own. The report functions assume that every document has a key: documents without one would be grouped together and counted as a single work.

## Usage

```python
import os
from dotenv import load_dotenv
from src.db.MongoConnection import MongoConnection
from src.analytics.aggregations import publications_per_year, top_authors

load_dotenv()
mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))

for row in publications_per_year(mongo.db, start_year=2020, end_year=2025):
    print(row["year"], row["count"])

for row in top_authors(mongo.db, limit=5):
    print(row["orcid_id"], row["count"])

mongo.close()
```

Every function receives the database object (`mongo.db`) as its first argument, logs its progress, and re-raises database errors after logging them.

---

## Search Helpers (`aggregations.py`)

### `build_works_match(query=None, start_year=None, end_year=None, types=None, subjects=None, keywords=None, institutes=None)`

Returns a `$match` document for the `works` collection. It is shared by the works search and the co-authorship network so that both interpret filters identically.

| Argument | Matching rule |
| --- | --- |
| `query` | Every term must match the title, a normalized contributor name or the DOI |
| `start_year`, `end_year` | Inclusive bounds on `publication_year` |
| `types` | `type` is one of the values |
| `subjects` | `topics.field.display_name` contains one of the values |
| `keywords` | `keywords.display_name` contains one of the values |
| `institutes` | An entry of `institutions.name` contains one of the values as an accent-insensitive substring |

Only documents with a `work_key` match.

### `search_terms(query)`, `strip_accents(text)`, `accent_insensitive_regex(text)`

`search_terms` splits a query into at most ten whitespace-separated terms. `strip_accents` lower-cases a string and removes diacritics. `accent_insensitive_regex` builds a regular expression that matches its argument regardless of accents and case by replacing each vowel and the letters `n`, `c` and `y` with a class of their accented variants; all other characters are escaped.

---

## Listings Used by the Web Application

### `all_authors_details_paginated(db, page=1, limit=50, query=None, institutes=None)`

Researchers ordered by `unique_works_count` (descending), then by ORCID iD. `query` is matched against given names, family names, credit name and ORCID iD; `institutes` against the profile's `institution_names`. Returns the pagination structure `{"data", "page", "has_next", "total"}`; each item contains `orcid_id`, `given_names`, `family_names` and `count`.

### `all_works_details_paginated(db, page=1, limit=50, query=None, start_year=None, end_year=None, keywords=None, institutes=None)`

Distinct works ordered by publication year (descending). The pipeline filters with `build_works_match`, groups by `work_key`, sorts, and paginates and counts in one `$facet` stage. Each item contains `doi`, `title`, `publication_year`, `type`, `journal_title` and `contributors`. When the records of a work differ, the DOI is taken from a record that has one.

### `value_counts(db, field_path, limit=100)` and `top_keywords(db, limit=100)`

`value_counts` counts distinct works per value of a field, most frequent first, and returns `[{"value", "count"}]`. The field may be scalar (`type`) or a path into an array of sub-documents (`topics.field.display_name`); a value repeated within one work counts once for that work. `top_keywords` applies it to `keywords.display_name` and returns `[{"keyword", "count"}]`.

### `publications_per_year(db, start_year=1969, end_year=None)`

Number of distinct works per publication year, ordered by year. `end_year` defaults to the current year. A work whose records disagree on the year is counted under the latest of its years within the range. Passing `start_year=None` explicitly yields an empty result; callers should omit the argument to use the default.

---

## Report Functions

These functions are used by `scripts/analyze_publications.py`. Each accepts optional inclusive `start_year` and `end_year` bounds and counts distinct works.

### `publications_per_institution_per_year(db, start_year=None, end_year=None)`

Works per affiliation and year, ordered by year: `[{"institution", "year", "count"}]`. A work is counted once for each affiliation stored on it. Affiliations are those of the record owner's ORCID profile (see the limitations in [README.md](../../README.md#institutional-affiliation)).

### `publications_per_type(db, start_year=None, end_year=None)`

Works per ORCID work type, most frequent first: `[{"type", "count"}]`.

### `top_authors(db, limit=10, start_year=None, end_year=None)`

Researchers with the most distinct works on their own ORCID record: `[{"orcid_id", "count"}]`. Duplicate records on one record count once. Works on which the researcher appears only as a contributor on another record are not included; `unique_works_count` in the `orcids` collection includes them.

### `author_contributor_analysis(db, limit=10, start_year=None, end_year=None)`

Contributors with linked ORCID iDs ranked by the number of distinct works on which they appear: `[{"orcid_id", "name", "publication_count"}]`. Counts are grouped by the pair of ORCID iD and credited name, so a researcher credited under two spellings appears twice.

### `publication_metrics_summary(db, start_year=None, end_year=None)`

Summary of the selection: number of distinct works, number of distinct affiliations, mean, minimum and maximum number of contributors per work, number of work types, year range, and the time at which the summary was computed (`computed_at`).

---

## Author Profile (`author_profile.py`)

A researcher's works are the works on the researcher's own ORCID record together with works on other records that list the researcher as a linked contributor, each counted once by `work_key`. The same definition determines `orcids.unique_works_count`, so the search page, the profile statistics and the works list report the same number.

### `is_valid_orcid(orcid_id)`

Whether the identifier has the form `0000-0000-0000-000X`.

### `get_author_profile(db, orcid_id)`

Returns the profile and statistics, or `None` if neither a profile nor a work exists for the identifier. The result contains the display name, other credited names, affiliations, the number of stored records (`orcid_works_count`), statistics (distinct works, open-access works, co-authors, first and last year), works per year, and the eight most frequent topics and types. E-mail addresses are never read.

### `get_author_works(db, orcid_id, page=1, limit=20, sort="newest", open_access_only=False)`

One page of the researcher's distinct works. `sort` is `newest`, `oldest` or `title`; the title order ignores case and leading quotation marks and brackets. Each item includes `oa_url`, restricted to `http` and `https` addresses, and `oa_is_pdf`, which indicates whether that address points directly to a document.

---

## Legacy Functions

`all_authors_details(db)` and `all_works_details(db)` return complete, unpaginated listings. They are not used by the application or the scripts. `all_works_details` removes duplicates by DOI only and omits works without a DOI; new code should use the paginated functions, which apply the work identity rules.

---

## Indexes

The pipelines rely on the following indexes of the `works` collection, created by the migrations:

| Index | Used by |
| --- | --- |
| `orcid_id`, (`orcid_id`, `work_key`) | Author profile, `top_authors` |
| `contributors.orcid_id` | Author profile (works listing the researcher as contributor) |
| `work_key` | Grouping of duplicate records |
| `publication_year`, (`publication_year`, `type`) | Year filters and per-year counts |
| `type`, `institutions.name` | Publication type and institute filters |

The subject filter matches `topics.field.display_name`, which has no index of its own; the existing `topics.display_name` index covers topic names, not fields. The search page orders researchers using the index (`unique_works_count` descending, `orcid_id`) of the `orcids` collection. Free-text search uses unanchored regular expressions, which cannot use an index and scan the matching collection; with the current data volume such queries complete in well under a second.

## Troubleshooting

| Symptom | Cause and remedy |
| --- | --- |
| A function returns no rows | Verify the year bounds; for `publications_per_year`, omit `start_year` or pass an integer |
| Counts differ from older reports | Earlier reports counted documents; current functions count distinct works |
| A new work is missing from listings | The document has no `work_key`; run `python -m src.data_migration.add_work_key` |
| `unique_works_count` of a co-author is outdated after a harvest | Run `add_work_key` (step 6 of `run_all.py`), which recomputes all counts |
