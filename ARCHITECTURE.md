# System Architecture and Design

This document describes the architecture of the UAEH Researchers Network system, the flow of data through it, and the design decisions taken during its development, together with the evidence that motivated them. Installation and execution instructions are given in [README.md](README.md); the HTTP interface is specified in [API_REFERENCE.md](API_REFERENCE.md).

Figures quoted in this document were measured against the project database on 2 and 3 October 2026 (34,662 work records, 5,386 researcher profiles) unless stated otherwise.

---

## 1. System Overview

The system is organized as a pipeline of five stages that share a single MongoDB database.

```txt
ORCID API ──> [1] Profile discovery ──> orcids
                                          │
ORCID API ──> [2] Works harvesting  ──> works ──────────────┐
                                          │                 │
OpenAlex ───> [3] Enrichment ─────────> works_metadata      │
                                          │                 │
              [4] Schema migrations <─────┴─────────────────┘
                     │  (DOI extraction, metadata merge, affiliations,
                     │   contributor linking, work identity, indexes)
                     v
              [5] Analytics and web application
                     ├── aggregation pipelines (src/analytics)
                     ├── co-authorship network (src/coauthorship)
                     └── Flask application (src/app, templates, static)
```

Each stage reads the output of the previous stages from the database and can be re-executed independently. The stages are implemented in separate packages with no dependency on the presentation layer.

---

## 2. Components

### 2.1 Profile discovery (`src/orcid`)

`DiscoveryEngine` searches ORCID for researchers whose current affiliation names the institution. The ORCID search API returns at most 10,000 results per query, so the search is divided into partitions by family-name prefix (`QueryPartition`): the engine seeds one partition per initial letter, estimates the result count of each, and splits any partition that exceeds the limit into longer prefixes, breadth first, until every partition fits. Partitions are persisted in the `partitions` collection with a status (`pending`, `processing`, `done`), so an interrupted run resumes with the pending partitions. Profiles are stored in `orcids` with a unique index on `orcid_id`.

### 2.2 Works harvesting (`src/works`)

`WorkHarvester` retrieves the list of work entries (`put_code` values) of each profile not yet marked as harvested, requests each entry, parses it into a `Work` model and stores it through `WorkStorage`, which enforces uniqueness of the pair (`orcid_id`, `put_code`). Requests are separated by a fixed delay of 0.1 seconds.

The harvester computes a `work_key` for each new record (Section 3). After a profile is harvested it links that profile's duplicate records, refreshes the researcher's `unique_works_count`, and records the number of stored records as `works_count`.

### 2.3 Enrichment (`src/data_enrichment`)

`MetadataSelector` collects the distinct DOIs of harvested works into `metadata_queue` as tasks with the status `pending`. `MetadataHarvester` processes the queue in batches: `OpenAlexClient` requests each DOI from OpenAlex (at most ten requests per second), `OpenAlexNormalizer` reduces the response to the fields used by the project, `AbstractReconstructor` rebuilds the abstract from OpenAlex's inverted index, and `MetadataStorage` upserts the result into `works_metadata`, keyed by DOI and source. Each task is then marked `done`, or `failed` with an incremented attempt counter; a failure does not stop the run.

### 2.4 Schema migrations (`src/data_migration`)

The migrations transform the harvested records into an analysis-ready form (see [src/data_migration/README.md](src/data_migration/README.md) for each step). They are executed in a fixed order by `run_all.py`, because later steps depend on fields produced by earlier ones; for example, `add_work_key` requires the DOIs extracted by `migrate_doi` and the contributor links created by `link_contributors`. Every migration is a function that receives the collections it needs and returns a status dictionary, which allows the runner to report results uniformly and to continue after a failure. All migrations are idempotent.

### 2.5 Analytics (`src/analytics`)

`aggregations.py` contains the aggregation pipelines for the search page, the filter options, the summary charts and the report script. `author_profile.py` contains the queries of the author profile page. Both modules count distinct works through `work_key`. The module is documented in [src/analytics/README.md](src/analytics/README.md).

### 2.6 Co-authorship network (`src/coauthorship`)

`MongoDBNetworkExtractor` selects the works that satisfy the requested filters, and `CoauthorshipNetworkBuilder` merges them into unique publications, counts the publications of each author and the publications shared by each pair of authors. The result is returned as nodes and weighted edges. The package is documented in [src/coauthorship/README.md](src/coauthorship/README.md).

### 2.7 Web application (`src/app`, `templates`, `static`)

A Flask application serves four pages and eleven JSON endpoints. Pages are rendered once by Jinja2 and then load their data from the JSON endpoints; no page embeds data at render time. The pages share a header template (`templates/_header.html`) and a single stylesheet (`static/styles/main.css`). Section 6 describes the client-side design.

---

## 3. Work Identity

### 3.1 Problem

ORCID stores one work entry for each source that contributes a publication to a researcher's record. A publication imported from Scopus, from Crossref and by manual entry therefore appears three times on the same record, each time with a different `put_code` and otherwise identical content. In addition, a publication appears once on the record of every co-author who has an ORCID iD.

Measurements on the dataset before the correction:

| Measure | Value |
| --- | --- |
| Work records | 34,662 |
| Records repeating a DOI already present on the same researcher's record | 5,249 |
| Records without a DOI repeating a title and year on the same record | 418 |
| Records without a DOI repeating a DOI record of the same researcher (same title and year) | 305 |
| Records whose title contains HTML markup (for example `AgSbS<inf>2</inf>`) | 1,278 |
| Researchers whose displayed publication count was inflated by duplicates | 705 of 5,386 |

The search page displayed `orcids.works_count`, which counted records rather than works, and ranked researchers by it. For example, one researcher was displayed with 202 publications although the 202 records describe 89 distinct works. Three of the ten highest-ranked researchers held their position because of duplicate records. The maintenance function `check_works_count` reset `works_count` to the raw record count on every execution, so the inflation persisted.

### 3.2 Solution

Every document of `works` carries a `work_key`. Documents that share a key describe the same publication, and every statistic counts distinct keys. The key is defined once, in `src/works/work_key.py`, and the same definition is used by the harvester, the migrations, the web application and the report functions.

The rules are applied in order:

1. **DOI.** The DOI is read from `doi` or, failing that, from `external_ids`. The resolver prefix (`https://doi.org/`) and the `doi:` label are removed and the value is lower-cased, because DOIs are case-insensitive. Key: `doi:<doi>`.
2. **Linking of records without a DOI.** If a record without a DOI has the same normalized title and the same year as exactly one DOI record of the same researcher, it receives that DOI key. When the title and year correspond to two or more DOIs, the record is left unlinked, because the match is ambiguous.
3. **Title and year.** The title is normalized by removing markup, decoding HTML entities, removing diacritics, case-folding and replacing punctuation with spaces. Inline tags such as `<inf>` and `<sup>` are removed without inserting a space, because they occur inside words. Titles of 40 or more normalized characters form a global key, `title:<title>|<year>`; shorter titles are scoped to the record owner, `title:<orcid>:<title>|<year>`, so that generic titles such as "Editorial" or "Introduction" are never merged across researchers.
4. **Fallback.** A record with neither DOI nor title receives `put:<orcid>:<put_code>` and counts as a work of its own.

Normalization is performed in Python rather than in the aggregation pipeline. MongoDB's `$toLower` operator folds only ASCII characters, so a pipeline-based key would have failed to merge, for example, `POLÍTICA` and `política`.

### 3.3 Counting

`unique_works_count` in `orcids` is the number of distinct keys among the works on the researcher's own record and the works on other records that list the researcher as a linked contributor. This is the same set of works that the author profile page lists, so the search page, the profile statistics and the works list report the same figure. `works_count` retains its original meaning, the number of records stored for the profile, and the profile page shows it as supplementary information.

Aggregations that must count works rather than records insert the stages returned by `unique_works_stages()`, which keep one document per `work_key`, or per pair of `orcid_id` and `work_key` for counts attributed to record owners.

### 3.4 Alternatives considered

| Alternative | Reason for rejection |
| --- | --- |
| Deleting duplicate records | `put_code` is ORCID's identifier, and a later harvest recreates every deleted entry. Duplicates also hold complementary fields: one copy may carry the journal title and another the open-access location. |
| A MongoDB view that groups works | A view only relocates the per-query grouping. It cannot be indexed after the grouping stage, and it does not provide a stored count by which researchers can be sorted. |
| Computing the key inside each aggregation pipeline | This was the initial implementation of the author profile page. It duplicated the rule in each query, could not fold non-ASCII case, and could not link records without a DOI to their DOI counterparts. |

### 3.5 Results

After the migration, the 34,662 records describe 21,770 distinct works: 13,445 identified by DOI and 8,325 by title. The researcher mentioned above is displayed with 89 works everywhere, and the three records of the publication shown during the analysis (three `put_code` values with the DOI `10.1016/j.hydromet.2020.105456`), together with a fourth record on a co-author's profile, form a single work. For a sample of 63 researchers, including the most affected ones, the search page count, the profile statistics and the total of the works list were verified to be equal.

### 3.6 Maintenance

Records inserted by the harvester receive a key immediately, and the harvested profile is reconciled at the end of its harvest. The counts of co-authors who appear on newly harvested works are updated when `add_work_key` runs, which is step 6 of `run_all.py`. The migration should therefore be executed after each harvest. A record that lacks a key is treated as a work of its own by the queries, so it is never silently omitted.

---

## 4. Search

### 4.1 Server-side search and filtering

Search and filtering are performed by the database, not in the browser. The client sends the query text and the active filters with every request, and the server returns one page of results and the total number of matches. The browser never holds the complete result set.

- **Researchers** are matched on given names, family names, credit name and ORCID iD.
- **Works** are matched on title, normalized contributor names and DOI.
- The query is split into terms; every term must match at least one field. A query such as "Garcia Lirios" therefore matches a researcher whose given and family names contain the two terms in separate fields.
- Matching is insensitive to accents and case. Each term is converted into a regular expression in which every vowel, `n`, `c` and `y` is replaced by a character class containing its accented variants in both cases, so that "garcia" matches "García".
- Hyphenated names are matched against `contributors.normalized_name`, in which hyphens are stored as spaces.
- User input is escaped before it is inserted into a regular expression, so characters such as `(` or `*` are matched literally.

Filters by year, keyword, publication type, subject and institute are combined with the text query by `build_works_match()`, which is shared by the works search and the co-authorship network so that both interpret filters identically.

### 4.2 Pagination

Results are paginated by the database (`$skip` and `$limit` within a `$facet` that also returns the total), so the size of a response is independent of the size of the collection. The page size is validated on the server and limited to the range 1 to 100. Responses contain only the fields that the result cards display. Each request replaces the visible page rather than appending to it.

These decisions date from the first refactoring of the search page (April 2026), which replaced the loading of every author and work at page start-up with on-demand, paginated requests. The original measurements of that change were not retained in a reproducible form and are not reported here.

---

## 5. Co-authorship Network

### 5.1 Construction

The network is built from the works that satisfy the requested year range and optional filters (publication type, subject, keyword and sub-institution). Records are merged into publications by `work_key`. Each publication contributes one unit to the count of each of its authors and one unit to the weight of the edge between each pair of its authors. Only authors identified by an ORCID iD that is linked to a stored profile become nodes.

### 5.2 On-demand generation

The network page loads no data when it opens. The graph is built only when the user selects filters and requests it, and the option lists of the filters are loaded when each list is first opened. Building the network is the most expensive operation of the application, and a narrower selection produces both a faster response and a more legible graph.

### 5.3 Performance

Profiling of the unfiltered network for 2020 to 2025 (4,321 authors and 40,678 collaborations at the time of measurement) located two sources of cost:

| Cause | Correction | Effect |
| --- | --- | --- |
| `NetworkData.get_stats()` counted authors without collaborations by scanning every edge for every node, approximately 176 million comparisons, and was called twice per request for logging | Collect the identifiers of connected authors in a set once, reducing the computation to linear time in nodes and edges | Approximately 20 seconds removed |
| The query transferred complete contributor objects (names, tokens, roles) although only ORCID iDs are used | Project only `contributors.orcid_id` | Database transfer reduced from about 7 to about 2 seconds |

The server time of the unfiltered network fell from 34 seconds to approximately 3.5 seconds, with identical nodes, edges and statistics. Repeated measurements of the complete request ranged from 3.2 to 16.9 seconds; the variation originates in the database round trip, while parsing and drawing in the browser take approximately 50 milliseconds. A network restricted to one subject is built in well under a second; for Computer Science (582 authors, 940 collaborations) the request took 0.3 seconds on 3 October 2026.

### 5.4 Rendering

The graph is drawn on a single canvas element rather than as one SVG element per node and edge. Each frame consists of a small number of batched drawing operations, redrawing is limited to one frame per animation tick, and hit testing uses a quadtree. Nodes are sized by publication count and edges by collaboration count.

---

## 6. Web Client Design

### 6.1 Visual design

The interface follows a minimal style with a blue palette (primary colour `#1E40AF` on slate neutrals), the Inter typeface, flat surfaces with 1-pixel borders and restrained motion. The style, palette and type pairing were selected with the ui-ux-pro-max design guidance and are defined as CSS custom properties in `static/styles/main.css`, which every page shares. Colours are never hard-coded in components.

### 6.2 Robustness of requests

- **Superseded requests.** Every request receives a sequence number, and a response is applied only if no newer request has been issued since. Rapid changes of search mode or filters therefore always display the result of the last action. An earlier design discarded new requests while one was pending, which could leave the results of a previous mode on screen.
- **Escaping.** All values from the database are escaped before insertion into the page, and actions are attached through event delegation rather than inline handlers. A title containing quotation marks or markup is displayed as text and cannot alter the page.
- **Links to external resources.** Open-access and DOI links accept only the `http` and `https` schemes, open in a new tab with `rel="noopener noreferrer"`, and state in their accessible name that they open a new tab.

### 6.3 State in the address

The author profile page records its page number, sort order and open-access filter in the URL query string. A profile view can therefore be shared, and the browser's back and forward buttons restore the previous state.

### 6.4 Accessibility

Interactive elements are native buttons, links and form controls, reachable by keyboard and provided with visible focus indicators. Custom checkboxes keep the native input in the tab order. Text meets a contrast ratio of 4.5:1 against its background. On small screens interactive targets are at least 44 pixels high. Animations are suppressed when the operating system requests reduced motion. The works-per-year chart of the author profile is accompanied by a text summary of its peak and range.

### 6.5 Open-access links

The author profile page shows a PDF button for an open-access work only when the stored link points directly to a document: the path ends in `.pdf` or contains `/pdf` or `/download`. About 37 percent of the stored open-access links satisfy this condition; the others lead to landing pages, which remain reachable through the DOI link of the title. The heuristic inspects only the address and does not download the target.

---

## 7. Verification

- **Unit tests.** `tests/data_migration/` contains 98 tests for the migrations and the work identity rules. They use mocked collections and require no database (see [tests/data_migration/README.md](tests/data_migration/README.md)).
- **Browser verification.** During development the pages were exercised in Google Chrome through Playwright with real interactions: search by button and keyboard, every filter, pagination, rapid mode changes, injection of markup into queries, generation and manipulation of the network, the author profile with its sorting, filtering and deep links, and layouts at a width of 375 pixels. These scripts are not part of the repository.
- **Data checks.** The work identity migration was verified by re-execution (no further changes), by comparison of the three author counts for a sample of researchers, and by inspection of the records of individual publications.

---

## 8. Known Limitations and Further Work

| Area | Observation | Possible improvement |
| --- | --- | --- |
| Network layout | After the layout settles, about one third of a subject-level graph and one fifth of the complete graph lie outside the visible area, because unconnected groups drift apart | Fit the view to the graph once the layout settles, and add a weak attraction towards the centre |
| Network response size | The unfiltered network response is 3.4 MB of uncompressed JSON | Compress responses and cache networks per filter combination |
| Search page summary cards | "Top Institutions", "Authors by Sub-Institution", "Publication Types" and "Top Research Topics" display placeholder figures | Back the cards with the existing aggregation functions |
| Search page actions | The Sort button and the View More button of works are placeholders | Implement sorting and a work detail view |
| Contributor linking | Linking compares complete normalized names; contributors credited by initials or in inverted order remain unlinked | Match on family name and initials, with the ambiguity rules already applied to full names |
| Network labels | Nodes are labelled by ORCID iD | Include researcher names in the network response |
| Favicon | No page declares an icon, so browsers request `/favicon.ico` and receive a 404 response | Add an icon link to the shared header |
