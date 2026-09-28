# API Setup

## OpenDART

1. OpenDART 회원가입/로그인
2. 오픈API 인증키 발급
3. 40자리 인증키 확인
4. GitHub repo의 `Settings → Secrets and variables → Actions`에서 `OPENDART_API_KEY` 생성
5. 값을 인증키로 입력
6. Actions에서 `Update Samsung financial data`를 수동 실행해 첫 적재를 확인

### 사용 API

- `corpCode.xml`: 기업 고유번호 확인용
- `list.json`: 삼성전자 정기보고서 접수번호 탐색
- `fnlttSinglAcntAll.json`: 2015년 이후 단일회사 전체 재무제표
- `document.xml`: 2010~2014년 역사 데이터의 원문 보조 수집

사업보고서/반기보고서/분기보고서 코드는 각각 `11011/11012/11013/11014`입니다. OpenDART 공식 문서의 보고서 코드와 재무정보 제공 범위를 기준으로 구현했습니다.
