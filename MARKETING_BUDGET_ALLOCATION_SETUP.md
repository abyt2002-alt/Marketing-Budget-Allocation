# Marketing Budget Allocation - Local Run

## Ports (locked)
- Frontend (Vite): `5190`
- Backend (FastAPI): `8020`
- Vite preview: `5191`

## 1) Start Backend
```powershell
cd "marketing-budget-allocation-backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload
```

## 2) Start Frontend
```powershell
cd "marketing-budget-allocation-frontend"
copy .env.example .env
npm install
npm run dev
```

Open: `http://127.0.0.1:5190`

## Notes
- Put these files in `results/` (already present in this workspace):
  - `Modeling_Master_D0_18.08 2.xlsx`
  - `AllBrands_updated_constraint_vol_converted_models_06.10.xlsx`
  - `Max Reach.xlsx`
- Frontend auto-loads files from `results/` via `GET /api/auto-config`.
- Allocation run uses `POST /api/optimize-auto` with selected brand/markets.
