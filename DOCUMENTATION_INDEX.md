# Documentation Index

This index lists the documentation of the UAEH Researchers Network project and indicates which document answers which question. All documents describe the system as of 3 October 2026.

## Documents

| Document | Content | Intended use |
| --- | --- | --- |
| [README.md](README.md) | Purpose and motivation, requirements, installation, execution of every stage, repository structure, data model, limitations | Starting point for every reader |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components and data flow, work identity and deduplication, search, co-authorship network, web client design, verification, known limitations | Understanding how the system works and why it was built this way |
| [API_REFERENCE.md](API_REFERENCE.md) | Parameters, responses and errors of every HTTP endpoint and page route | Using or extending the web application's API |
| [src/data_migration/README.md](src/data_migration/README.md) | Order, effects and commands of the schema migrations; maintenance functions; procedure for new migrations | Running or changing the migrations |
| [src/analytics/README.md](src/analytics/README.md) | Aggregation, report and author profile functions | Writing analyses in Python or modifying queries |
| [src/coauthorship/README.md](src/coauthorship/README.md) | Construction, performance and limitations of the co-authorship network | Working on the network |
| [tests/data_migration/README.md](tests/data_migration/README.md) | Unit test suite: commands, test files, fixtures | Running and extending the tests |
| [scripts/db_dumps/DUMP_README.md](scripts/db_dumps/DUMP_README.md) | Database backup and restoration | Protecting data before modifications |

## Questions and Where They Are Answered

| Question | Section |
| --- | --- |
| How is the system installed and configured? | [README.md: Installation](README.md#installation) |
| In which order are the harvesting, enrichment and migration scripts run? | [README.md: Execution](README.md#execution) |
| How is the web application started? | [README.md: Stage 5](README.md#stage-5-run-the-web-application) |
| Which collections and fields exist? | [README.md: Data Model](README.md#data-model) |
| Why do publication counts differ from the number of records? | [ARCHITECTURE.md: Work Identity](ARCHITECTURE.md#3-work-identity) |
| How does search match names with and without accents? | [ARCHITECTURE.md: Search](ARCHITECTURE.md#4-search) |
| Why is the network built only on request? | [ARCHITECTURE.md: Co-authorship Network](ARCHITECTURE.md#5-co-authorship-network) |
| Which parameters does an endpoint accept? | [API_REFERENCE.md](API_REFERENCE.md) |
| What are the limits of the data and of the analyses? | [README.md: Limitations](README.md#limitations) and [ARCHITECTURE.md: Known Limitations](ARCHITECTURE.md#8-known-limitations-and-further-work) |
| How are the migrations run, and in which order? | [src/data_migration/README.md](src/data_migration/README.md) |
| How are the tests run? | [tests/data_migration/README.md](tests/data_migration/README.md) |
| How is a backup created and restored? | [scripts/db_dumps/DUMP_README.md](scripts/db_dumps/DUMP_README.md) |

## Development History

The project evolved through the following stages. The design decisions of each stage are recorded in [ARCHITECTURE.md](ARCHITECTURE.md).

| Period | Stage |
| --- | --- |
| February 2026 | Harvesting of ORCID profiles (partitioned discovery) and of their works |
| March 2026 | OpenAlex enrichment pipeline; schema migrations and their unit tests; publication analytics by year; co-authorship network prototype with Flask and D3.js and its object-oriented refactoring |
| April 2026 | Paginated, on-demand loading of authors and works on the search page |
| October 2026 | Redesign of the interface; server-side search with filters; filtered, on-demand network generation; author profile pages with open-access links; work identity and deduplication of statistics |

The documents that described the April 2026 pagination change (`REFACTORING_GUIDE.md`, `REFACTORING_SUMMARY.md` and `BEFORE_AFTER_COMPARISON.md`) were removed in October 2026, because later work superseded the code they reproduced. Their design rationale is preserved in [ARCHITECTURE.md, Section 4.2](ARCHITECTURE.md#42-pagination).
