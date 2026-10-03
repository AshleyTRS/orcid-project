# HTTP API Reference

This document specifies the HTTP interface of the web application defined in `src/app/__init__.py`. The application is started with `python run.py` and listens on `http://127.0.0.1:5000` by default.

All endpoints accept only `GET` requests and return JSON encoded in UTF-8. Cross-origin requests are permitted (Flask-CORS). The API performs no authentication and applies no rate limiting; it is intended for use on a trusted network.

---

## Conventions

### Counting of works

The database stores one document per ORCID work entry, so the same publication can be stored several times. Every endpoint that returns works or counts of works counts distinct works, identified by the `work_key` field. The rules are described in [ARCHITECTURE.md](ARCHITECTURE.md#3-work-identity).

### Pagination

Paginated endpoints accept `page` (1-based) and `limit`, and return:

| Field | Type | Description |
| --- | --- | --- |
| `data` | array | Items of the requested page |
| `page` | integer | Page returned |
| `has_next` | boolean | Whether a further page exists |
| `total` | integer | Number of items matching the request |

The number of pages is `ceil(total / limit)`. Values of `page` below 1 are treated as 1, and `limit` is clamped to the range stated for each endpoint.

### Repeatable parameters

Parameters described as repeatable may be given several times, for example `?keyword=Biology&keyword=Chemistry`. A work matches if it has any of the given values. Different parameters are combined with a logical AND.

### Text search

The `q` parameter is split into whitespace-separated terms (at most ten; the query is truncated to 200 characters). Every term must match at least one of the searched fields. Matching ignores case and accents, so `garcia` matches `García`. Characters with a meaning in regular expressions are matched literally.

### Errors

Errors are returned as `{"error": "<message>"}` with one of the following status codes:

| Status | Meaning |
| --- | --- |
| 400 | A parameter is malformed or out of range |
| 404 | The requested author does not exist |
| 500 | The database query failed; the message contains the error text |

---

## Endpoint Summary

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Availability check |
| `GET /api/authors` | Search and list researchers |
| `GET /api/authors/<orcid>` | Profile and statistics of one researcher |
| `GET /api/authors/<orcid>/works` | Works of one researcher |
| `GET /api/works` | Search and list works |
| `GET /api/publications-per-year` | Number of works per publication year |
| `GET /api/keywords` | Most frequent keywords |
| `GET /api/work-types` | Publication types with work counts |
| `GET /api/subjects` | Subjects with work counts |
| `GET /api/coauthorship` | Co-authorship network |
| `GET /api/stats` | Statistics of a co-authorship network |

---

## Health

### `GET /health`

Returns `{"status": "healthy"}` with status 200 when the application is running. The database is not contacted.

---

## Researchers

### `GET /api/authors`

Returns researchers ordered by number of distinct works (descending), then by ORCID iD.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Page size, 1 to 100 |
| `q` | string | none | Matched against given names, family names, credit name and ORCID iD |
| `institute` | string, repeatable | none | Institute name, matched as an accent-insensitive substring of the researcher's ORCID affiliations |

Response items:

| Field | Type | Description |
| --- | --- | --- |
| `orcid_id` | string | ORCID iD |
| `given_names` | string | Given names, or an empty string |
| `family_names` | string | Family names, or an empty string |
| `count` | integer | Number of distinct works (`unique_works_count`) |

Example:

```bash
curl "http://127.0.0.1:5000/api/authors?q=garcia&limit=2"
```

```json
{
  "data": [
    {"orcid_id": "0000-0002-9364-6796", "given_names": "Cruz", "family_names": "García Lirios", "count": 338},
    {"orcid_id": "0000-0002-7405-4883", "given_names": "LAURA GEMMA", "family_names": "FLORES GARCIA", "count": 199}
  ],
  "page": 1,
  "has_next": true,
  "total": 287
}
```

Errors: 400 with `Invalid page or limit parameter` if `page` or `limit` is not an integer.

### `GET /api/authors/<orcid>`

Returns the profile and summary statistics of one researcher. The researcher's works are the works on the researcher's own ORCID record together with works on other records that list the researcher as a linked contributor, each counted once.

| Field | Type | Description |
| --- | --- | --- |
| `orcid_id` | string | ORCID iD |
| `name` | string | Display name (given and family names, otherwise credit name) |
| `observed_names` | array of strings | Other names under which the researcher is credited |
| `institutions` | array of strings | Affiliations listed on the ORCID profile |
| `orcid_works_count` | integer or null | Number of work records stored for the profile, duplicates included |
| `stats.works` | integer | Number of distinct works |
| `stats.open_access` | integer | Distinct works with an open-access location |
| `stats.coauthors` | integer | Distinct co-authors with a linked ORCID iD |
| `stats.first_year`, `stats.last_year` | integer or null | Earliest and latest publication year |
| `per_year` | array | `{"year", "count"}` for each year with works |
| `topics` | array | Up to eight `{"value", "count"}` items, most frequent first |
| `types` | array | Up to eight `{"value", "count"}` items, most frequent first |

Errors: 400 with `Invalid ORCID iD` if the identifier does not have the form `0000-0000-0000-000X`; 404 with `Author not found` if no profile or work exists for it. E-mail addresses stored in the profile are never returned.

### `GET /api/authors/<orcid>/works`

Returns one page of a researcher's distinct works.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | integer | 1 | Page number |
| `limit` | integer | 20 | Page size, 1 to 100 |
| `sort` | string | `newest` | `newest`, `oldest` or `title`; any other value is treated as `newest` |
| `oa` | string | none | `1` returns only open-access works |

The `title` order ignores case and leading quotation marks and brackets.

Response items:

| Field | Type | Description |
| --- | --- | --- |
| `doi` | string or null | DOI, if any record of the work has one |
| `title` | string | Title |
| `publication_year` | integer or null | Publication year |
| `type` | string | ORCID work type, for example `journal-article` |
| `journal_title` | string | Journal or venue, or an empty string |
| `contributors` | array of strings | Contributor names as credited |
| `is_oa` | boolean | Whether an open-access location is known |
| `oa_url` | string or null | Open-access location; only `http` and `https` addresses are returned |
| `oa_is_pdf` | boolean | Whether `oa_url` points directly to a document (path ending in `.pdf` or containing `/pdf` or `/download`) |

Errors: 400 with `Invalid ORCID iD`, or with `Invalid page or limit parameter`.

---

## Works

### `GET /api/works`

Returns distinct works ordered by publication year (descending). Works without a DOI are included.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Page size, 1 to 100 |
| `q` | string | none | Matched against title, contributor names and DOI |
| `start_year` | integer | none | Earliest publication year, inclusive |
| `end_year` | integer | none | Latest publication year, inclusive |
| `keyword` | string, repeatable | none | OpenAlex keyword display name |
| `institute` | string, repeatable | none | Institute name, matched as an accent-insensitive substring of the affiliations stored on the work |

Response items contain `doi`, `title`, `publication_year`, `type`, `journal_title` and `contributors`, with the meanings given above.

Errors: 400 with `Invalid page, limit or year parameter`.

### `GET /api/publications-per-year`

Returns the number of distinct works for each publication year in a range.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `start_year` | integer | 1969 | Earliest year, inclusive |
| `end_year` | integer | current year | Latest year, inclusive |

Response: `{"data": [{"year": 2020, "count": 1410}, ...]}`, ordered by year.

A work whose records disagree on the year is counted once, under the latest of its years within the requested range.

Errors: 400 with `Invalid start_year or end_year parameter`.

---

## Filter Options

These endpoints supply the option lists of the filters. Counts are numbers of distinct works.

### `GET /api/keywords`

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | integer | 100 | Number of keywords, 1 to 500 |

Response: `{"data": [{"keyword": "Humanities", "count": 2845}, ...]}`, most frequent first.

### `GET /api/work-types`

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | integer | 100 | Number of types, 1 to 500 |

Response: `{"data": [{"value": "journal-article", "count": 13311}, ...]}`, most frequent first.

### `GET /api/subjects`

Subjects are OpenAlex topic fields, for example `Computer Science` or `Medicine`.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | integer | 100 | Number of subjects, 1 to 500 |

Response: `{"data": [{"value": "Agricultural and Biological Sciences", "count": 2325}, ...]}`, most frequent first.

Errors for all three endpoints: 400 with `Invalid limit parameter`.

---

## Co-authorship Network

### `GET /api/coauthorship`

Returns the co-authorship network of the works that satisfy the parameters. Nodes are researchers identified by a linked ORCID iD; an edge joins two researchers who share at least one work.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `startYear` | integer | 2020 | Earliest publication year, inclusive |
| `endYear` | integer | 2026 | Latest publication year, inclusive |
| `type` | string, repeatable | none | ORCID work type |
| `subject` | string, repeatable | none | OpenAlex topic field |
| `keyword` | string, repeatable | none | OpenAlex keyword display name |
| `institute` | string, repeatable | none | Institute name, matched against the affiliations stored on the work |

Response:

```json
{
  "nodes": [{"id": "0000-0001-2345-6789", "publications": 5}],
  "edges": [{"source": "0000-0001-2345-6789", "target": "0000-0002-3456-7890", "weight": 3}]
}
```

`publications` is the number of distinct works of the researcher within the selection; `weight` is the number of distinct works the two researchers share.

Errors: 400 with `startYear must be less than or equal to endYear`, with `Years must be between 1900 and 2100`, or with the conversion error if a year is not an integer.

Performance: without filters, the response for 2020 to 2026 contains 4,656 nodes and 42,676 edges (3.4 MB). It was built in 3.4 seconds on 3 October 2026; earlier repeated measurements ranged from 3.2 to 16.9 seconds, the variation originating in the database round trip. A network restricted to the subject Computer Science (582 nodes, 940 edges) is returned in about 0.3 seconds.

### `GET /api/stats`

Accepts the same parameters as `/api/coauthorship` and returns statistics of the resulting network:

| Field | Type | Description |
| --- | --- | --- |
| `total_nodes` | integer | Number of researchers |
| `total_edges` | integer | Number of collaborating pairs |
| `total_collaborations` | integer | Sum of edge weights |
| `solo_authors` | integer | Researchers without a collaboration in the selection |
| `start_year`, `end_year` | integer | Year range applied |

---

## Page Routes

The following routes return HTML pages, not JSON.

| Route | Page |
| --- | --- |
| `/`, `/index` | Search |
| `/author/<orcid>` | Author profile; responds with 404 if the identifier is malformed |
| `/network` | Co-authorship network |
| `/json_view` | Viewer of the raw `/api/coauthorship` response |
