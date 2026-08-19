# 텅텅(TangTang) 백엔드 구현 계획 — 정종우 (routing 모듈 단독 담당)

> 작성일: 2026-08-19 (스프린트 Day1, 종료 08.21)
> 담당 범위: F-01 ~ F-06 전체 (`backend/app/modules/routing/*`)
> 근거 문서: `4조_1차MVP_기획명세서2026_08_18.pdf`, `텅텅_백엔드개발핸드오프-2026_08_19생성.pdf`, `CLAUDE.md`

---

## 0. 전제 — 착수 전 반드시 확인

이 항목이 안 풀리면 스코어링/필터링 코드를 짜도 다시 갈아엎게 된다. **최우선.**

- [ ] **Q1. congestion_score 결합 공식** — 지하철 %혼잡도(0~100)와 버스 net_onboard(절대 인원수) 단위가 다름. 정규화 방식(노선 정원 추정치 출처 포함)을 김재우님과 확정
- [ ] **Q2. 분당개선의 baseline** — ODsay 후보 중 최단시간 경로를 기준으로 할지 확정
- [ ] **Q3. 정차순번(stop_sequence) 반영 방식** — 가중치 항목으로 넣을지, 필터 조건(예: ≤3)으로 쓸지 확정
- [ ] **Q4. 좌표 매칭 반경** — ODsay 좌표 ↔ station/bus_stop/rental_dock 매칭 허용 반경(예: 50m) 및 매칭 실패 시 처리 방식 확정
- [ ] ODsay API 키 상태 및 실제 응답 필드(정류장 좌표 포함 여부) 재확인 — 테스트 호출로 직접 검증
- [ ] 김재우님에게 로컬 개발용 샘플 데이터(가중치 테이블 더미) 요청
- [ ] `route_request`/`route_candidate`에 좌표 원본을 기록하는 것이 N-04(개인정보 미수집)와 충돌하는지 여부 — 핸드오프 문서는 "사용자 식별자 없음, 좌표+시각만"이라 문제없다는 전제. 이 해석에 팀 이견 없는지 확인 (CLAUDE.md §4 참고)
- [ ] 프론트(윤상은)와 `/routes/search` 응답 스키마(`segments` 구조 등) 사전 합의

---

## 1. 확정된 기술 스택

| 영역 | 선택 |
|---|---|
| Backend | FastAPI (Python 3.12), Uvicorn |
| DB | PostgreSQL + SQLAlchemy (ORM 사용) |
| 캐시 | Redis — ODsay 응답 캐시, 일일 호출 카운터 |
| 리버스 프록시 | nginx |
| 인증 | 없음 (비회원 MVP) |

환경변수(예정): `DATABASE_URL`, `REDIS_URL`, `ODSAY_API_KEY`, `ODSAY_DAILY_QUOTA`(기본 1000)

---

## 2. 담당 범위 매핑 (F-01 ~ F-06)

| 기능 | 내용 | 비고 |
|---|---|---|
| F-01 | ODsay 멀티모달 경로탐색 연동 (요청당 1회) | 캐시 미스 시에만 호출 |
| F-02 | 역/정류장 가중치 매칭 + 혼잡 스코어링 | Q1, Q3, Q4 확정 필요 |
| F-03 | 분당개선 지표 기반 필터링 | Q2 확정 필요 |
| F-04 | 따릉이 대여소 후보 통합 (dock_hub_distance 매칭) | F-01~03 파이프라인 결과에 병합 |
| F-05 | 대여소 실시간 재고 확인 | API 미확정 — **스텁 처리**(항상 재고 확인 없이 후보만 제시), 후속 검증 항목으로 이월 |
| F-06 | 지도 경로 시각화용 데이터 | 실제 렌더링은 프론트 담당. 백엔드는 응답에 station_id/stop_id/좌표만 정확히 실어주면 끝 — 별도 구현 거의 없음 |

F-07(오프라인 배치)은 김재우님 담당, 이 모듈에서 다루지 않는다 — 결과 테이블만 읽기 전용으로 조회.

---

## 3. 디렉토리/파일 구성 (`backend/app/modules/routing/`)

```
routing/
├── routers/
│   └── routes.py          # POST /routes/search, GET /routes/{request_id}
├── schemas/
│   └── route.py           # 요청/응답 Pydantic 모델 (6절 API 명세 기준)
├── services/
│   ├── odsay_client.py    # ODsay 호출 + Redis 캐시/호출한도 관리 (F-01)
│   ├── matching.py        # 좌표 → station_id/stop_id/dock_id 매칭 (Q4)
│   ├── scoring.py         # 혼잡 스코어링 (F-02, Q1/Q3)
│   ├── filtering.py       # 분당개선 필터링 (F-03, Q2)
│   └── bike.py            # 따릉이 후보 통합 (F-04) + 재고 스텁 (F-05)
└── queries/
    ├── weight_queries.py      # station_weight / bus_weight 조회 (SQLAlchemy)
    ├── location_queries.py    # station / bus_stop / rental_dock / dock_hub_distance 조회
    ├── batch_queries.py       # batch_run 최신 상태 조회 (N-05)
    └── request_log_queries.py # route_request / route_candidate 기록
```

공용 관리자/헬스체크(`/admin/batch/latest`, `/health`)는 routing 모듈 내 별도 라우터로 두거나 팀과 위치 협의.

---

## 4. 데이터 계약 요약

**읽기 전용 (김재우님 배치 결과, INSERT/UPDATE 금지)**
- `station_weight` (station_id, batch_id, time_slot, dow, net_onboard, congestion_pct, stop_sequence)
- `bus_weight` (stop_id, route_id, batch_id, time_slot, dow, net_onboard)
- `dock_hub_distance` (dock_id, hub_type, hub_id, batch_id, distance_m)
- `batch_run` (id, run_month, status, finished_at)
- `station` / `bus_stop` / `rental_dock` (id, name, lat, lng, stop_std_id)

**백엔드 소유 (직접 write)**
- `route_request` (id, origin_lat/lng, dest_lat/lng, requested_at) — 사용자 식별자 없음
- `route_candidate` (id, request_id FK, path_type, total_time_min, congestion_score, minute_improvement_ratio, is_recommended)

---

## 5. API 명세 (확정 — 핸드오프 문서 6절 기준)

Base URL `/api/v1`, 인증 없음, 응답 JSON.

| Method | URL | 설명 |
|---|---|---|
| POST | `/routes/search` | ODsay 1회 호출 + 스코어링 + 분당개선 필터링 |
| GET | `/routes/{request_id}` | 과거 요청 결과 재조회 (ODsay 재호출 없음) |
| GET | `/admin/batch/latest` | 최신 배치 실행 상태 (N-05) |
| GET | `/health` | DB·Redis·최신 배치 상태 헬스체크 |

에러 코드: `400 INVALID_INPUT`, `404 NO_CANDIDATE`, `429 ODSAY_QUOTA_EXCEEDED`(캐시 유사 결과 대체 반환), `502 UPSTREAM_ERROR`

---

## 6. 작업 순서 (날짜보다 의존성 우선 — 혼자 진행이라 병렬화 불가, 순서대로)

### Phase 0 — 블로커 해소 (지금, 최우선)
- [ ] 0절 체크리스트 전부 김재우님과 확정
- [ ] ODsay 테스트 호출로 실제 응답 필드 확인

### Phase 1 — 스캐폴딩
- [ ] FastAPI 프로젝트 골격, `/health` (DB/Redis 연결만 우선 체크)
- [ ] docker-compose: PostgreSQL + Redis + nginx(리버스 프록시)
- [ ] SQLAlchemy 엔진/세션(`core/db.py`) — 로컬용, 김재우님 스키마와 필드명 일치 확인
- [ ] `.env.example`

### Phase 2 — 코어 파이프라인 (F-01)
- [ ] ODsay 클라이언트 (호출 1회 강제, Redis 캐시 키 = origin+destination+time_slot)
- [ ] Redis 일일 호출 카운터 + 429 처리
- [ ] 좌표 매칭(`matching.py`) — Q4 반경 기준 적용

### Phase 3 — 스코어링 (F-02)
- [ ] `weight_queries.py` (station_weight/bus_weight 조회)
- [ ] `scoring.py` — Q1 정규화 공식, Q3 정차순번 반영

### Phase 4 — 필터링 + 엔드포인트 완성 (F-03)
- [ ] `filtering.py` — Q2 baseline 기준 분당개선 계산
- [ ] `POST /routes/search` 통합, 응답 스키마 확정
- [ ] `route_request`/`route_candidate` 로깅

### Phase 5 — 따릉이 통합 (F-04, F-05)
- [ ] `dock_hub_distance` 조회 + 후보 병합
- [ ] 재고 확인 스텁(항상 통과) — F-05 API 확정되면 교체

### Phase 6 — 나머지 엔드포인트 + 마무리
- [ ] `GET /routes/{request_id}` (캐시 재조회)
- [ ] `GET /admin/batch/latest`
- [ ] `/health` 최종화 (배치 최신성 포함)
- [ ] 에러 처리 전체(400/404/429/502)

### Phase 7 — 통합 테스트 · 배포
- [ ] 프론트(윤상은)와 `/routes/search` 연동 테스트
- [ ] 김재우님 인프라 위 배포
- [ ] 데모 시나리오 점검

---

## 7. 리스크 / 열린 이슈

- 혼자 F-01~06 전부 담당 → 남은 기간(08.19 저녁~08.21) 대비 범위가 넓음. Phase 진행하며 F-05/F-06처럼 축소 가능한 항목은 과감히 스텁·최소구현으로 유지
- Q1~Q4 미확정 상태로 시간이 더 지체되면 Phase 2 이후 전부 지연 — 오늘 안에 반드시 확정
- `route_request`/`route_candidate`의 개인정보 원칙 적합성은 핸드오프 문서 기준으로 진행하되, 팀 전체 합의 여부 재확인 권장
