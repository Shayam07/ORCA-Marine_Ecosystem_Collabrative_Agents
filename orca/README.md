# 🌊 ORCA — Marine EcOsystem Reasoning with Collaborative Agents

**Multi-agent marine ecosystem intelligence and reasoning platform** for SIH 2026 Problem Statement 176.

ORCA combines real marine/environmental datasets with specialized AI agents that independently analyze evidence, then fuse their findings into explainable ecosystem hypotheses with programmatic confidence scores.

## Architecture

```
User → React Frontend → FastAPI API → Query Understanding
    → Coordinator Agent → Parallel Specialized Agents
    → Evidence Fusion → Temporal/Spatial Reasoning
    → Hypothesis Engine → Confidence Engine → Response
```

### Agents
| Agent | Analyzes |
|-------|----------|
| 🌊 Ocean | SST, salinity, currents, sea level |
| 🛰️ Satellite | Chlorophyll, ocean color, satellite SST |
| 🐋 Biology | Ecological indicators, productivity |
| ⛅ Weather | Wind, storms, atmospheric conditions |
| 🐟 Fisheries | Vessel activity, fishing pressure |
| 🏭 Pollution | Turbidity, sediment, water quality |
| 📚 Literature | Scientific papers and research context |

### Data Providers
- **ISRO/MOSDAC** — Indian Earth observation data
- **Copernicus Marine** — European ocean monitoring
- **NASA** — Satellite and ocean data
- **NOAA** — Ocean and atmospheric data
- **ERA5/Weather** — Atmospheric reanalysis
- **Global Fishing Watch** — Vessel activity
- **Scientific Literature** — Crossref, Semantic Scholar

## Quick Start

### Option 1: Docker (Recommended)

```bash
cd orca
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000

### Option 2: Local Development

**Backend:**
```bash
cd orca/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd orca/frontend
npm install
npm run dev
```

Open http://localhost:5173

## Usage

1. **Select a region** on the interactive map (or use the default Indian west coast)
2. **Ask a question** like:
   - "Why has chlorophyll decreased near the west coast of India?"
   - "Is this region showing ecosystem anomalies?"
   - "Compare current SST with historical baselines"
3. **View results**:
   - Ecosystem status and confidence score
   - Agent findings with evidence
   - Multiple ranked hypotheses
   - Temporal and spatial relationships
   - Full agent execution trace
   - Data source transparency

## Data Modes

ORCA operates in **LIVE mode by default**, fetching real data from connected providers:

- **● LIVE** — Real-time data from connected providers (default)
- **● CACHED** — Previously fetched real data from cache
- **● DEMO** — Synthetic data (only when explicitly selected)
- **● NO_DATA** — No data available for the requested location/time

DEMO mode is never used silently in production. The UI always shows the actual data mode.

## Connecting Real Data

Set credentials in `.env`:

```bash
# Copernicus Marine
COPERNICUS_USERNAME=your_username
COPERNICUS_PASSWORD=your_password

# NASA
NASA_USERNAME=your_username
NASA_PASSWORD=your_password

# Global Fishing Watch
FISHING_API_KEY=your_key
```

Providers fail gracefully — if one is unavailable, ORCA uses others. Partial data still produces useful analysis.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/query` | POST | Run analysis query |
| `/api/v1/analysis/{id}` | GET | Get saved analysis |
| `/api/v1/map/layers` | GET | Available map layers |
| `/api/v1/map/data/{layer}` | GET | Layer data (GeoJSON) |
| `/api/v1/sources` | GET | Data source info |
| `/api/v1/sources/status` | GET | Provider health |
| `/api/v1/agents/status` | GET | Agent status |
| `/api/v1/health` | GET | System health |

## Non-Negotiable Principles

1. **No fabricated data** — All quantitative observations come from datasets or ML calculations
2. **Separate observation from inference** — Clear distinction between OBSERVED, DERIVED, PREDICTED, and HYPOTHESIZED
3. **Full provenance** — Every observation has source, dataset, timestamp, location, quality
4. **Replaceable providers** — Agent-agnostic data layer
5. **Graceful degradation** — Works with demo data when APIs unavailable

## Tech Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, MapLibre GL JS, Recharts
- **Backend:** Python, FastAPI, Pydantic, asyncio, httpx
- **Database:** PostgreSQL, PostGIS, Redis
- **ML:** scikit-learn (Isolation Forest), NumPy, Pandas
- **Geospatial:** GeoPandas, Shapely, xarray

## License

MIT
