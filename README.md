# REAI Georgia Pipeline

Production starter for statewide Georgia real-estate distress intelligence.

## Implemented now
- Normalized source model
- Source adapter interface
- PACER bankruptcy adapter shell with configurable endpoint and credentials
- GSCCCA CSV export adapter for HOA liens, tax liens, judgments, lis pendens, deed under power, mechanics liens
- Distress scoring
- CLI runner
- Export-time lead expansion for multiple email addresses
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

## Full pipeline from start to Instantly
```bash
# 1) Convert source exports into one combined leads.csv
python reai/convert_leads.py ga_sfr.xlsx --type foreclosure -o leads.csv
python reai/convert_leads.py lis_pendis_nod_20260619.xlsx --type foreclosure -o leads.csv --append
python reai/convert_leads.py Successors_Data_20260305.xlsx --type successor -o leads.csv --append

# 2) Optional: enrich missing phone/email values
python reai/datazapp_append.py leads.csv

# 3) Score leads and produce scored results JSON
python app.py --leads leads.csv --gsccca-dir data/gsccca_exports --out data/output/results.json

# 4) Export CRM/dialer-ready files (including email-based row expansion)
python export_result.py --input data/output/results.json --outdir data/output

# 5) Optional: generate an HTML dashboard
python visualize_results.py --input data/output/results.json --output data/output/results.html

# 6) Push to Instantly (dry-run first)
python push_to_instantly.py --input data/output/results.json --min-score 25 --campaign-id YOUR_CAMPAIGN_ID

# 7) Push live to Instantly when ready
python push_to_instantly.py --input data/output/results.json --min-score 25 --campaign-id YOUR_CAMPAIGN_ID --live
```

## Test
```bash
pytest -q
```

## GSCCCA workflow
GSCCCA does not publish a simple public bulk API for these searches. Use an approved GSCCCA account/search/export workflow, then place CSV exports in `data/gsccca_exports`.

## PACER workflow
Add PACER credentials to `.env`, confirm current PCL API endpoint/payload from your PACER account documentation, then run with `--include-pacer`.

## DataZapp workflow
DataZapp gates their API docs behind a sales contact (api@datazapp.com per their knowledge base), so the
endpoint path and response field names in `reai/datazapp_append.py` are inferred from their public marketing
examples, not a confirmed spec. Email them for API access, confirm the real request/response shape, update
the adapter if it differs, then add `DATAZAPP_API_KEY` (and `DATAZAPP_BASE_URL` if it's not `/v1`) to `.env`.
## COPY FILE TO VSCODE
cp "C:\Users\Optiplex7060\Downloads\<FILENAME.XLSX>" .
## Run the app step by step

**1. Convert each lead export into a combined `leads.csv`** (first call writes, subsequent calls merge in):
```bash 
python reai/convert_leads.py your_file.xlsx --type [foreclosure|successor] -o leads.csv [--append]

python reai/convert_leads.py ga_sfr.xlsx --type foreclosure -o leads.csv
python reai/convert_leads.py lis_pendis_nod_20260619.xlsx --type foreclosure -o leads.csv --append
python reai/convert_leads.py Successors_Data_20260305.xlsx --type successor -o leads.csv --append
```
If the same lead (matched by normalized owner name + property address) is seen under more than one seed
type - e.g. a foreclosure file and a successor file both list the same property  - the types combine as a
pipe-delimited list (`foreclosure|successor`) rather than picking one. `distress_score()` sums distinct
record types rather than taking the max, so a lead seeded under multiple types scores higher, not the same.

If a lead has multiple email addresses after skip-tracing, the export phase expands that one scored lead into
multiple rows so each email gets its own output record while preserving the same property and distress data.

**2. Skip-trace: fill in missing phone/email via DataZapp:**
```bash
python reai/datazapp_append.py leads.csv
```
Only calls out for leads that have neither phone nor email, and overwrites `leads.csv` in place with matches.
Requires `DATAZAPP_API_KEY` (and optionally `DATAZAPP_BASE_URL`) in `.env` - see the DataZapp workflow note below.

**3. Run the scoring pipeline:**
```bash
python app.py --leads leads.csv --include-pacer --gsccca-dir data/gsccca_exports --out data/output/results.json
# add --include-pacer to also run live PACER bankruptcy search (billed, real network calls)
# add --limit N to only process the first N leads
```

**4. Export to CRM/dialer-ready files:**
```bash
python export_result.py
# writes data/output/results_summary.csv, results_detailed.csv, results_sorted.json
```

After scoring, each lead is expanded into one output row per unique email address found in the lead's `email` / `all_emails` fields. This lets downstream CRM and outreach tools receive one record per email without changing the scoring step itself.

**4b. (Optional) Build an HTML dashboard to eyeball the results:**
```bash
python visualize_results.py --input data/output/results.json --output data/output/results.html
# self-contained report: score distribution chart + sortable/filterable lead table, no server needed
```

**5. Push to GHL and/or Instantly** (both default to dry-run - add `--live` to actually call the API):
```bash
python push_to_ghl.py --min-score 25 --live
python push_to_instantly.py --min-score 25 --live
python push_to_instantly.py --input data/output/results.json --min-score 25 --live


```

## Distress Scoring Model

`reai/scoring.py` computes a 0-100 score per lead from every `SourceRecord` found for it - the seeded
intake type from `convert_leads.py`, plus whatever GSCCCA/PACER find live. The same record type is
only counted once per lead (no stacking duplicate filings of the same type), but distinct types add together.

**Base weights by record type:**

| Record type | Points |
|---|---|
| Deed under power | 30 |
| Foreclosure | 30 |
| Lis pendens | 25 |
| Probate | 20 |
| Successor | 20 |
| Bankruptcy | 18 |
| HOA lien | 18 |
| Tax lien | 18 |
| Notice of default | 15 |
| Mechanics lien | 12 |
| Judgment | 12 |

**PACER bankruptcy bonuses** (on top of the base 18 points for finding a bankruptcy record):

| Bonus | Condition | Points |
|---|---|---|
| Recency | Most recent filing within 90 days | +15 |
| | Most recent filing 91-180 days ago | +12 |
| | Most recent filing 181-365 days ago | +8 |
| | Most recent filing older than 365 days | +0 |
| Repeat filer | 2 distinct bankruptcy filings found | +2 |
| | 3+ distinct bankruptcy filings found | +5 |

**Stacking bonus** (breadth of distress signal, across all sources/seed types for the lead):

| Distinct distress types found | Points |
|---|---|
| 1 | +0 |
| 2 | +5 |
| 3+ | +10 |

The final score is the sum of all of the above, clamped to the 0-100 range.

   