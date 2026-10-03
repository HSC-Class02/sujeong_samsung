# 🔗 삼성전자 DART Financial Intelligence Dashboard

[![🔗 대시보드 바로가기](https://img.shields.io/badge/🔗%20대시보드%20바로가기-2563EB?style=for-the-badge&logo=github&logoColor=white)](https://hsc-class02.github.io/sujeong_samsung/)

> OpenDART의 삼성전자 정기보고서를 수집하고 주요 재무수치와 재무비율을 계산해 GitHub Pages Dashboard로 제공하는 자동화 Agent입니다.

## 기본 설정

| 항목 | 설정 |
|---|---|
| 회사 | 삼성전자 |
| DART 고유번호 | `00126380` |
| 종목코드 | `005930` |
| 시작연도 | 2010 |
| 재무기준 | 연결(CFS) 우선 |
| 보고서 | 사업보고서 / 반기보고서 / 1·3분기보고서 |
| 자동 업데이트 | 매월 1일 00:10 KST |
| Dashboard | https://hsc-class02.github.io/sujeong_samsung/ |

## Dashboard

상단에는 KPI와 4개의 시각화 figures를 배치하고, 하단에는 요청하신 3개 category를 각각 별도 table로 제공합니다.

- **Annual**: 연간 사업보고서 기준
- **Half-year**: 반기보고서 기준 누적 실적
- **Quarterly**: Q1은 보고값, Q2/Q3/Q4는 누적 DART 공시를 차감한 standalone quarter

모든 표는 가로 스크롤이 가능하며, 핵심 수치와 주요 비율을 함께 표시합니다.

## 첨부 재무분석 가이드 반영

**재무상태표:** 총자산, 현금및현금성자산, 매출채권, 재고자산, 유동자산, 유동부채, 매입채무, 유형자산, 총부채, 이자부차입금, 자본총계

**손익계산서:** 매출액, 매출원가, 매출총이익, 판매비와관리비, 영업이익, 세전이익, 당기순이익, 지배주주순이익, EBITDA

**현금흐름:** CFO, CFI, CFF, CAPEX, FCF, 순차입금

**수익성:** 매출총이익률, 영업이익률, 순이익률, EBITDA 마진, ROA, ROE, ROIC

**유동성/재무안정성:** 유동비율, 당좌비율, 부채비율, 자기자본비율, 차입금의존도, 이자보상배율, 순차입금/EBITDA

**활동성/성장성:** 총자산회전율, DSO, DIO, DPO, CCC, 매출증가율, CFO/순이익

> 재무비율은 단일 숫자보다 성장 → 마진 → 현금흐름 → 차입부담 → 자본효율을 연결해서 보는 방식으로 구성했습니다.

## 2010년부터 데이터 처리

OpenDART의 단일회사 전체 재무제표 API는 2015년 이후 구조화 재무정보에 사용합니다. 2010~2014년은 정기보고서 접수번호를 찾은 뒤 `fnlttXbrl.xml`을 우선 시도하고, 실패할 경우 `document.xml` 원문을 보조 파싱합니다.

원본 API 응답과 역사 데이터는 `data/raw/`에 보관하고, Dashboard가 읽을 데이터는 `data/processed/`와 `site/data/processed/`에 생성합니다.

## API Key 설정

GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**

- **Name:** `OPENDART_API_KEY`
- **Value:** OpenDART에서 발급받은 40자리 인증키

API Key는 코드나 README에 직접 입력하지 않습니다.

### Local 실행

macOS/Linux:

```bash
export OPENDART_API_KEY="발급받은_40자리_키"
pip install -r requirements.txt
python src/dart_agent.py
```

Windows PowerShell:

```powershell
$env:OPENDART_API_KEY="발급받은_40자리_키"
pip install -r requirements.txt
python src/dart_agent.py
```

## GitHub Actions

실제 workflow는 다음 위치에 있습니다.

- `.github/workflows/update-data.yml`
- `.github/workflows/pages.yml`

**Update Samsung financial data** workflow는 매월 1일 00:10 KST에 DART 데이터를 수집하고 분석합니다. `workflow_dispatch`도 지원하므로 수동 실행도 가능합니다.

**Deploy dashboard to GitHub Pages** workflow는 `site/`를 GitHub Pages로 배포합니다. Agent가 `site/data/processed/`까지 생성하므로 Dashboard와 분석 데이터가 함께 배포됩니다.

## 국내 Peer Firms

| 기업 | 종목코드 | 주요 비교 맥락 |
|---|---:|---|
| SK하이닉스 | 000660 | 메모리·AI 반도체 |
| 삼성전기 | 009150 | MLCC·카메라모듈·반도체 패키지 |
| LG전자 | 066570 | 가전·전장·전자제품 |
| LG이노텍 | 011070 | 카메라모듈·기판·전장부품 |
| LG디스플레이 | 034220 | 디스플레이 패널 |
| DB하이텍 | 000990 | 파운드리 |

Peer set은 삼성전자의 사업 중첩을 설명하기 위한 국내 비교군이며, 기업 간 투자 우열이나 순위를 의미하지 않습니다.

## 시장가치 지표

첨부 가이드의 PER, PBR, EV/EBITDA, FCF 수익률은 주가·시가총액 등 별도 시장데이터가 필요합니다. 현재 프로젝트는 **DART-only**로 설계하여 해당 시장배수는 자동 계산하지 않고, 재무제표 기반 지표에 집중합니다.

## GitHub Repository About 링크

Repository 페이지 오른쪽 **About → Website**에 다음 주소를 입력하면 Dashboard 바로가기 링크가 표시됩니다.

https://hsc-class02.github.io/sujeong_samsung/

Repository metadata의 Website 값은 현재 연결된 GitHub 도구에서 직접 변경할 수 없어 이 항목만 1회 수동 설정이 필요합니다.

## 주요 참고

- OpenDART: https://opendart.fss.or.kr/
- Repository: https://github.com/HSC-Class02/sujeong_samsung
- Dashboard: https://hsc-class02.github.io/sujeong_samsung/
