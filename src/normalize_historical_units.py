from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dart_agent_v2 import ALL_FIELDS, ratios

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SITE = ROOT / "site" / "data" / "processed"

def main() -> None:
    csv = PROC / "samsung_financials.csv"
    if not csv.exists():
        return
    df = pd.read_csv(csv)
    money_fields = [c for c in ALL_FIELDS if c in df.columns]
    hist = df["year"].astype(int) < 2015
    if not hist.any():
        return

    # OpenDART XBRL monetary facts can be stored in KRW while the structured
    # financial API is presented in million KRW. Historical rows are scaled only
    # when their magnitude strongly indicates raw KRW, leaving document-table
    # values already expressed in million KRW unchanged.
    for idx in df.index[hist]:
        scale = 1_000_000.0 if any(abs(float(df.at[idx, c])) >= 1e12 for c in money_fields if pd.notna(df.at[idx, c])) else 1.0
        if scale != 1.0:
            for c in money_fields:
                if pd.notna(df.at[idx, c]):
                    df.at[idx, c] = float(df.at[idx, c]) / scale

    df = ratios(df)
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    payload = df.replace({pd.NA: None, float("inf"): None, float("-inf"): None}).where(pd.notna(df), None).to_dict(orient="records")
    (PROC / "samsung_financials.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    SITE.mkdir(parents=True, exist_ok=True)
    for name in ["samsung_financials.csv", "samsung_financials.json"]:
        (SITE / name).write_bytes((PROC / name).read_bytes())
    print("Historical unit normalization completed.")

if __name__ == "__main__":
    main()
