from __future__ import annotations

import io
import json
import os
import re
import time
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
BASE = "https://opendart.fss.or.kr/api"
COMP = CFG["company"]
CODES = CFG["reports"]
FS_DIV = COMP["fs_div"]
FLOW = ["revenue","cost_of_sales","gross_profit","sga","operating_income","pretax_income","net_income","controlling_net_income","cfo","cfi","cff","capex","interest_expense","income_tax","depreciation_amortization"]
BAL = ["total_assets","cash","receivables","inventory","current_assets","current_liabilities","payables","ppe","total_liabilities","interest_bearing_debt","total_equity"]
ALL_FIELDS = FLOW + BAL

ALIASES = {
 "total_assets":["자산총계","총자산"], "cash":["현금및현금성자산","현금 및 현금성자산"],
 "receivables":["매출채권","매출채권 및 기타채권","매출채권및기타채권"], "inventory":["재고자산"],
 "current_assets":["유동자산"], "current_liabilities":["유동부채"], "payables":["매입채무","매입채무 및 기타채무","매입채무및기타채무"],
 "ppe":["유형자산","유형자산 합계","유형자산합계"], "total_liabilities":["부채총계","총부채"], "total_equity":["자본총계","총자본"],
 "revenue":["매출액","수익(매출액)","수익 (매출액)","매출"], "cost_of_sales":["매출원가"], "gross_profit":["매출총이익"],
 "sga":["판매비와관리비","판매비와 일반관리비"], "operating_income":["영업이익","영업이익(손실)","영업이익 (손실)"],
 "pretax_income":["법인세비용차감전순이익","세전이익","세전계속사업이익"], "net_income":["당기순이익","당기순이익(손실)","당기순이익 (손실)"],
 "controlling_net_income":["지배기업의 소유주에게 귀속되는 당기순이익","지배기업 소유주지분 순이익","지배주주순이익"],
 "cfo":["영업활동으로 인한 현금흐름","영업활동현금흐름"], "cfi":["투자활동으로 인한 현금흐름","투자활동현금흐름"],
 "cff":["재무활동으로 인한 현금흐름","재무활동현금흐름"], "capex":["유형자산의 취득","유형자산 취득","유형자산의 취득으로 인한 현금유출"],
 "interest_expense":["이자비용","금융비용"], "income_tax":["법인세비용","법인세비용(수익)"],
 "depreciation_amortization":["감가상각비","감가상각비 및 무형자산상각비","감가상각비및무형자산상각비"],
 "interest_bearing_debt":["차입금","이자부차입금","차입금및사채","차입금 및 사채"],
}


def key() -> str:
    k = os.getenv("OPENDART_API_KEY", "").strip()
    if len(k) != 40:
        raise RuntimeError("OPENDART_API_KEY가 없거나 40자리 인증키가 아닙니다.")
    return k


def get_json(endpoint: str, params: dict[str, Any], retries: int = 4) -> dict[str, Any]:
    p = {"crtfc_key": key(), **params}
    last = None
    for i in range(retries):
        r = requests.get(f"{BASE}/{endpoint}", params=p, timeout=90)
        r.raise_for_status()
        d = r.json()
        if d.get("status") == "000":
            return d
        last = d
        if d.get("status") in {"020", "800"}:
            time.sleep(2**i)
            continue
        raise RuntimeError(f"DART API {endpoint}: {d.get('status')} / {d.get('message')}")
    raise RuntimeError(f"DART API 재시도 실패 {endpoint}: {last}")


def get_zip(endpoint: str, params: dict[str, Any]) -> bytes:
    p = {"crtfc_key": key(), **params}
    for i in range(4):
        r = requests.get(f"{BASE}/{endpoint}", params=p, timeout=180)
        r.raise_for_status()
        if r.content[:2] == b"PK":
            return r.content
        txt = r.text
        m = re.search(r"<status>(\d+)</status>.*?<message>(.*?)</message>", txt, re.S)
        status = m.group(1) if m else "unknown"
        msg = BeautifulSoup(m.group(2), "html.parser").get_text(" ", strip=True) if m else txt[:300]
        if status in {"020", "800"}:
            time.sleep(2**i)
            continue
        raise RuntimeError(f"DART binary API {endpoint}: {status} / {msg}")
    raise RuntimeError(f"DART binary API 재시도 실패 {endpoint}")


def num(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).replace(",", "").replace(" ", "").strip()
    if s.lower() in {"", "-", "—", "nan", "none", "n/a"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return None if not m else (-1 if neg else 1) * float(m.group(0))


def clean(s: Any) -> str:
    return re.sub(r"\s+", "", str(s or "")).replace("·", "")


def amount(row: dict[str, Any], flow: bool) -> float | None:
    keys = ("thstrm_add_amount", "thstrm_amount") if flow else ("thstrm_amount", "thstrm_add_amount")
    for k in keys:
        x = num(row.get(k))
        if x is not None:
            return x
    return None


def value(rows: list[dict[str, Any]], field: str, flow: bool) -> float | None:
    aliases = [clean(x) for x in ALIASES.get(field, [field])]
    hits = [r for r in rows if r.get("fs_div") in (None, FS_DIV) and any(clean(r.get("account_nm")) == a or a in clean(r.get("account_nm")) for a in aliases)]
    if not hits:
        return None
    hits.sort(key=lambda r: min(0 if clean(r.get("account_nm")) == a else 1 for a in aliases))
    return amount(hits[0], flow)


def debt(rows: list[dict[str, Any]]) -> float | None:
    exact = {clean(x) for x in ["차입금","이자부차입금","차입금및사채","차입금 및 사채"]}
    for r in rows:
        if r.get("fs_div") in (None, FS_DIV) and clean(r.get("account_nm")) in exact:
            x = amount(r, False)
            if x is not None:
                return x
    parts = {clean(x) for x in ["단기차입금","장기차입금","유동성장기차입금","사채","유동성사채","장기차입금및사채","장기차입금 및 사채"]}
    vals = [amount(r, False) for r in rows if r.get("fs_div") in (None, FS_DIV) and clean(r.get("account_nm")) in parts]
    vals = [x for x in vals if x is not None]
    return float(sum(vals)) if vals else None


def capex(rows: list[dict[str, Any]]) -> float | None:
    labels = {clean(x) for x in ["유형자산의 취득","유형자산 취득","유형자산의 취득으로 인한 현금유출","무형자산의 취득","무형자산 취득"]}
    vals = [abs(amount(r, True)) for r in rows if r.get("fs_div") in (None, FS_DIV) and clean(r.get("account_nm")) in labels and amount(r, True) is not None]
    return float(sum(vals)) if vals else None


def normalize(rows: list[dict[str, Any]], year: int, period: str, code: str, rcept_no: str | None, source: str) -> dict[str, Any]:
    out = {"year":year,"period":period,"reprt_code":code,"rcept_no":rcept_no,"fs_div":FS_DIV,"source":source}
    for f in ALL_FIELDS:
        out[f] = value(rows, f, f in FLOW)
    out["interest_bearing_debt"] = debt(rows)
    out["capex"] = capex(rows)
    oi, da = out.get("operating_income"), out.get("depreciation_amortization")
    out["ebitda"] = oi + abs(da) if oi is not None and da is not None else None
    out["raw_account_count"] = len(rows)
    return out


def filing_code(kind: str) -> str:
    return {"annual":CODES["annual"],"half_year":CODES["half_year"],"quarterly_q1":CODES["quarterly_q1"],"quarterly_q3":CODES["quarterly_q3"]}[kind]


def disclosure_list(year: int) -> list[dict[str, Any]]:
    out=[]; page=1
    while True:
        d=get_json("list.json",{"corp_code":COMP["corp_code"],"bgn_de":f"{year}0101","end_de":f"{year}1231","page_no":page,"page_count":100,"sort":"date","sort_mth":"desc"})
        out += d.get("list",[])
        total=int(d.get("total_page") or 1)
        if page>=total: break
        page += 1
        if page>20: break
    return out


def pick(disclosures: list[dict[str,Any]], kind: str) -> dict[str,Any] | None:
    names={"annual":["사업보고서"],"half_year":["반기보고서"],"quarterly_q1":["분기보고서"],"quarterly_q3":["분기보고서"]}
    xs=[x for x in disclosures if any(k in str(x.get("report_nm","")) for k in names[kind])]
    if kind == "quarterly_q1": xs=[x for x in xs if "1분기" in str(x.get("report_nm",""))]
    if kind == "quarterly_q3": xs=[x for x in xs if "3분기" in str(x.get("report_nm",""))]
    xs=[x for x in xs if "첨부추가" not in str(x.get("report_nm",""))]
    return sorted(xs,key=lambda x:str(x.get("rcept_dt","")),reverse=True)[0] if xs else None


def parse_xbrl(payload: bytes, year: int, period: str, rcept_no: str) -> dict[str, Any] | None:
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        members={n:z.read(n) for n in z.namelist() if not n.endswith("/")}
    contexts={}; facts=[]; unit_ids=set()
    def lname(t): return t.split("}")[-1].split(":")[-1]
    for content in members.values():
        try: root=ET.fromstring(content)
        except ET.ParseError: continue
        for n in root.iter():
            if lname(n.tag)=="context" and n.attrib.get("id"):
                c=n.attrib["id"]; ctx={"instant":None,"start":None,"end":None,"dims":0}
                for q in n.iter():
                    z0=lname(q.tag)
                    if z0=="instant": ctx["instant"]=(q.text or "").strip()
                    elif z0=="startDate": ctx["start"]=(q.text or "").strip()
                    elif z0=="endDate": ctx["end"]=(q.text or "").strip()
                    elif z0=="explicitMember": ctx["dims"] += 1
                contexts[c]=ctx
            if lname(n.tag)=="unit" and n.attrib.get("id"):
                unit_ids.add(n.attrib["id"])
        for n in root.iter():
            if len(n): continue
            c=n.attrib.get("contextRef")
            if c in contexts:
                x=num(n.text)
                if x is not None: facts.append((lname(n.tag),x,contexts[c],n.attrib.get("unitRef")))
    if not facts: return None
    end=f"{year}-12-31"; target=[ctx for ctx in contexts.values() if ctx.get("dims",0)==0 and (ctx.get("instant")==end or (ctx.get("end")==end and ctx.get("start") and str(ctx.get("start")).startswith(f"{year}-01")))]
    if not target: target=list(contexts.values())
    concept={
      "total_assets":["Assets"],"cash":["CashAndCashEquivalents"],"receivables":["TradeAndOtherCurrentReceivables","TradeReceivables"],"inventory":["Inventories"],"current_assets":["CurrentAssets"],"current_liabilities":["CurrentLiabilities"],"payables":["TradeAndOtherCurrentPayables","TradePayables"],"ppe":["PropertyPlantAndEquipment"],"total_liabilities":["Liabilities"],"total_equity":["Equity","EquityAttributableToOwnersOfParent"],"revenue":["Revenue"],"cost_of_sales":["CostOfSales"],"gross_profit":["GrossProfit"],"sga":["SellingGeneralAndAdministrativeExpense"],"operating_income":["OperatingProfitLoss","ProfitLossFromOperatingActivities"],"pretax_income":["ProfitLossBeforeTax"],"net_income":["ProfitLoss"],"controlling_net_income":["ProfitLossAttributableToOwnersOfParent"],"cfo":["CashFlowsFromUsedInOperatingActivities","NetCashFlowsFromUsedInOperatingActivities"],"cfi":["CashFlowsFromUsedInInvestingActivities","NetCashFlowsFromUsedInInvestingActivities"],"cff":["CashFlowsFromUsedInFinancingActivities","NetCashFlowsFromUsedInFinancingActivities"],"interest_expense":["InterestExpense"],"income_tax":["IncomeTaxExpenseBenefit"],"depreciation_amortization":["DepreciationAndAmortisation","DepreciationAndAmortization"],"interest_bearing_debt":["Borrowings","InterestBearingBorrowings"],"capex":["PaymentsToAcquirePropertyPlantAndEquipment","PurchaseOfPropertyPlantAndEquipment","PaymentsToAcquirePropertyPlantEquipment"]}
    out={"year":year,"period":period,"reprt_code":filing_code(period),"rcept_no":rcept_no,"fs_div":FS_DIV,"source":"OpenDART fnlttXbrl/document XBRL"}
    for f in ALL_FIELDS:
        concepts=concept.get(f,[])
        vals=[v for c,v,ctx,u in facts if ctx in target and c in concepts]
        if vals: out[f]=sum(vals) if f=="interest_bearing_debt" else vals[-1]
        else: out[f]=None
    if out.get("capex") is not None: out["capex"]=abs(out["capex"])
    oi,da=out.get("operating_income"),out.get("depreciation_amortization")
    out["ebitda"]=oi+abs(da) if oi is not None and da is not None else None
    out["raw_fact_count"]=len(facts)
    out["xbrl_note"]="Historical XBRL values are retained for audit; verify units against the source filing when comparing with structured API values."
    return out


def historical_html(payload: bytes, year: int, period: str, rcept_no: str, report_nm: str) -> dict[str, Any] | None:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        docs=[]
        for n in z.namelist():
            if n.endswith("/"): continue
            content=z.read(n)
            if b"<table" in content[:500000].lower():
                docs.append(content.decode("utf-8",errors="ignore"))
    if not docs: return None
    out={"year":year,"period":period,"reprt_code":filing_code(period),"rcept_no":rcept_no,"fs_div":FS_DIV,"source":"OpenDART document.xml table fallback","report_nm":report_nm}
    found=0
    for f,als0 in ALIASES.items():
        als=[clean(x) for x in als0]; got=None
        for doc in docs:
            soup=BeautifulSoup(doc,"lxml")
            for tr in soup.find_all("tr"):
                cells=[re.sub(r"\s+"," ",x.get_text(" ",strip=True)) for x in tr.find_all(["th","td"])]
                if not cells or not any(a==clean(cells[0]) or a in clean(cells[0]) for a in als): continue
                xs=[num(x) for x in re.findall(r"[-+]?\(?\d[\d,]*(?:\.\d+)?\)?"," ".join(cells[1:]))]; xs=[x for x in xs if x is not None]
                if xs: got=xs[0]; break
            if got is not None: break
        out[f]=got; found += got is not None
    oi,da=out.get("operating_income"),out.get("depreciation_amortization"); out["ebitda"]=oi+abs(da) if oi is not None and da is not None else None
    return out if found>=5 else None


def historical(year:int, kind:str, disclosures:list[dict[str,Any]]):
    filing=pick(disclosures,kind)
    if not filing: return None,None,None
    r=str(filing["rcept_no"]); nm=str(filing.get("report_nm",""))
    try:
        z=get_zip("fnlttXbrl.xml",{"rcept_no":r}); p=parse_xbrl(z,year,kind,r)
        if p: return p,z,f"xbrl_{r}.zip"
    except Exception as e: print(f"WARN XBRL {year} {kind}: {e}")
    try:
        z=get_zip("document.xml",{"rcept_no":r}); p=historical_html(z,year,kind,r,nm)
        return p,z,f"document_{r}.zip"
    except Exception as e: print(f"WARN document {year} {kind}: {e}")
    return None,None,None


def _json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def save(path:Path,obj:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    payload = _json_ready(obj)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )


def ratios(df:pd.DataFrame)->pd.DataFrame:
    df=df.copy().sort_values(["year","period"])
    for c in ALL_FIELDS+["ebitda"]:
        if c not in df: df[c]=np.nan
    df["fcf"]=df["cfo"]-df["capex"].abs(); df["net_debt"]=df["interest_bearing_debt"]-df["cash"]
    df["gross_margin"]=df["gross_profit"]/df["revenue"]*100; df["operating_margin"]=df["operating_income"]/df["revenue"]*100; df["net_margin"]=df["net_income"]/df["revenue"]*100; df["ebitda_margin"]=df["ebitda"]/df["revenue"]*100
    prev_assets=df["total_assets"].shift(1); prev_eq=df["total_equity"].shift(1); avg_assets=(df["total_assets"]+prev_assets)/2; avg_eq=(df["total_equity"]+prev_eq)/2
    df["roa"]=df["net_income"]/avg_assets*100; df["roe"]=df["net_income"]/avg_eq*100; df["current_ratio"]=df["current_assets"]/df["current_liabilities"]*100; df["quick_ratio"]=(df["current_assets"]-df["inventory"])/df["current_liabilities"]*100
    df["debt_ratio"]=df["total_liabilities"]/df["total_equity"]*100; df["equity_ratio"]=df["total_equity"]/df["total_assets"]*100; df["debt_to_assets"]=df["interest_bearing_debt"]/df["total_assets"]*100
    df["interest_coverage"]=df["operating_income"]/df["interest_expense"]; df["net_debt_to_ebitda"]=df["net_debt"]/df["ebitda"]; tax=(df["income_tax"]/df["pretax_income"]).clip(0,1); nopat=df["operating_income"]*(1-tax); ic=df["interest_bearing_debt"]+df["total_equity"]-df["cash"]; df["roic"]=nopat/((ic+ic.shift(1))/2)*100
    df["dso"]=df["receivables"]/df["revenue"]*365; df["dio"]=df["inventory"]/df["cost_of_sales"]*365; df["dpo"]=df["payables"]/(df["cost_of_sales"]+df["inventory"]-df["inventory"].shift(1))*365; df["ccc"]=df["dso"]+df["dio"]-df["dpo"]; df["asset_turnover"]=df["revenue"]/avg_assets; df["revenue_growth"]=df["revenue"].pct_change()*100; df["cfo_to_net_income"]=df["cfo"]/df["net_income"]
    return df.replace([np.inf,-np.inf],np.nan)


def standalone_quarters(df:pd.DataFrame)->pd.DataFrame:
    out=[]
    for year,g in df.groupby("year"):
        g=g.set_index("period"); q1=g.loc["quarterly_q1"] if "quarterly_q1" in g.index else None; h1=g.loc["half_year"] if "half_year" in g.index else None; q3=g.loc["quarterly_q3"] if "quarterly_q3" in g.index else None; ann=g.loc["annual"] if "annual" in g.index else None
        for label,src,sub in [("Q1",q1,None),("Q2",h1,q1),("Q3",q3,h1),("Q4",ann,q3)]:
            if src is None: continue
            r=src.to_dict(); r["period"]=label; r["report_basis"]="reported" if label=="Q1" else "derived from cumulative DART filing"
            if label!="Q1" and sub is not None:
                for f in FLOW:
                    if pd.notna(src.get(f)) and pd.notna(sub.get(f)): r[f]=src.get(f)-sub.get(f)
            out.append(r)
    return ratios(pd.DataFrame(out)) if out else pd.DataFrame()


def main():
    start=int(COMP["start_year"]); current=date.today().year; raw=ROOT/"data/raw"; proc=ROOT/"data/processed"; raw.mkdir(parents=True,exist_ok=True); proc.mkdir(parents=True,exist_ok=True)
    normalized=[]; registry=[]
    for y in range(max(2015,start),current+1):
        for kind in ["annual","half_year","quarterly_q1","quarterly_q3"]:
            code=filing_code(kind)
            try:
                d=get_json("fnlttSinglAcntAll.json",{"corp_code":COMP["corp_code"],"bsns_year":str(y),"reprt_code":code,"fs_div":FS_DIV}); rows=d.get("list",[])
                if rows:
                    rno=str(rows[0].get("rcept_no") or "") or None; normalized.append(normalize(rows,y,kind,code,rno,"OpenDART fnlttSinglAcntAll")); save(raw/"structured"/str(y)/f"{kind}.json",{"meta":{"year":y,"period":kind,"retrieved_at":pd.Timestamp.utcnow().isoformat()},"list":rows}); registry.append({"year":y,"period":kind,"reprt_code":code,"rcept_no":rno,"viewer_url":f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}"})
            except Exception as e: print(f"WARN {y} {kind}: {e}")
    for y in range(start,min(2015,current+1)):
        try: disclosures=disclosure_list(y); save(raw/"disclosures"/f"{y}.json",disclosures)
        except Exception as e: print(f"WARN disclosure {y}: {e}"); continue
        for kind in ["annual","half_year","quarterly_q1","quarterly_q3"]:
            p,z,name=historical(y,kind,disclosures); filing=pick(disclosures,kind)
            if filing:
                rno=str(filing["rcept_no"]); registry.append({"year":y,"period":kind,"reprt_code":filing_code(kind),"rcept_no":rno,"report_nm":filing.get("report_nm"),"rcept_dt":filing.get("rcept_dt"),"viewer_url":f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}"})
                if z and name:
                    d=raw/"historical"/str(y); d.mkdir(parents=True,exist_ok=True); (d/name).write_bytes(z)
            if p: normalized.append(p); save(raw/"historical"/str(y)/f"{kind}.json",p)
    if not normalized: raise RuntimeError("수집된 재무 데이터가 없습니다.")
    df=pd.DataFrame(normalized)
    for c in ALL_FIELDS:
        if c not in df: df[c]=np.nan
    df=df.sort_values(["year","period"]).drop_duplicates(["year","period"],keep="first"); df=ratios(df)
    q=standalone_quarters(df); dashboard=pd.concat([df[df.period.isin(["annual","half_year"])],q],ignore_index=True,sort=False).sort_values(["year","period"])
    dashboard.to_csv(proc/"samsung_financials.csv",index=False,encoding="utf-8-sig"); save(proc/"samsung_financials.json",dashboard.replace({np.nan:None}).to_dict(orient="records")); save(proc/"metadata.json",{"company":COMP,"updated_at_utc":pd.Timestamp.utcnow().isoformat(),"structured_financial_data_from":2015,"historical_fallback":"2010-2014 disclosure + fnlttXbrl/document original file","rows":len(dashboard)})
    pd.DataFrame(registry).drop_duplicates(subset=["year","period","rcept_no"]).to_csv(proc/"report_registry.csv",index=False,encoding="utf-8-sig")
    site=ROOT/"site/data/processed"; site.mkdir(parents=True,exist_ok=True)
    for f in ["samsung_financials.json","samsung_financials.csv","metadata.json","report_registry.csv"]: (site/f).write_bytes((proc/f).read_bytes())
    print(f"OK dashboard_rows={len(dashboard)} annual={(dashboard.period=='annual').sum()} half={(dashboard.period=='half_year').sum()} quarters={dashboard.period.isin(['Q1','Q2','Q3','Q4']).sum()}")


if __name__=="__main__":
    main()
