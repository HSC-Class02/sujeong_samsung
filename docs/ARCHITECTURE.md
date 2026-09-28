# Architecture

```text
OpenDART
   │
   ├─ list.json ───────────────┐
   ├─ fnlttSinglAcntAll.json ──┼─> src/dart_agent.py ─> data/processed/*.json
   └─ document.xml (2010-14) ──┘                              │
                                                              ▼
                                                        site/index.html
                                                              │
                                                              ▼
                                                        GitHub Pages
```

`update-data.yml`는 매월 1일 서울 날짜를 확인한 뒤 수집·계산·commit을 수행하고, `pages.yml`이 변경된 데이터를 Pages로 배포합니다.
