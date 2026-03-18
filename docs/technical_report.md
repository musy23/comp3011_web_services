# UK Climate Insights API — Technical Report

**Module:** COMP3011 Web Services and Web Data · University of Leeds · March 2026

---

**GitHub repository:** https://github.com/musy23/comp3011_web_services
**API documentation:** https://github.com/musy23/comp3011_web_services/blob/main/docs/api_documentation.md
**Presentation slides:** *(add link — Google Drive / OneDrive)*
**GenAI conversation logs:** *(add link — Google Drive / OneDrive)*

---

## 1. Introduction

This report describes the UK Climate Insights API — a RESTful web service providing access to historical UK weather observations from 8 Met Office monitoring stations (1853–2025). The system supports full CRUD operations on stations, observations, and annotations, plus a suite of analytical endpoints (trend regression, anomaly detection, seasonal statistics, WMO climate normals). A 6-page interactive frontend dashboard and an MCP server for AI assistant integration extend the project beyond the base requirements.

---

## 2. Technology Stack and Justification

### Framework: FastAPI (Python 3.13)

I chose **FastAPI** over Django REST Framework after evaluating both. Django carries significant overhead — its ORM is synchronous by default, the settings module is heavyweight, and the DRF serialiser/viewset abstraction adds indirection that I find harder to reason about. FastAPI offered three specific advantages for this project:

- **Native async/await** — the analytics endpoints run SQL aggregations over 11,000+ records. Blocking the thread during these queries would degrade concurrency. FastAPI's async handlers combined with SQLAlchemy 2's async engine keep the event loop unblocked.
- **Auto-generated documentation** — Pydantic schemas and route decorators produce Swagger UI and ReDoc automatically. This was important because the marking criteria require documented endpoints, and maintaining a separate doc file in sync with code would have been error-prone.
- **Pydantic v2 validation** — request bodies and responses are validated and serialised by the same schema, eliminating a whole class of inconsistency bugs.

I considered **GraphQL** but rejected it. The query patterns for climate data are well-defined: filter by station, date range, and variable. REST's resource model (`/stations`, `/observations`, `/analytics/trends`) maps onto the domain naturally. GraphQL's flexibility would have added schema complexity without meaningful client benefit.

### Database: PostgreSQL 16

**PostgreSQL** was my preferred choice over SQLite (insufficient for concurrent writes, no window functions) and MongoDB (document model doesn't suit time-series queries). The decisive factor was PostgreSQL's statistical aggregate functions:

- `regr_slope(y, x)` and `regr_r2(y, x)` — used directly in the trend endpoint to compute linear regression in a single SQL query, without loading data into Python
- `STDDEV_POP` and `AVG` — used for z-score anomaly detection, computing monthly baselines across all years in one pass

These functions let the database do the heavy analytical work, keeping the Python application layer thin.

### ORM: SQLAlchemy 2 (async) + Repository Pattern

I structured data access using a **repository pattern** — a deliberate architectural decision to separate SQL from business logic. Each router delegates to a service (business rules) which delegates to a repository (SQL). This made unit testing significantly easier: the repository tests hit the database, the service tests mock the repository. It also means if I were to swap PostgreSQL for another database, only the repositories need changing.

### Containerisation: Docker Compose

Docker Compose orchestrates the API and PostgreSQL as two services. This was a practical necessity — having a reproducible environment that any evaluator can spin up with `docker-compose up --build` without installing PostgreSQL locally. The Dockerfile uses layered caching (dependencies installed before application code) to keep rebuilds fast.

---

## 3. Architecture Overview

The application follows a four-layer architecture:

```
Router  →  Service  →  Repository  →  PostgreSQL
(HTTP)    (logic)       (SQL)          (data)
```

Three ORM models: **Station** (geographic metadata, operational dates), **Observation** (monthly climate record with a unique constraint on `station_id + date`), **Annotation** (user-submitted notes with an approval flag).

Analytics are computed in SQL rather than Python — this was a conscious choice to keep the application stateless and horizontally scalable. All seven analytics endpoints (`/trends`, `/anomalies`, `/seasonal`, `/compare`, `/extremes`, `/heatmap`, `/climate-normal`) return pre-aggregated results from single SQL queries.

---

## 4. Key Design Decisions

**Authentication:** API key (`X-API-Key` header) for write operations; all reads are public. I chose key-based auth over OAuth 2.0 because the write surface is small (admin ingestion, not user-facing writes) and OAuth would have added disproportionate complexity. The key is configurable via environment variable.

**Pagination:** All list endpoints return a consistent `PaginatedResponse` wrapper — `{ data: [...], pagination: { page, page_size, total, pages } }`. Choosing a standard envelope early prevented the frontend pagination logic from diverging across pages.

**Partial-year exclusion:** 2026 data is ingested for completeness but excluded from all average and baseline calculations (`WHERE EXTRACT(YEAR FROM date) <= 2025`). Including a partial year would systematically skew seasonal means — e.g. a warm January 2026 would inflate the January average without a compensating December.

**MCP server:** `mcp_server.py` wraps the service layer in 8 callable tools using `fastmcp`, enabling Claude Desktop to query the API via natural language. This demonstrates MCP-compatible design as outlined in the outstanding criteria. I verified all 8 tools against the live database (Durham warming trend: +0.25°C/decade; Heathrow Jan 1963: −3.84σ cold anomaly).

---

## 5. Testing Approach

47 tests across 4 files, achieving **81% line coverage**:

| File | Tests | Focus |
|---|---|---|
| `test_stations.py` | 12 | Full CRUD, auth rejection, 404/409 |
| `test_observations.py` | 11 | Full CRUD, date filtering, quality flags |
| `test_annotations.py` | 12 | Full CRUD, approval workflow |
| `test_analytics.py` | 12 | All 7 analytics endpoints, edge cases |

Tests use an **in-memory async SQLite** database as a fixture — no live PostgreSQL required. Factory helpers (`station_factory`, `observation_factory`) create test data with sensible defaults, keeping individual tests concise. I consciously chose integration-style tests (routes → services → repositories against a real database) over heavily mocked unit tests, because mocking the repository layer would only test that the mock behaves correctly — not that the actual SQL is right.

---

## 6. Challenges and Lessons Learned

**Chart.js version mismatches** were the most time-consuming frontend problem. The `Chart.defaults.scale` API (v3) was removed in v4.4.3 — my code silently threw a TypeError before any network requests executed, making charts fail with no obvious cause. Lesson: always pin library versions and test against the pinned version explicitly.

**Schema validation vs data reality:** The `sunshine_hours` field was initially constrained `le=24` (appropriate for daily hours). Met Office data stores monthly totals — up to ~300 hours/month — causing every observation with sunshine data to fail Pydantic response validation with a 500 error. The fix was trivial (`le=750`) but the root cause was an assumption about data granularity I hadn't questioned. Lesson: validate schemas against actual data samples early.

**Partial-year skew in analytics** was caught during frontend testing when the 2026 climate map showed anomalously high annual averages at some stations. Tracing this revealed that averages including January–February 2026 (an unusually warm start to the year) skewed the annual mean upward. I added explicit year-capping to all aggregate queries.

---

## 7. Limitations and Future Work

- **8 stations, monthly resolution** — the Met Office publishes data for ~37 long-record stations, and daily data is available from the CEDA Archive. Extending coverage would require a CEDA account but minimal code change.
- **No real-time data** — the API is historic-only. A production version could poll the Met Office API for near-real-time monthly updates.
- **Authentication** — API key auth is appropriate for an academic API but would need replacing with OAuth 2.0 / JWT for a public multi-user system.
- **Deployment** — the submission runs locally via Docker. Railway/Render deployment is straightforward but requires a managed PostgreSQL add-on.

---

## Appendix A — GenAI Declaration

This project was developed with **Claude Code** (Anthropic, Sonnet 4.6 model) throughout. The full conversation log is linked at the top of this report.

**How GenAI was used:**

| Activity | My role |
|---|---|
| Project scaffolding, Dockerfile, docker-compose | Reviewed and approved structure |
| SQLAlchemy models, Pydantic schemas | Specified field requirements and constraints |
| Repository/service/router pattern | Directed approach, reviewed all SQL queries |
| Analytics SQL (regression, z-score, normals) | Validated against known historical results |
| Frontend dashboard (6 pages, Chart.js, Leaflet) | Specified each page, tested, directed redesigns |
| Test suite (47 tests) | Reviewed for correctness, identified missing edge cases |
| MCP server | Specified 8 tool requirements, verified live against DB |
| API documentation and this report | Edited for accuracy, added personal experience sections |

**Critical analysis:**

GenAI accelerated boilerplate significantly — route handlers, schema definitions, and test fixtures that follow well-established patterns were generated correctly first time. However, it produced several errors that required my own diagnosis:

1. **`Chart.defaults.scale` (Chart.js v3 API)** — used in generated frontend code, does not exist in v4.4.3. All charts crashed silently until I read the browser console and identified the root cause.
2. **`fill:'+1'` circular reference** — generated Chart.js code caused "Maximum call stack exceeded" due to circular fill resolution in v4. I identified this and changed all fills to `fill:false`.
3. **`sunshine_hours le=24`** — generated constraint appropriate for daily data, wrong for monthly totals. Caused 500 errors on every observation with sunshine data.
4. **`.items` vs `.data` in paginated responses** — generated frontend accessed the wrong key on the pagination envelope, requiring me to trace the response shape through the network tab.

These errors share a pattern: GenAI applied general knowledge correctly but did not anticipate domain-specific constraints (monthly vs daily data, Chart.js version-specific API changes). Each required me to understand both the generated code and the underlying system well enough to identify where the assumption broke down. GenAI did not replace engineering judgement — it shifted where that judgement was applied, from writing to reviewing and debugging.

All code in this submission is understood by me and I am prepared to explain any part of it at the oral examination.

---

*University of Leeds · COMP3011 · March 2026*
