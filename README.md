# 🔗 삼성전자 DART Financial Intelligence Dashboard

[![🔗 대시보드 바로가기](https://img.shields.io/badge/🔗%20대시보드%20바로가기-2563EB?style=for-the-badge&logo=github&logoColor=white)](https://hsc-class02.github.io/sujeong_samsung/)

> OpenDART의 삼성전자 사업보고서·반기보고서·분기보고서를 수집하고, 주요 재무수치와 재무비율을 계산해 GitHub Pages 대시보드로 제공하는 자동화 Agent입니다.

## 무엇을 자동화하나요?

- 대상: 삼성전자 (DART corp_code `00126380`, 종목코드 `005930`)
- 기간: 2010년부터 현재까지
- 보고서: 사업보고서 / 반기보고서 / 1·3분기보고서
- 기준: 연결재무제표(CFS) 우선
- 2015년 이후: OpenDART `fnlttSinglAcntAll` 구조화 재무정보 API
- 2010~2014년: DART 공시검색 → `document.xml` 원문 다운로드 → 재무표 휴리스틱 파싱
- 자동화: 매월 1일(Asia/Seoul 기준) GitHub Actions가 업데이트
- 배포: GitHub Pages

OpenDART는 공시 원문과 주요 재무정보를 API로 제공하며, 정기보고서 재무정보의 사업연도·보고서 코드는 2015년 이후 구조화 데이터에 적용됩니다. citeturn0search12turn2search13

## 대시보드 구성

1. 상단 KPI cards
2. 매출액·영업이익·영업현금흐름 추세 그래프
3. 영업이익률·ROE·ROIC 그래프
4. Annual table
5. Half-year table
6. Quarterly table
7. 국내 peer firms table
8. 데이터 기준 및 해석 주의사항

## 첨부된 재무비율 가이드 반영 항목

### 재무상태표
총자산, 현금및현금성자산, 매출채권, 재고자산, 유형자산, 총부채, 이자부차입금, 자본총계 등

### 손익계산서
매출액, 매출총이익, 판매비와관리비, 영업이익, 세전이익, 당기순이익, 지배주주순이익, EBITDA 등

### 현금흐름
영업활동현금흐름(CFO), 투자활동현금흐름(CFI), 재무활동현금흐름(CFF), CAPEX, FCF, 순차입금

### 주요 비율
매출총이익률, 영업이익률, 순이익률, EBITDA 마진, ROA, ROE, ROIC, 유동비율, 당좌비율, 부채비율, 자기자본비율, 차입금의존도, 이자보상배율, 순차입금/EBITDA, 총자산회전율, DSO, DIO, DPO, CCC, 매출증가율, CFO/순이익

재무비율은 단일 지표보다 성장→마진→현금흐름→차입부담→투자수익률의 연결로 보는 방식으로 설계했습니다. fileciteturn1file0L205-L219

## GitHub Actions 설정

### 1. DART API Key 등록

GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**

- Name: `OPENDART_API_KEY`
- Secret: OpenDART에서 발급받은 40자리 인증키

OpenDART의 API는 `crtfc_key` 인증키가 필수이며, 인증키를 코드에 직접 넣지 않고 GitHub Actions Secret으로 주입합니다. citeturn0search0turn0search4

### 2. GitHub Pages 활성화

Repository → **Settings → Pages → Build and deployment → Source: GitHub Actions**

그 후 **Actions → Deploy dashboard to GitHub Pages → Run workflow**를 한 번 실행합니다.

### 3. 자동 업데이트

`update-data.yml`은 GitHub cron의 UTC 한계를 고려해 28~31일에 실행 후보를 만들고, `Asia/Seoul` 날짜가 1일일 때만 실제 DART 수집을 수행합니다. 수집 결과를 commit하면 `pages.yml`이 다시 실행되어 Pages를 갱신합니다.

### 4. 수동 업데이트

Actions → **Update Samsung financial data → Run workflow**

수동 실행은 날짜와 관계없이 즉시 수행합니다.

## API 코드 입력 안내

코드에 API 키를 직접 입력하지 않습니다.

```text
OPENDART_API_KEY = "여기에 40자리 키를 코드로 작성하지 않음"
```

대신 GitHub Secret에 저장하면 workflow에서 다음과 같이 전달됩니다.

```yaml
env:
  OPENDART_API_KEY: ${{ secrets.OPENDART_API_KEY }}
```

로컬 실행 시에는 환경변수를 사용합니다.

```bash
export OPENDART_API_KEY="발급받은_40자리_키"
python src/dart_agent.py
```

## 국내 Peer Firms

| 기업 | 종목코드 | 비교 맥락 |
|---|---:|---|
| SK하이닉스 | 000660 | 메모리/AI 반도체 |
| 삼성전기 | 009150 | 전자부품/패키지·부품 |
| LG전자 | 066570 | 전자제품/전장·가전 |
| LG이노텍 | 011070 | 전자부품/카메라·기판 |
| DB하이텍 | 000990 | 파운드리 |

이 peer set은 삼성전자의 메모리·전자부품·전자제품·파운드리 연관 사업을 고려한 국내 비교군이며, 특정 기업의 투자 우열을 의미하지 않습니다. 국내 전자/반도체 관련 peer 사례에는 SK하이닉스, 삼성전기, LG전자, LG이노텍 등이 함께 언급됩니다. citeturn3search0turn3search28

## 시장가치 지표

첨부 가이드는 PER, PBR, EV/EBITDA, FCF 수익률도 제시합니다. 이 지표는 주가·시가총액 등 시장데이터가 필요하므로 현재 프로젝트의 **DART-only 수집 모드에서는 별도 컬럼으로 자동 계산하지 않습니다**. 필요하면 KRX 등 별도 시장데이터 source를 추가하는 확장 단계에서 연결할 수 있습니다. fileciteturn1file0L197-L204

## 참고

- OpenDART: https://opendart.fss.or.kr/
- Repository: https://github.com/HSC-Class02/sujeong_samsung
- Dashboard: https://hsc-class02.github.io/sujeong_samsung/
