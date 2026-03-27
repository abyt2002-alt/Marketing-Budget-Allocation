# Backend Structure

The backend is now organized for maintainability:

## Entry Point
- `app/main.py`
  - Thin bootstrap only.
  - Creates FastAPI app via `create_app()`.

## App Factory
- `app/core/app_factory.py`
  - FastAPI initialization.
  - CORS middleware setup.
  - Router registration.

## API Routers
- `app/api/router.py`
  - Aggregates all route groups.

- `app/api/routes/system.py`
  - `/health`
  - `/api/auto-config`

- `app/api/routes/optimization.py`
  - `/api/optimize-auto`
  - `/api/constraints-auto`
  - `/api/s-curves-auto`
  - `/api/contributions-auto`
  - `/api/yoy-growth-auto`
  - `/api/brand-allocation`

- `app/api/routes/insights.py`
  - `/api/insights-ai-summary`
  - `/api/insights-ai`
  - `/api/trinity-report`

- `app/api/routes/scenarios.py`
  - `/api/scenarios/jobs`
  - `/api/scenarios/jobs/{job_id}`
  - `/api/scenarios/jobs/{job_id}/results`

## Service Layer
- `app/services/engine.py`
  - Core MMM logic, optimization, S-curves, scenario generation, Trinity/Gemini flows.
  - Pydantic request models shared with routers.
  - `service_*` functions are router-safe orchestration entry points.

## Run Command
```powershell
cd "marketing-budget-allocation-backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload
```

