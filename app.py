from __future__ import annotations
import argparse, json
from pathlib import Path
from dotenv import load_dotenv
from reai.pipeline import default_sources, load_leads_csv, run_for_leads


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="REAI Georgia statewide source pipeline")
    p.add_argument("--leads", required=True, help="CSV with owner_name, parcel_id, property_address, county, state")
    p.add_argument("--gsccca-dir", default="data/gsccca_exports")
    p.add_argument("--include-pacer", action="store_true")
    p.add_argument("--out", default="data/output/results.json")
    args = p.parse_args()
 
    leads = load_leads_csv(args.leads)
    sources = default_sources(args.gsccca_dir, include_pacer=args.include_pacer)
    for s in sources:
        print(s.healthcheck().model_dump())
    results = run_for_leads(leads, sources)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
