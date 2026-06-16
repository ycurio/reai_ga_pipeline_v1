# REAI Georgia Pipeline

Production starter for statewide Georgia real-estate distress intelligence.

## Implemented now
- Normalized source model
- Source adapter interface
- FEMA NFHL adapter for flood risk when lat/lon is available
- PACER bankruptcy adapter shell with configurable endpoint and credentials
- GSCCCA CSV export adapter for HOA liens, tax liens, judgments, lis pendens, deed under power, mechanics liens
- Distress scoring
- CLI runner
- Pytest tests

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run
```bash
python app.py --leads sample_leads.csv --gsccca-dir data/gsccca_exports --out data/output/results.json
```

## Test
```bash
pytest -q
```

## GSCCCA workflow
GSCCCA does not publish a simple public bulk API for these searches. Use an approved GSCCCA account/search/export workflow, then place CSV exports in `data/gsccca_exports`.

## PACER workflow
Add PACER credentials to `.env`, confirm current PCL API endpoint/payload from your PACER account documentation, then run with `--include-pacer`.
