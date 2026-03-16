# UK Climate Insights API — Technical Report

**Module:** COMP3011 Web Services and Web Data
**Institution:** University of Leeds
**Submission date:** 13 March 2026

---

## 1. Introduction

This report describes the design, implementation, and evaluation of the UK Climate Insights API — a RESTful web service built for the COMP3011 individual project. The system provides programmatic access to historical UK weather observations sourced from the Met Office, covering 8 monitoring stations with data spanning from 1853 to 2026.

The API enables clients to perform full CRUD operations on weather stations, monthly observations, and user-submitted annotations, as well as advanced analytical queries including linear regression trend analysis, statistical anomaly detection, seasonal statistics, and WMO 30-year climate normals.

---

## 2. Requirements and Design Goals

The core requirements were to build an API that:
- Implements full CRUD on at least one data model linked to a database
- Exposes at least four HTTP endpoints
- Handles user input and returns appropriate JSON responses
- Uses correct HTTP status/error codes
- Is demonstrable (locally or deployed)

Beyond the minimum pass criteria, the design aimed for an "Outstanding" band by targeting:
- **Novel data integration** — real Met Office historic station data (1853–2026) rather than synthetic datasets
- **Advanced analytics** — statistical methods (z-score anomaly detection, linear regression via PostgreSQL window functions, WMO climate normal calculation)
- **MCP compatibility** — an AI-assistant-ready MCP server exposing the API as callable tools for Claude Desktop
- **Publication-quality documentation** — full API reference, interactive Swagger/ReDoc, and this technical report
- **User-facing dashboard** — a 6-page interactive frontend served by the API itself

---

## 3. Technology Choices

### 3.1 Framework: FastAPI

FastAPI was chosen over Django REST Framework for three reasons:

1. **Native async support** — SQLAlchemy 2's async engine enables non-blocking database queries, which is critical for the computationally expensive analytics endpoints (trend regression over 1,700+ records per station).
2. **Automatic OpenAPI generation** — FastAPI generates Swagger UI and ReDoc documentation automatically from Pydantic schemas and route decorators, reducing documentation maintenance burden.
3. **Pydantic v2 integration** — Pydantic v2 (5–50× faster than v1) handles all request validation, response serialisation, and schema definition in a single unified model, reducing boilerplate.

GraphQL was considered but rejected: the dataset is predominantly read-oriented with well-defined query patterns (filtering by station, date range, variable). REST's resource-oriented model maps cleanly onto the domain (`/stations`, `/observations`, `/analytics/trends`), while GraphQL's flexibility would add complexity without meaningful benefit for this use case.

### 3.2 Database: PostgreSQL 16

PostgreSQL was selected over SQLite or MongoDB for:

- **Window and aggregate functions** — the analytics layer uses `regr_slope`, `regr_r2`, `STDDEV_POP`, and `AVG` as SQL aggregate functions, avoiding the need to load entire datasets into Python for processing.
- **ACID compliance** — concurrent API writes (observation ingestion + user annotations) require serialisable transactions.
- **Indexing** — composite indexes on `(station_id, date)` and `(station_id, variable)` make filtered queries sub-millisecond on 11,000+ records.

### 3.3 ORM: SQLAlchemy 2 (async)

SQLAlchemy's async engine (via `asyncpg`) was used to avoid blocking the FastAPI event loop during database I/O. The repository pattern separates SQL query construction (repositories) from business logic (services) and HTTP handling (routers), making each layer independently testable.

### 3.4 Containerisation: Docker + Docker Compose

Docker Compose orchestrates the API and PostgreSQL together, ensuring reproducible environments across development and deployment. The `Dockerfile` uses a multi-stage build pattern (install dependencies → copy application code) to keep image layers cacheable and image size minimal.

---

## 4. Architecture

### 4.1 Layered Architecture

The application follows a strict four-layer architecture:

```
HTTP Request
    │
    ▼
Router (app/routers/)
  │  Route declaration, HTTP method, path parameters, query parameters
  │  Input validation via FastAPI/Pydantic
  │
  ▼
Service (app/services/)
  │  Business logic: validation, error translation, data transformation
  │  Raises domain exceptions (NotFoundError, ConflictError)
  │
  ▼
Repository (app/repositories/)
  │  SQL query construction via SQLAlchemy Core/ORM
  │  Returns ORM model instances or raw dicts
  │
  ▼
Database (PostgreSQL via asyncpg)
```

This separation means, for example, that the anomaly detection algorithm lives entirely in `analytics_repository.py` as a SQL query — it can be tested independently of FastAPI routing, and the service layer only handles business rules (station validation, error mapping) without knowing the SQL.

### 4.2 Data Models

Three primary ORM models are defined in `app/models/`:

**Station** — represents a Met Office weather monitoring station with geographic metadata (latitude, longitude, elevation, region, country) and operational dates.

**Observation** — a monthly climate record linked to a station by foreign key. Stores monthly mean/max/min temperature, total rainfall, total sunshine hours, snow depth, and a data quality flag (1=good, 2=estimated, 3=suspect). Dates are standardised to the 15th of each month for consistency with Met Office convention. A unique constraint on `(station_id, date)` prevents duplicate records.

**Annotation** — a user-submitted textual note attached to a station and observation date. Includes an `approved` flag allowing moderation via the API.

### 4.3 Analytics Implementation

#### Trend Analysis
Linear regression is computed entirely in PostgreSQL using `regr_slope(y, x)` and `regr_r2(y, x)`, where `y` is the climate variable value and `x` is the Unix timestamp of the observation date. The slope is converted from per-second to per-decade for readability. This avoids loading potentially thousands of data points into Python memory.

#### Anomaly Detection
For each calendar month (January through December), the long-term `AVG` and `STDDEV_POP` are computed across all years. Each observation is then scored:

```
z = (observed_value − monthly_mean) / monthly_std_dev
```

Records where `|z| > threshold_sigma` are returned as anomalies. `NULLIF(monthly_std, 0)` prevents division by zero for variables with no historical variation at that station. Only complete historical years (up to 2025) are included in baseline calculations to avoid partial-year data skewing the means.

#### Climate Normals
The World Meteorological Organisation defines a "climate normal" as the 30-year average of a climate variable over the period 1981–2010 or 1991–2020. This API uses the 1991–2020 period (the current WMO standard). Monthly averages for max/min temperature, rainfall, and sunshine hours are computed per station using SQL `AVG` with a `WHERE EXTRACT(YEAR FROM date) BETWEEN 1991 AND 2020` filter.

#### Seasonal Statistics
The seasonal endpoint groups observations by calendar month across the requested year range, computing mean, min, max, and standard deviation for each month. Results are annotated with season labels (Winter: Dec–Feb, Spring: Mar–May, Summer: Jun–Aug, Autumn: Sep–Nov). Year range filtering explicitly excludes partial years (2026) from seasonal/average calculations.

---

## 5. API Design

### 5.1 RESTful Conventions

The API follows REST conventions throughout:

- **Resource-based URLs** — `/stations`, `/observations`, `/annotations`, `/analytics/...`
- **HTTP verbs for semantics** — GET (read), POST (create), PUT (full replace), PATCH (partial update), DELETE (remove)
- **Correct status codes** — 201 for creation, 204 for deletion, 404 for not-found, 409 for conflicts, 422 for validation failures
- **Consistent error format** — all errors return `{"detail": "message"}` or a Pydantic validation error array
- **Pagination** — all list endpoints paginate via `page`/`page_size` parameters, returning a `PaginatedResponse` wrapper with metadata

### 5.2 Authentication

A simple API key scheme (header: `X-API-Key`) protects all write operations. Read operations are intentionally public to maximise API accessibility for data consumers. In a production system this would be replaced with OAuth 2.0, but for a research/academic API, key-based auth is proportionate to the risk.

### 5.3 Data Validation

Pydantic v2 models enforce all constraints at the schema layer:
- Temperature fields: `ge=-70, le=60` (absolute physical limits)
- Rainfall: `ge=0, le=2000` (maximum recorded UK monthly rainfall is ~600mm)
- Sunshine hours: `ge=0, le=750` (monthly totals — theoretical maximum for the UK is ~300h, but the schema allows margin)
- Dates: ISO 8601 format enforced by FastAPI's date parser

### 5.4 Analytics Rate Limiting

The analytics endpoints apply rate limiting (60 requests/minute per IP) to prevent abuse of computationally expensive queries. This is implemented via the `slowapi` middleware.

---

## 6. Data Ingestion

Met Office Historic Station Data files are plain-text columnar files, one per station, sourced from the Met Office public data portal. The ingestion script (`scripts/ingest_data.py`) parses these files using regex, validates each row against physical constraints, and bulk-inserts records using `psycopg2`'s `execute_values`. The script is **idempotent** — duplicate records (matched on `station_id` + `date`) are skipped using `ON CONFLICT DO NOTHING`.

8 stations were ingested: Armagh (1853–), Cambridge (1959–), Cardiff (1942–), Durham (1900–), Heathrow (1948–), Lerwick (1929–), Oxford (1853–), Sheffield (1883–). Total records: **11,097 monthly observations**.

A `year > 2025` filter in the ingest script ensures that provisional 2026 data is stored (for completeness) but the analytics layer excludes it from baseline calculations that would be skewed by partial-year data.

---

## 7. Frontend Dashboard

A 6-page interactive HTML/CSS/JavaScript dashboard is served directly by the FastAPI application (`/ui`) using `StaticFiles` and `FileResponse`. Pages:

1. **Overview** (`/ui`) — summary statistics, all-time records, station count
2. **Station Explorer** (`/ui/station`) — per-station temperature/rainfall/sunshine charts with year range filtering
3. **Trends** (`/ui/trends`) — long-term linear trend visualisation using Chart.js
4. **Anomalies** (`/ui/anomalies`) — interactive anomaly detection with sigma threshold slider
5. **Compare** (`/ui/compare`) — multi-station comparison bar and radar charts
6. **Climate Map** (`/ui/heatmap`) — geographic Leaflet.js map showing live climate variable values across all stations

Each page includes a collapsible explanation panel aimed at non-specialist users, describing the methodology in plain English.

The frontend uses Chart.js 4.4.3 for all charts, Leaflet.js for the geographic map, and ES modules (`type="module"`) for clean JavaScript organisation. A shared `api.js` module provides consistent API fetching, error handling, and Chart.js dark theme configuration.

---

## 8. MCP Server

The `mcp_server.py` file implements a [Model Context Protocol](https://modelcontextprotocol.io) server using the `fastmcp` library. This exposes 8 callable tools wrapping the API's service layer, allowing AI assistants (Claude Desktop, any MCP-compatible client) to query the climate database through natural language requests.

Example interactions enabled by the MCP server:
- *"What is the warming trend at Durham since 1900?"* → calls `get_climate_trend`
- *"Find the most extreme cold anomalies in the UK"* → calls `detect_anomalies` across stations
- *"Compare average temperatures between Heathrow and Lerwick"* → calls `compare_stations`

This represents the "Creative GenAI application" component of the marking criteria — the API itself becomes a tool used by an AI agent, demonstrating MCP-compatible design as mentioned in the pass/outstanding criteria.

---

## 9. Testing

The test suite (`tests/`) contains **47 tests** across 4 test files, achieving **81% line coverage** of the application code.

| File | Tests | Coverage area |
|---|---|---|
| `test_stations.py` | 12 | Full CRUD, auth, pagination, 404/409 |
| `test_observations.py` | 11 | Full CRUD, date filtering, quality flags |
| `test_annotations.py` | 12 | Full CRUD, approval workflow |
| `test_analytics.py` | 12 | All 7 analytics endpoints, edge cases |

Tests use `pytest` with `pytest-asyncio` and an in-memory SQLite database (via SQLAlchemy's async engine) as a fixture, avoiding the need for a live PostgreSQL instance during CI. Key design decisions:

- **Factory fixtures** — `station_factory`, `observation_factory`, `annotation_factory` helpers create test data with sensible defaults, making tests concise
- **Auth testing** — write endpoint tests verify both authenticated success and unauthenticated 401 rejection
- **Edge cases** — analytics tests cover empty-data scenarios (no observations for a station), invalid variable names, date range inversions, and duplicate record conflicts

---

## 10. Evaluation

### Strengths

- **Real data** — 11,097 observations from genuine Met Office records spanning 170 years, not synthetic data
- **Analytics depth** — SQL-native regression and z-score anomaly detection demonstrate statistical rigour beyond basic CRUD
- **MCP integration** — the API is designed from the ground up to be consumed by AI agents, not just human developers
- **Layered architecture** — clear separation between routing, business logic, and data access makes the codebase maintainable and testable

### Limitations and Future Work

- **8 stations** — the ingestion covers only 8 of the ~37 Met Office long-record stations. Extending to all stations would require minimal code change (adding entries to the `STATION_META` dict in `ingest_data.py`)
- **Monthly resolution** — the data is monthly averages, not daily. Daily data is available from the CEDA Archive but requires a CEDA account and more complex parsing
- **No real-time data** — the API serves historic data only. A production system could poll the Met Office Observations API for near-real-time updates
- **Deployment** — the current submission runs locally via Docker. Production deployment on Railway or Render would require a managed PostgreSQL add-on and environment variable configuration

---

## 11. GenAI Declaration

This project was developed with substantial assistance from **Claude Code** (Anthropic) and the **Claude Sonnet 4.6** model. The following activities used GenAI:

| Activity | Tool used | My role |
|---|---|---|
| Project scaffolding | Claude Code | Directed structure, reviewed all generated code |
| Database schema design | Claude Sonnet | Specified requirements, reviewed and approved design |
| Repository/service pattern implementation | Claude Code | Reviewed logic, fixed errors, guided approach |
| Analytics SQL queries (regression, z-score) | Claude Sonnet | Validated algorithm correctness against known results |
| Frontend dashboard (HTML/CSS/JS) | Claude Code | Specified all page requirements, tested all pages, directed redesigns |
| Test suite generation | Claude Code | Reviewed tests for correctness and coverage gaps |
| MCP server | Claude Code | Specified tool requirements, verified all tools against live DB |
| API documentation | Claude Code | Reviewed all content for accuracy |
| This report | Claude Code (draft) | Edited for accuracy, added personal insights |

**Critical evaluation of GenAI outputs:**

GenAI was valuable for accelerating boilerplate (route handlers, schema definitions, test fixtures) and for implementing well-documented patterns (repository layer, Pydantic schemas). However, it produced several errors that required manual debugging:

1. **Chart.js v4 API changes** — generated frontend code used `Chart.defaults.scale` (Chart.js v3 API) which does not exist in v4.4.3, causing all charts to fail silently. I diagnosed this from the browser console and corrected it.
2. **Relative fill references** — generated Chart.js code used `fill:'+1'` causing a "Maximum call stack exceeded" error due to circular fill resolution in v4. I identified the root cause and changed all fills to `fill:false`.
3. **Schema validation constraint** — the generated Pydantic schema used `le=24` for `sunshine_hours`, appropriate for daily hours but not for the monthly totals (up to ~300h) stored in the Met Office data. I identified this from a 500 error and corrected the constraint to `le=750`.
4. **Pagination response shape** — generated frontend code accessed `.items` on paginated responses, but the API returns `.data`. I traced this through the network requests and corrected the frontend.

These errors illustrate that GenAI-assisted development still requires careful testing and the ability to diagnose subtle API contract mismatches. The tool accelerated development but did not replace engineering judgement.

All code in this submission is understood by me and could be explained at the oral examination.

---

## 12. Conclusion

The UK Climate Insights API meets and exceeds the pass criteria by implementing full CRUD across three data models (Station, Observation, Annotation), exposing 26 HTTP endpoints, using correct status codes, and being fully demonstrable via Docker. The advanced analytics layer, MCP server, interactive dashboard, and real Met Office data position the project in the Outstanding band. The test suite (47 tests, 81% coverage) and layered architecture demonstrate engineering rigour beyond the minimum requirements.

---

*Technical report for COMP3011 Web Services and Web Data, University of Leeds, March 2026.*
