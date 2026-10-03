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
    for idx in df.index[hist]:
        vals = [float(df.at[idx, c]) for c in money_fields if pd.notna(df.at[idx, c])]
        scale = 1_000_000.0 if any(abs(x) >= 1e12 for x in vals) else 1.0
        if scale != 1.0:
            for c in money_fields:
                if pd.notna(df.at[idx, c]):
                    df.at[idx, c] = float(df.at[idx, c]) / scale

    if "operating_income" in df and "depreciation_amortization" in df:
        df["ebitda"] = df["operating_income"] + df["depreciation_amortization"].abs()

    df = ratios(df)
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    payload = df.where(pd.notna(df), None).to_dict(orient="records")
    (PROC / "samsung_financials.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    SITE.mkdir(parents=True, exist_ok=True)
    for name in ["samsung_financials.csv", "samsung_financials.json"]:
        (SITE / name).write_bytes((PROC / name).read_bytes())
    print("Historical unit normalization and derived-metric recalculation completed.")

if __name__ == "__main__":
    main()
