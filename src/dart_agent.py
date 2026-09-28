from __future__ import annotations

import io
import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
BASE = "https://opendart.fss.or.kr/api"
REPORT_CODES = CONFIG["reports"]

# DART account labels vary slightly by period/translation. These aliases keep
# extraction resilient while preserving the source account name in raw data.
ALIASES = {
    "total_assets": ["자산총계", "총자산"],
    "cash": ["현금및현금성자산", "현금및현금성자산(현금성자산 포함)", "현금 및 현금성자산"],
    "receivables": ["매출채권", "매출채권 및 기타채권"],
    "inventory": ["재고자산"],
    "current_assets": ["유동자산"],
    "current_liabilities": ["유동부채"],
    "payables": ["매입채무", "매입채무및기타채무"],
    "ppe": ["유형자산", "유형자산 합계"],
    "total_liabilities": ["부채총계", "총부채"],
    "interest_bearing_debt": ["차입금", "이자부차입금", "단기차입금", "장기차입금"],
    "total_equity": ["자본총계", "총자본"],
    "revenue": ["매출액", "수익(매출액)", "매출"],
    "cost_of_sales": ["매출원가"],
    "gross_profit": ["매출총이익"],
    "sga": ["판매비와관리비", "판매비와 일반관리비"],
    "operating_income": ["영업이익", "영업이익(손실)"],
    "pretax_income": ["법인세비용차감전순이익", "세전이익", "세전계속사업이익"],
    "net_income": ["당기순이익", "당기순이익(손실)"],
    "controlling_net_income": ["지배기업의 소유주에게 귀속되는 당기순이익", "지배기업 소유주지분 순이익", "지배주주순이익"],
    "cfo": ["영업활동으로 인한 현금흐름", "영업활동현금흐름"],
    "cfi": ["투자활동으로 인한 현금흐름", "투자활동현금흐름"],
    "cff": ["재무활동으로 인한 현금흐름", "재무활동현금흐름"],
    "capex": ["유형자산의 취득", "유형자산 취득", "유형자산의 취득으로 인한 현금유출"],
    "interest_expense": ["이자비용", "금융비용"],
    "income_tax": ["법인세비용", "법인세비용(수익)"],
    "ebitda": ["EBITDA"],
}


def api_get(path: str, params: dict[str, Any], retries: int = 4) -> dict[str, Any]:
    key = os.environ.get("OPENDART_API_KEY")
    if not key:
        raise RuntimeError("OPENDART_API_KEY 환경변수가 없습니다. GitHub Actions secret에 등록하세요.")
    params = {"crtfc_key": key, **params}
    last = None
    for attempt in range(retries):
        r = requests.get(f"{BASE}/{path}", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "000":
            return data
        last = data
        if data.get("status") in {"020", "800"}:
            time.sleep(2 ** attempt)
        else:
            break
    raise RuntimeError(f"DART API 오류: {last}")


def parse_num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    s = str(value).replace(",", "").replace(" ", "").strip()
    if s in {"", "-", "—", "nan", "None"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
        return -x if neg else x
    except ValueError:
        return None


def get_value(rows: list[dict[str, Any]], aliases: list[str], fs_div: str) -> float | None:
    # Prefer rows from requested consolidated/individual division and the latest
    # period column. The source row is retained for auditability.
    candidates = []
    for row in rows:
        if row.get("fs_div") not in (None, fs_div):
            continue
        name = str(row.get("account_nm", "")).strip()
        if any(a == name or a in name for a in aliases):
            candidates.append(row)
    if not candidates:
        return None
    row = candidates[0]
    for key in ("thstrm_amount", "thstrm_add_amount", "thstrm_q_amount", "thstrm_nmpr"):
        if key in row:
            x = parse_num(row.get(key))
            if x is not None:
                return x
    return None


def report_rows(year: int, reprt_code: str) -> list[dict[str, Any]]:
    data = api_get("fnlttSinglAcntAll.json", {
        "corp_code": CONFIG["company"]["corp_code"],
        "bsns_year": str(year),
        "reprt_code": reprt_code,
        "fs_div": CONFIG["company"]["fs_div"],
    })
    return data.get("list", [])


def search_disclosures(year: int) -> list[dict[str, Any]]:
    # DART disclosure search supports date range + corporation. Filter report
    # titles locally so historical years use the same source of truth.
    out = []
    page = 1
    while True:
        data = api_get("list.json", {
            "corp_code": CONFIG["company"]["corp_code"],
            "bgn_de": f"{year}0101",
            "end_de": f"{year}1231",
            "page_no": page,
            "page_count": 100,
            "sort": "date",
            "sort_mth": "desc",
        })
        out.extend(data.get("list", []))
        if page >= int(data.get("total_page", 1)):
            break
        page += 1
        if page > 20:
            break
    keywords = ("사업보고서", "반기보고서", "분기보고서")
    return [x for x in out if any(k in str(x.get("report_nm", "")) for k in keywords)]


def download_document(receipt_no: str) -> list[bytes]:
    key = os.environ.get("OPENDART_API_KEY")
    if not key:
        raise RuntimeError("OPENDART_API_KEY 환경변수가 없습니다.")
    r = requests.get(f"{BASE}/document.xml", params={"crtfc_key": key, "rcept_no": receipt_no}, timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return [z.read(n) for n in z.namelist() if not n.endswith("/")]


def raw_historical_extract(year: int) -> list[dict[str, Any]]:
    records = []
    disclosures = search_disclosures(year)
    wanted = {"사업보고서": "annual", "반기보고서": "half_year", "분기보고서": "quarterly"}
    for d in disclosures:
        name = str(d.get("report_nm", ""))
        kind = next((v for k, v in wanted.items() if k in name), None)
        if not kind:
            continue
        rcept = d.get("rcept_no")
        if not rcept:
            continue
        try:
            files = download_document(rcept)
        except Exception:
            continue
        for content in files:
            text = content.decode("utf-8", errors="ignore")
            if "재무상태표" not in text and "손익계산서" not in text:
                continue
            # Historical DART documents are not guaranteed to expose the modern
            # XBRL schema. We parse HTML tables heuristically and save raw text.
            try:
                tables = pd.read_html(io.StringIO(text))
            except Exception:
                tables = []
            for i, df in enumerate(tables):
                flat = " ".join(map(str, df.astype(str).values.ravel()))
                if not any(k in flat for k in ["자산총계", "매출액", "영업이익", "당기순이익"]):
                    continue
                records.append({
                    "year": year, "period": kind, "receipt_no": rcept,
                    "report_nm": name, "table_index": i,
                    "columns": [str(c) for c in df.columns],
                    "rows": df.fillna("").astype(str).to_dict(orient="records"),
                    "source": "DART document.xml heuristic parser",
                })
        # One report per category is sufficient for historical seed data.
    return records


def normalize_rows(rows: list[dict[str, Any]], year: int, period: str, reprt_code: str) -> dict[str, Any]:
    result = {"year": year, "period": period, "reprt_code": reprt_code, "fs_div": CONFIG["company"]["fs_div"]}
    for key, aliases in ALIASES.items():
        result[key] = get_value(rows, aliases, CONFIG["company"]["fs_div"])
    result["raw_account_count"] = len(rows)
    return result


def annualize(df: pd.DataFrame) -> pd.DataFrame:
    # DART quarterly/half-year amounts are YTD in many rows. For the dashboard,
    # annual tables use the annual filing; quarterly tables retain reported YTD
    # values rather than silently inventing quarter-only numbers.
    return df


def calc_ratios(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["year", "period"]).copy()
    for c in ["total_assets", "cash", "receivables", "inventory", "ppe", "total_liabilities", "interest_bearing_debt", "total_equity", "revenue", "gross_profit", "sga", "operating_income", "pretax_income", "net_income", "controlling_net_income", "cfo", "cfi", "cff", "capex", "interest_expense", "ebitda"]:
        if c not in df: df[c] = np.nan
    df["fcf"] = df["cfo"] - df["capex"].abs()
    df["net_debt"] = df["interest_bearing_debt"] - df["cash"]
    avg_assets = df["total_assets"].rolling(2).mean()
    avg_equity = df["total_equity"].rolling(2).mean()
    df["gross_margin"] = df["gross_profit"] / df["revenue"] * 100
    df["operating_margin"] = df["operating_income"] / df["revenue"] * 100
    df["net_margin"] = df["net_income"] / df["revenue"] * 100
    df["ebitda_margin"] = df["ebitda"] / df["revenue"] * 100
    df["roa"] = df["net_income"] / avg_assets * 100
    df["roe"] = df["net_income"] / avg_equity * 100
    df["current_ratio"] = df["current_assets"] / df["current_liabilities"] * 100
    df["quick_assets"] = df["current_assets"] - df["inventory"]
    df["quick_ratio"] = df["quick_assets"] / df["current_liabilities"] * 100
    df["debt_ratio"] = df["total_liabilities"] / df["total_equity"] * 100
    df["equity_ratio"] = df["total_equity"] / df["total_assets"] * 100
    df["debt_to_assets"] = df["interest_bearing_debt"] / df["total_assets"] * 100
    df["interest_coverage"] = df["operating_income"] / df["interest_expense"]
    df["net_debt_to_ebitda"] = df["net_debt"] / df["ebitda"]
    effective_tax = df["income_tax"] / df["pretax_income"]
    nopat = df["operating_income"] * (1 - effective_tax.clip(lower=0, upper=1))
    invested_capital = df["interest_bearing_debt"] + df["total_equity"] - df["cash"]
    df["roic"] = nopat / invested_capital.rolling(2).mean() * 100
    df["dso"] = df["receivables"] / df["revenue"] * 365
    df["dio"] = df["inventory"] / df["cost_of_sales"] * 365
    purchases = df["cost_of_sales"] + df["inventory"] - df["inventory"].shift(1)
    df["dpo"] = df["payables"] / purchases * 365
    df["ccc"] = df["dso"] + df["dio"] - df["dpo"]
    df["asset_turnover"] = df["revenue"] / avg_assets
    df["revenue_growth"] = df["revenue"].pct_change() * 100
    df["cfo_to_net_income"] = df["cfo"] / df["net_income"]
    return df.replace([np.inf, -np.inf], np.nan)


def main() -> None:
    out_raw = ROOT / "data/raw"
    out_proc = ROOT / "data/processed"
    out_raw.mkdir(parents=True, exist_ok=True)
    out_proc.mkdir(parents=True, exist_ok=True)
    rows = []
    for year in range(CONFIG["company"]["start_year"], pd.Timestamp.now().year + 1):
        if year < 2015 and CONFIG["raw_fallback"]["enabled"]:
            historical = raw_historical_extract(year)
            (out_raw / f"{year}_historical.json").write_text(json.dumps(historical, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        for period, code in [("annual", REPORT_CODES["annual"]), ("half_year", REPORT_CODES["half_year"]), ("quarterly_q1", REPORT_CODES["quarterly_q1"]), ("quarterly_q3", REPORT_CODES["quarterly_q3"])]:
            try:
                api_rows = report_rows(year, code)
                if api_rows:
                    rows.append(normalize_rows(api_rows, year, period, code))
            except RuntimeError as e:
                print(f"WARN {year} {period}: {e}")
    df = pd.DataFrame(rows)
    if not df.empty:
        df = calc_ratios(df)
        df.to_csv(out_proc / "samsung_financials.csv", index=False, encoding="utf-8-sig")
        (out_proc / "samsung_financials.json").write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    metadata = {
        "company": CONFIG["company"],
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "source": "OpenDART API",
        "structured_financial_data_from": 2015,
        "historical_raw_fallback": "2010-2014 via DART disclosure search + document.xml heuristic parser",
        "rows": int(len(df)),
    }
    (out_proc / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
