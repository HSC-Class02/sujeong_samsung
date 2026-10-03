from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import dart_agent_v2 as mod


def base_rows():
    common = {
        "cost_of_sales": 600, "gross_profit": 400, "sga": 200,
        "pretax_income": 100, "interest_expense": 20, "income_tax": 20,
        "depreciation_amortization": 50, "total_assets": 2000, "cash": 200,
        "receivables": 180, "inventory": 240, "current_assets": 700,
        "current_liabilities": 500, "payables": 160, "ppe": 800,
        "total_liabilities": 800, "interest_bearing_debt": 300,
        "total_equity": 1200, "cfi": -100, "cff": -80,
    }
    q1 = dict(common, year=2025, period="quarterly_q1", reprt_code="11013",
              revenue=1000, operating_income=200, net_income=80,
              controlling_net_income=80, cfo=250, capex=100)
    h1 = dict(common, year=2025, period="half_year", reprt_code="11012",
              revenue=2100, operating_income=420, net_income=170,
              controlling_net_income=170, cfo=520, capex=220)
    q3 = dict(common, year=2025, period="quarterly_q3", reprt_code="11014",
              revenue=3300, operating_income=650, net_income=270,
              controlling_net_income=270, cfo=780, capex=340)
    ann = dict(common, year=2025, period="annual", reprt_code="11011",
               revenue=4500, operating_income=900, net_income=400,
               controlling_net_income=400, cfo=1100, capex=480)
    return pd.DataFrame([q1, h1, q3, ann])


def run():
    assert mod.num("1,234") == 1234
    assert mod.num("(123)") == -123
    assert mod.num("-") is None

    df = mod.ratios(base_rows())
    annual = df[df.period == "annual"].iloc[0]
    assert round(annual["ebitda"], 2) == 950
    assert round(annual["operating_margin"], 2) == 20.0
    assert round(annual["fcf"], 2) == 620
    assert round(annual["interest_coverage"], 2) == 45.0
    assert round(annual["net_debt"], 2) == 100

    qdf = mod.standalone_quarters(base_rows())
    q2 = qdf[qdf.period == "Q2"].iloc[0]
    q3 = qdf[qdf.period == "Q3"].iloc[0]
    q4 = qdf[qdf.period == "Q4"].iloc[0]
    assert q2["revenue"] == 1100
    assert q3["revenue"] == 1200
    assert q4["revenue"] == 1200
    assert q2["cfo"] == 270
    assert q4["cfo"] == 320
    print("All financial-ratio tests passed.")


if __name__ == "__main__":
    run()
