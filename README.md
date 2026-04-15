# Marketing Budget Allocation

Business analytics tool for media planning with three major workflows:

1. Insights
- S-Curves by brand x market (TV and Digital response)
- Contribution drivers and YoY movement views
- Trinity report generation from model outputs

2. Budget Allocation (Step 1 and Step 2)
- Step 1: National -> Brand budget allocation
- Step 2: Brand -> Market scenario generation with constraints
- Scenario browser with ranking, filtering, and market-level split details

3. AI-Assisted Generation
- Gemini-guided strategy controls for scenario exploration
- Async scenario job execution and paginated results
- AI summaries/reports where configured

## Repo Structure
- `marketing-budget-allocation-backend/` FastAPI backend
- `marketing-budget-allocation-frontend/` React + Vite frontend
- `results/` input Excel files used by auto-config and optimization

## Required Data Files (Local)
Place source files in `results/` (local machine):
- `Modeling_Master_D0_18.08 2.xlsx`
- `AllBrands_updated_constraint_vol_converted_models_06.10.xlsx`
- `Max Reach.xlsx`
- any additional local files your run requires

Note: `results/` is gitignored by design.

## Prerequisites
- Python 3.10+ (recommended 3.11)
- Node.js 18+
- npm

## Environment Variables (Local Only)
Do not commit real secrets.

Backend reads these env vars:
- `GEMINI_API_KEY` (optional but required for Gemini-powered outputs)
- `GEMINI_MODEL` (optional, default: `gemini-2.5-flash`)
- `MBA_RESULTS_DIR` (optional override for results folder path)

### PowerShell example (session-only)
```powershell
$env:GEMINI_API_KEY="your_key_here"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

### Optional local env file approach
Create `marketing-budget-allocation-backend/.env` locally (already gitignored), for example:
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```
Then run backend with:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8020 --env-file .env
```

## Run Locally

### 1) Start Backend
```powershell
cd "marketing-budget-allocation-backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8020
```

Backend health/doc URLs:
- `http://127.0.0.1:8020/health`
- `http://127.0.0.1:8020/docs`

### 2) Start Frontend (new terminal)
```powershell
cd "marketing-budget-allocation-frontend"
npm install
npm run dev -- --host 0.0.0.0 --port 5190
```

Frontend URL:
- `http://127.0.0.1:5190`

## Share on Local Network
Run both services with `--host 0.0.0.0` (as above), then share:
- `http://<YOUR_LOCAL_IP>:5190`

If other devices cannot access:
- allow inbound firewall rules for ports `5190` and `8020`
- ensure both devices are on same LAN/VPN

## Common Troubleshooting

### "Failed to auto-load configuration"
Usually one of:
- backend not running on port `8020`
- API URL mismatch
- blocked by firewall/network isolation
- missing or unreadable files in `results/`

Quick checks:
```powershell
Invoke-WebRequest http://127.0.0.1:8020/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8020/api/auto-config -UseBasicParsing
```

### Missing Python packages
If backend errors with `ModuleNotFoundError`:
```powershell
pip install -r requirements.txt
```

## Security Notes
- Never commit API keys.
- Keep `.env` local only.
- Rotate keys if accidentally exposed.
