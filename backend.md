# 텅텅(TangTang) 백엔드 통합 계획서

> 작성: 정종우(A) · 2026-08-19 · 김창영(B)의 `backend_split_for_A.md`(2026-08-19) + 백엔드 핸드오프 문서 + 팀 대화 내용을 하나로 통합한 최종본.
> 이 문서가 backend 관련 최신 소스오브트루스다. 이전 개별 문서(핸드오프, `backend_split_for_A.md`)와 내용이 다르면 **이 문서를 따른다.**
> 마감: **2026-08-20(목)** (원래 08.21에서 하루 앞당겨짐)

---

## 1. 서비스 목적 (모든 결정의 기준)

지하철·버스 앱이 보여주는 혼잡도는 "하차 전" 상태다. 텅텅은 대량 하차 직후의 실제 재차인원을 계산해서,
**조금 돌아가더라도 실제로 덜 혼잡하고 쾌적한 지점·시간에 타도록 추천**하는 서비스다.
백엔드의 모든 스코어링·필터링 로직은 이 목적 — "목적지까지 편하게 가는 것" — 에 맞춰 설계한다.
단순히 최단시간 경로만 보여주는 게 아니라, **"조금 느려도 덜 붐빈다"는 가치를 사용자가 체감하게 만드는 것**이 핵심이다.

---

## 2. 확정 기술 스택

| 영역 | 결정 | 비고 |
|---|---|---|
| Backend | FastAPI (Python 3.12), Uvicorn | |
| DB | **PostgreSQL** | 확정 |
| DB 접근 | **ORM 사용 안 함** — `psycopg`(v3) + 원시 SQL + 파라미터 바인딩 | 같은 날 한때 SQLAlchemy ORM으로 갔다가 최종적으로 원시 SQL로 재확정됨. PG 전용 문법(`JSONB`/`ARRAY`/`RETURNING`)도 가급적 피하고 표준 SQL로 작성(과거 MySQL 8 공통지침으로 되돌아갈 가능성 대비) |
| 캐시 | Redis | ODsay 응답 캐시, 일일 호출 카운터 |
| 리버스 프록시 | nginx | FastAPI 앞단 |
| 인증 | 없음 | 1차 MVP 비회원 서비스 |
| Frontend | React + Vite (윤상은 담당, 백엔드 범위 아님) | |

CLAUDE.md §2/§8/§13에 동일하게 반영됨.

---

## 3. 담당 범위 (A=정종우, B=김창영)

~~게시판 CRUD, 도보/자전거 폴리라인은 이번 스프린트 범위에서 완전히 제외한다.~~ → **일부 번복
(2026-08-19 저녁)**: 게시판 CRUD는 다시 포함하기로 결정함(§11). 도보 폴리라인도 Tmap API 키
발급 진행 중이라 포함될 예정. 자전거(따릉이) 경로 폴리라인만 여전히 범위 밖 — 따릉이는 대여소
조회(§6)만 제공하고 출발~도착 사이 자전거 경로선은 그리지 않음.
**쿠폰(Redis 선착순)은 조건부 유지** — B가 통합(8/20 12시) 끝나고 시간 남으면 진행, 아니면 드롭 (`routers/coupon.py`, `POST /coupons/claim`, B 담당 파일이라 A 작업엔 영향 없음).

남기는 범위(A 기준): **경로 검색 + 스코어링 + 비교(최단시간 vs 추천)**. 여기에 B가 따릉이 대여소 조회를 더한다.

| | **A (정종우)** | **B (김창영)** |
|---|---|---|
| 메인 | `POST /api/v1/routes/search` | 조회·보조 API 전체 |
| 세부 | ODsay 연동 → 좌표 매칭 → 스코어링 → 분당개선 필터 → 비교 응답(최단시간 vs 추천) | `GET /routes/{request_id}`<br>`GET /api/v1/bike/docks` (F-04)<br>`GET /api/v1/system/meta`<br>`GET /health`<br>`GET /admin/batch/latest` |
| 파일 | `routers/search.py`<br>`services/odsay.py`<br>`services/scoring.py` | `routers/result.py`<br>`routers/bike.py`<br>`routers/system.py`<br>`sql/*`<br>`core/*` |

**비교 기능(최단시간 vs 혼잡회피 추천)은 A의 `/search` 응답 안에 포함한다.** ODsay가 한 번에 주는 후보 풀에서
최속 후보와 추천 후보를 골라 응답 형태만 바꾸는 것이라 별도 API로 안 나눈다. 이게 이 서비스의 핵심 가치를
가장 직접적으로 보여주는 응답이라 데모에서도 중요하다 (§9 참고).

### B가 오늘 밤 push하는 공용 파일 (A는 이걸 기다리지 않고 하드코딩으로 먼저 진행)

```
backend/app/main.py          FastAPI 앱 + 라우터 등록 (A 먼저, B 나중 순서로 include_router)
backend/app/core/db.py       psycopg 커넥션 풀
backend/app/core/redis.py    Redis 클라이언트
backend/.env.example         환경변수 키 정의
backend/sql/01_schema.sql    명세서 §8 ERD 기준 — ⚠️ 로컬 개발 전용 임시 스키마. 김재우님의 실제 배치 스키마와
                              필드명이 다르면 나중에 그쪽 기준으로 교체 (김재우님과 별도 확인 필요)
backend/sql/02_seed.sql      개발용 더미 데이터 (강남·신도림·성수·신답 등 실존역 5~6개 + 시간대별 가중치)
docker-compose.yml           PostgreSQL + Redis
```

`main.py`, `core/*`는 이후 A/B 모두 건드리지 않는다.

### 접점 함수 (A ↔ B)

```python
# backend/app/services/candidate_log.py  (B 작성)
def save_candidates(request_id: int, candidates: list[dict]) -> None
```

A는 `/search` 마지막 줄에서 이 함수를 한 번 호출하면 끝. `candidates` 각 항목 필수 키:
`path_type`, `total_time_min`, `congestion_score`, `minute_improvement_ratio`, `is_recommended`.
`route_request` INSERT와 `request_id` 반환도 B가 처리.

---

## 4. 데이터 계약

**읽기 전용 (김재우님 배치 결과)**
- `station_weight`(station_id, batch_id, time_slot, dow, net_onboard, congestion_pct, stop_sequence)
- `bus_weight`(stop_id, route_id, batch_id, time_slot, dow, net_onboard) — ⚠️ **`stop_sequence` 컬럼이 없음, 아래 §7.3 참고**
- `dock_hub_distance`(dock_id, hub_type, hub_id, batch_id, distance_m)
- `batch_run`(id, run_month, status, finished_at)
- `station` / `bus_stop`(`stop_std_id` UNIQUE) / `rental_dock`

**백엔드 소유 (B가 write)**
- `route_request`(id, origin_lat/lng, dest_lat/lng, requested_at) — 사용자 식별자 없음
- `route_candidate`(id, request_id FK, path_type, total_time_min, congestion_score, minute_improvement_ratio, is_recommended)

---

## 5. API 명세

Base URL `/api/v1`, 인증 없음, 응답 JSON.

| Method | URL | 담당 | 설명 |
|---|---|---|---|
| POST | `/routes/search` | A | ODsay 1회 호출 + 스코어링 + 분당개선 필터링 + 비교 응답 |
| GET | `/routes/{request_id}` | B | 과거 요청 결과 재조회 (ODsay 재호출 없음) |
| GET | `/bike/docks` | B | `hub_type`/`hub_id`/`max_distance` 기준 근처 따릉이 대여소 조회 (F-04) |
| GET | `/system/meta` | B | Front/Server version, 서버 IP, 서버명 등 (§8 참고 — 필드 수 확인 필요) |
| GET | `/health` | B | DB·Redis·최신 배치 상태 |
| GET | `/admin/batch/latest` | B | 최신 배치 실행 상태 (N-05) |

에러 코드: `400 INVALID_INPUT`, `404 NO_CANDIDATE`, `429 ODSAY_QUOTA_EXCEEDED`(캐시 유사 결과 대체 반환), `502 UPSTREAM_ERROR`
(FastAPI `HTTPException`으로 던지므로 실제 응답 바디는 `{"detail": {"code": "NO_CANDIDATE"}}`처럼 `detail`에
한 번 감싸져 있음 — `docs/api-contracts/routing.md`엔 이 wrapping이 아직 안 적혀 있어서 프론트 확인 필요)

### 5.1 `/routes/search` 실제 응답 형태 (2026-08-19 기준, 코드로 확정됨 — §6.2도 참고)

윤상은님 `docs/api-contracts/routing.md`가 "미확정"으로 표시해둔 것들이 이제 전부 코드로 확정됨:
최상위 키는 `routes`가 아니라 **`candidates`**, 각 candidate엔 **`id`**(0부터 시작하는 순번, React key로
바로 써도 됨)와 **`is_fastest`**(최단시간 후보인지 — `is_recommended`와 별도 필드)가 추가됨.

```json
{
  "request_id": 10234,
  "is_same": false,
  "candidates": [
    {
      "id": 0,
      "path_type": "subway+bus",
      "total_time_min": 74,
      "congestion_score": 0.32,
      "minute_improvement_ratio": 5.1,
      "is_recommended": true,
      "is_fastest": false,
      "segments": [
        { "mode": "walk", "duration_min": 4, "distance_m": 292,
          "start": {"lat": 37.5012, "lng": 127.0396}, "end": {"lat": 37.5006, "lng": 127.0364},
          "station_id": null, "stop_id": null, "stop_std_id": null, "route_id": null,
          "matched": false, "polyline": null },
        { "mode": "subway", "duration_min": 28, "distance_m": 10800,
          "start": {"lat": 37.5006, "lng": 127.0364}, "end": {"lat": 37.4842, "lng": 126.9297},
          "station_id": 1021, "stop_id": null, "stop_std_id": null, "route_id": "2",
          "matched": true,
          "polyline": [ {"lat": 37.5006, "lng": 127.0364}, {"lat": 37.4998, "lng": 127.0301}, "... (실제 선로를 따라가는 점 수십~백여 개)" ] }
      ]
    }
  ]
}
```

`path_type`은 "recommended"/"fastest" 같은 분류값이 아니라 **교통수단 조합 문자열**이다
(`"subway"` / `"bus"` / `"subway+bus"`). 추천·최단 구분은 `is_recommended`/`is_fastest` 두 불리언으로 본다.
따릉이(`bike`)는 segment의 mode로 절대 안 온다 — 완전히 별도인 `GET /bike/docks`(B 담당)를 호출해야 함.

---

## 6. 따릉이(F-04/F-05) 처리 방식

경로 후보 자체를 자전거로 재생성하지 않는다(ODsay 호출이 늘어나 N-03 위반). 대신 **경로 후보의 지하철역·
버스정류장 근처 대여소를 참고 정보로 별도 API에서 내려주는 방식**으로 간다.

```
GET /api/v1/bike/docks?hub_type=station&hub_id=1021&max_distance=500
→ dock_hub_distance 조회 → 가까운 대여소 목록 반환
```

`/routes/search` 응답에 이미 `station_id`/`stop_id`가 들어가므로 A쪽 추가 작업은 없다. 실시간 재고(F-05)는
API 미확정이라 응답에 `stock: null`로 두고 스텁 처리한다.

### 6.1 지도 위 지하철 노선 시각화 — 실제 선로 곡선 데이터 (2026-08-19 추가)

프론트에서 "노선도에 경로 그리기"를 요청했을 때, 개략도(45도 직선으로 재배치한 그 노란/파란 지하철 안내도
스타일)를 프로그래밍으로 다루는 건 검토해본 결과 이번 스프린트 안에 불가능하다고 판단했다 — 후보로 찾아본
정부 공식 노선도는 PDF/JPG뿐이라 조작 불가능하고, 오픈소스 SVG는 역별 id가 없고(하나로 뭉쳐진 도형) 수인분당선
·우이신설선·서해선 등 최근 노선이 빠져 있어 그대로 못 씀.

**대신 실제 지리 좌표 기반 지도(카카오맵) 위에 진짜 선로 곡선을 그리는 방식으로 간다** — 이건 `frontend-plan.md`
§5에 원래 계획된 방식(좌표 이어서 Polyline)의 업그레이드일 뿐, 새로운 화면 구조가 아니다.

`API 응답 값/서울 지하철 노선 형상(OpenStreetMap).geojson`에 실제 선로 곡선 데이터를 받아 정리해뒀다.

- 출처: OpenStreetMap (Overpass API), 2026-08-19 수집. **라이선스 ODbL — 화면 어딘가에 "© OpenStreetMap
  contributors" 출처 표시 필요.**
- 수도권 25개 노선(1~9호선, 신분당·수인분당·경의중앙·경춘·서해·공항철도·GTX-A·각종 경전철 등), 1324개
  구간(segment), 0.58MB
- 구조: GeoJSON `FeatureCollection`, 각 Feature는 `LineString` 하나(노선 전체가 아니라 그 노선의 짧은
  구간 하나). `properties.line_ref`(예: `"2"`, `"신분당"`, `"GTX-A"` — ODsay `lane[].subwayCode`/segment의
  `route_id`와 매칭되는 값), `properties.line_name`, `properties.colour`(실제 노선 색 hex)
- ⚠️ GeoJSON 좌표 순서는 `[lng, lat]`(경도, 위도) — 우리 서비스의 `{lat, lng}` 순서와 반대라 주의
  (이 원본 GeoJSON을 프론트가 직접 쓸 일은 없음 — 아래 6.2 참고. 백엔드 내부에서만 이 순서 조심하면 됨)

### 6.2 `/routes/search` 응답에 노선 곡선 포함 완료 — 프론트는 이것만 쓰면 됨 (2026-08-19)

**"프론트는 윤상은님 전담" 결정에 따라, 구간 자르기는 전부 백엔드에서 처리해서 내려준다.** 원본 GeoJSON이나
좌표 계산(점-선 투영)을 프론트가 알거나 다룰 필요가 전혀 없다.

`/routes/search` 응답의 지하철(`mode: "subway"`) segment마다 **`polyline` 필드**가 추가됐다(§5.1 예시 참고):

- 값이 있으면(`[{lat, lng}, {lat, lng}, ...]`, 보통 수십~수백 개) → 이 점들을 순서대로 이어서 그리면 그게
  시작역~끝역 사이의 **실제 선로 곡선**이다. 카카오맵 Polyline에 좌표 배열 그대로 넣으면 됨.
  좌표 순서는 우리 서비스 컨벤션 그대로 `{lat, lng}` — GeoJSON의 `[lng, lat]` 순서 걱정 안 해도 됨.
- 값이 `null`이면 → 매칭 실패(해당 구간이 OSM 데이터에서 300m 이내로 못 찾아짐) 또는 버스/도보 구간.
  이때는 기존 방식대로 `start`/`end`를 직선(Polyline 두 점)으로 이으면 됨 — 원래 계획하신 방식과 동일.
- 버스(`mode: "bus"`)도 2026-08-19부터 지원 — 지하철과 데이터 확보 방식이 다르다(정적 파일이 아니라
  실시간 Overpass 조회 + 캐싱). §6.3 참고. 매칭 실패 시 `null`로 떨어지는 폴백 조건은 지하철과 동일.

구현: `backend/app/services/line_geometry.py` — 궁금하면 참고, 몰라도 사용에는 문제없음.

**어디에 더 기록해두면 좋을지**: 이 내용은 `docs/api-contracts/routing.md`(윤상은님 소유, 프론트-백엔드
계약 문서)에도 그대로 옮겨두는 게 맞다고 판단함 — 그 문서가 "미확정"이라고 표시해둔 항목들(§5.1에서 언급한
`routes`→`candidates`, `path_type` 의미, `id` 필드 등)의 실제 답이 다 여기 있어서, 그쪽에도 반영돼야 프론트
작업하실 때 참고하기 편할 것 같음. 다만 그 문서는 윤상은님 브랜치(`feature/routing/mvp-ui-scaffold`)에만
있어서 A/B가 직접 수정하지 않고 이 내용을 전달하는 방식으로 진행.

### 6.3 버스 노선 곡선 — 실시간 Overpass 조회 + 프로세스 캐싱 (2026-08-19 추가)

지하철과 동일하게 "노선 전체를 미리 받아 정적 파일로" 방식을 버스에도 쓰려고 했으나, 실제로 수도권 버스
노선 수를 세어보니(2026-08-19, Overpass count 조회로 실측) 지하철과 비교가 안 될 정도로 커서 방식을
바꿨다. "완벽한 시스템 구현"이 목표라 데모 좌표에만 맞춘 하드코딩이 아니라, 실제 API로 전체 커버리지를
가져가는 방향으로 확정.

**실측 비교 (동일한 수도권 bbox 기준)**

| | 지하철(정적 파일로 이미 보유) | 버스(전체) |
|---|---|---|
| relation(노선) 수 | 181 | 1,588 (8.8배) |
| way(구간) 수 | 1,694 | 26,673 (15.7배) |
| node(좌표점) 수 | 19,747 | 162,676 (8.2배) |
| 전체 fetch 소요시간 | 6.6초(geometry 포함) | count만도 4초 — geometry까지 받으면 훨씬 오래 걸리고 무료
공유 Overpass 서버에 부담을 주는 요청임 |

전체를 미리 받는 방식은 기각했다 — 시간/용량보다 더 큰 문제는, 지하철처럼 노선번호(1~9)로 바로 매칭이
안 돼서(ODsay `busNo` ↔ OSM `ref` 매핑이 노선마다 다 검증된 게 아님) **매 사용자 요청마다 1,588개 노선
전체를 좌표로 스캔하는 fallback을 타게 될 위험**이 있었다는 것 — 이건 한 번의 데이터 준비 비용이 아니라
매 요청마다 반복되는 실행시간(latency) 문제였다.

**대신 선택한 방식 — 노선별 on-demand 조회 + 캐싱** (`line_geometry.get_bus_curve`)

- 세그먼트에 실제로 등장한 버스 노선번호(ODsay `lane.busNo` — OSM `ref`와 동일한 값임을 504번 버스로
  실측 확인함)만, 그 노선이 처음 등장했을 때 딱 한 번 Overpass에 물어본다
  (`relation["route"="bus"]["ref"="{ref}"]` + 지하철 수집 때와 동일한 수도권 bbox로 스코프 한정).
- 결과(성공/실패 모두)는 FastAPI **프로세스 메모리**에 캐싱 — 같은 노선 재요청 시 네트워크 호출 없음.
  **DB에는 저장하지 않는다**(route_request/route_candidate와 무관, §10 무상태 원칙 유지). 다만 인스턴스
  재시작이나 다중 인스턴스 환경에서는 캐시가 공유되지 않는다는 한계가 있음 — core/redis.py(B) 통합 후
  Redis로 교체 예정(코드에 TODO 남겨둠).
- 실패(타임아웃/네트워크 오류/노선 없음)해도 예외를 던지지 않고 `polyline: null`로 떨어진다 — 프론트는
  기존과 동일하게 직선으로 이으면 됨.
- 지하철과 마찬가지로 OSM 데이터라 **동일한 ODbL 출처 표시가 버스에도 적용됨**(§6.1 참고 — 화면에
  "© OpenStreetMap contributors" 한 줄이면 지하철·버스 둘 다 커버됨, 별도 표시 불필요).

**⚠️ 인프라 확인 필요(김재우님)**: AWS 배포 시 API 서버(private 서브넷)가 Overpass(`overpass-api.de`,
443 포트)로 나가는 아웃바운드 경로가 필요하다 — ODsay 호출과 같은 NAT Gateway 경로를 타지만, 보안그룹/
NACL을 도메인 단위로 좁게 잡을 계획이면 Overpass도 명시적으로 추가해야 한다. 인바운드 규칙은 영향 없음
(전부 서버→외부 방향 호출이라 인바운드를 열 필요가 없음).

**⚠️ 알아두어야 할 리스크(실제로 겪음)**: 2026-08-19 저녁, 코드 작성 후 라이브로 재확인하려는 과정에서
`overpass-api.de`와 미러 서버(`overpass.kumi.systems`) 양쪽 모두 TCP 연결 자체가 타임아웃되는 걸
발견했다 — 같은 시점에 ODsay·GitHub 등 다른 API는 정상 연결됐고, 같은 날 낮에는 Overpass도 정상
응답했었다(6.6초 fetch 성공). 원인은 미확정(개발 샌드박스의 아웃바운드 제한 / Overpass 임시 장애 /
대량 조회 이후 fair-use 제한 등 가능성이 다 열려있음) — 실제 배포 환경에서 재확인이 필요하다. 이 경험은
`polyline: null` 폴백이 이론상 안전장치가 아니라 실제로 자주 탈 수 있는 경로라는 뜻이라, 프론트에서도
이 필드가 자주 null일 수 있다는 전제로 구현해야 한다.

---

## 7. 핵심 로직 — Q1~Q4 확정 값 + 확인 필요 사항

시간이 없어 아래 값으로 **일단 진행**한다. 상수는 전부 코드 상단에 분리해서 나중에 바꾸기 쉽게 만든다.
**정규화 방향은 "0에 가까울수록 쾌적"으로 통일** — 이게 어긋나면 추천이 정확히 거꾸로 나온다.

### 7.1 확정 값

| | 값 |
|---|---|
| Q1 점수 통합 | 지하철 `min(congestion_pct/150, 1.0)`, 버스 `min(net_onboard/50, 1.0)`<br>경로 점수 = 구간 소요시간 가중평균 |
| Q2 baseline | ODsay 후보 중 `total_time_min` 최솟값 |
| Q4 매칭 반경 | 지하철 100m, 버스 50m. 실패 시 `matched: false` + 중립값 0.5 |

### 7.2 Q3 — 정차순번 반영: 완만한 감산으로 최종 확정 (A 단독 결정)

`scoring.py`는 A 전담 파일이라 B 확인 없이 A가 결정하기로 함(2026-08-19). 원안(B): `stop_sequence ≤ 3`이면
점수 × 0.7, 아니면 그대로(계단식 컷오프) — 아래 방식으로 대체한다.

계단식보다 **거리에 비례해 완만하게 줄어드는 감산**이 더 현실적이다. 정차순번 3에서 4로 넘어가는 순간
보너스가 뚝 끊기는 것보다, 출고역(정차순번 0, "계단 내려오면 바로 있는 빈 열차"에 해당하는 기준점)에서
멀어질수록 보너스가 서서히 사라지는 게 실제 혼잡 누적 양상에 가깝다.

```
discount_factor = 1 - max(0, (K - stop_sequence) / K) * MAX_BONUS
# K = 8, MAX_BONUS = 0.3 (기본값, 튜닝 가능한 상수)
# stop_sequence = 0  → factor = 0.7  (가장 큰 보너스)
# stop_sequence = 4  → factor = 0.85
# stop_sequence ≥ 8  → factor = 1.0  (보너스 없음, 원래 congestion_score 그대로)

congestion_score *= discount_factor
```

계단식(K=3에서 뚝 끊김) 대비 완만한 램프(K=8까지 서서히 줄어듦)라 "정차순번 3 vs 4"처럼 경계값 근처에서
추천이 뒤집히는 부자연스러움이 줄어든다. K/MAX_BONUS 값 자체는 근거 데이터가 없는 추정치라 임의 상수인 건
B안과 동일 — 다만 계단식보다 함수 형태 자체가 더 낫다는 제안.

**데이터 확인 결과 (2026-08-19, `API 응답 값/` 폴더 검토):**
- **버스**: 국토교통부 재차인원/혼잡도 API 응답(`1_재차인원.txt`, `2_혼잡도.txt`)에 노선별로 `sttn_seq`(정차순번)와
  `cgst`(혼잡도) / `avg_scdtm_nope`(재차인원성 값)가 **이미 함께 들어있음.** 즉 버스는 정차순번별 혼잡도 실측
  관계를 원천 데이터에서 뽑아낼 수 있다 — 위 임의 상수 대신 실제 곡선을 쓸 수 있음. 다만 이 계산은 배치
  파이프라인(김재우) 영역이라, 시간 되면 `bus_weight`에 반영 요청.
- **지하철**: `서울교통공사_지하철혼잡도정보_20260630.xlsx`는 역/호선/상하구분/30분 시간대별 %혼잡도만 있고
  **정차순번 컬럼 자체가 없음.** 정차순번은 별도로 열차운행시각표에서 계산해야 해서(명세서 4절 방식), 지하철은
  "정차순번별 혼잡도 실측 곡선"이 원천 데이터에 바로 없다 — 위 감산 공식(추정 상수) 방식이 현재로선 유일한 방법.
- **⚠️ 김재우님 확인 필요**: `bus_weight` 테이블에 `stop_sequence` 컬럼이 현재 계약(§4)에 없음. 원천 데이터가
  이미 `sttn_seq`를 주므로 컬럼 추가가 어렵지 않을 것 — 시간 되면 추가 요청. **추가로 `서울시 노선 정류장마스터
  정보.csv`(노선_ID, 정류장_ID, 링크_구간거리, 정류장_순서)에 노선+정류장 조합별 순번이 이미 있는 걸 확인함
  (§7.3 참고)** — `sttn_seq`(국토교통부)와 교차검증하거나 이 마스터 파일을 그대로 써도 됨.

### 7.3 Q4 관련 추가 발견 — 버스는 반경 매칭 대신 ID 직접 매칭 가능 (확인 완료)

`odsay_result.json` 실제 응답의 버스 구간(`trafficType:2`)엔 `localStationID` 필드가 있고 값 형태가
`"118000004"` 식이다. **`서울시 노선 정류장마스터 정보.csv`의 `정류장_ID` 컬럼과 직접 대조해 완전히 일치함을
확인했다** (예: ODsay `localStationID: "118000004"` ↔ CSV `정류장_ID: "118000004"`, 같은 정류장). 즉 버스는
**50m 반경 매칭 없이 `bus_stop.stop_std_id = localStationID`로 정확히 조인 가능** — 반경 매칭보다 오매칭
위험이 없다. `matching.py`에는 버스는 ID 직접 매칭을, 지하철은 기존대로 좌표 반경 매칭(ODsay `stationID`가
자체 내부 ID라 이 방식이 안 통함)을 구현한다.

**보너스**: 이 마스터 CSV에 `정류장_순서` 컬럼이 노선_ID+정류장_ID 조합별로 이미 있어서, 버스 쪽 정차순번은
국토교통부 API와 별개로 이 파일에서도 뽑아낼 수 있음 (§7.2 참고, 김재우님 배치 작업 참고용).

---

## 8. 개인정보 처리 — `route_request` 확정안

CLAUDE.md §13(구현 보류) vs 핸드오프 §3(담당 업무)이 충돌하던 부분. **팀 합의 완료(2026-08-19), 아래대로
구현 확정**: 좌표를 소수점 3자리로 절삭 저장(약 100m 격자)하고, N-04 문구를 "요청 좌표는 일반화하여 저장하며
사용자 식별자와 결합하지 않는다"로 수정. CLAUDE.md §4/§9/§13에 반영 완료.

`/system/meta` 필수 표시 항목은 **6개로 확정**: Front version, Server version, 서버명, 서버 IP, 클라이언트 IP,
X-Forwarded-For(B 담당, nginx가 넘겨주는 헤더 사용). CLAUDE.md §12는 4개만 명시하고 있어 갱신 필요.

---

## 9. 일정

### 오늘 (8/19 수) 저녁

| A | B |
|---|---|
| ODsay 키 확인 → 실제 호출 → 응답 필드 파악(정류장 좌표 포함 여부) | 공용 파일 3개 + schema/seed + docker-compose push |
| `/routes/search` 골격 + Request/Response 스키마 | `/health`, `/system/meta` |
| 하드코딩 가중치(dict)로 스코어링 뼈대 | `save_candidates` 시그니처 확정 |

### 내일 (8/20 목)

| 시간 | A | B |
|---|---|---|
| 오전 | 실제 가중치 조회 연결, 분당개선, 비교 응답 | `GET /routes/{id}`, `/bike/docks`, `/admin/batch/latest` |
| 12시 | **통합 — `save_candidates` 연결, 프론트 연동 시작** | ← 같이 |
| 오후 | 에러 처리(400/404/429/502), 시연 좌표 튜닝 | 배포 지원 |
| 16시 | **코드 동결** | ← 같이 |
| 이후 | 배포·데모 리허설·README | ← 같이 |

---

## 10. 데모 시나리오

비교 화면에서 최단시간 경로와 추천 경로가 같으면 데모가 비어 보인다. 명세서 4절에서 이미 차이가 검증된
**래미안위브아파트 → 독산사거리**를 기본 좌표로 고정한다. 두 경로가 우연히 같은 경우를 대비해 응답에
`is_same` 플래그를 넣어, 프론트가 "가장 빠른 경로가 가장 쾌적하기도 합니다"로 표시하게 한다 (실패가 아닌
유효한 결과로 처리).

---

## 11. 커뮤니티 게시판 (2026-08-19 저녁 추가 — 스코프 재포함)

§3에서 "완전히 제외"였던 항목인데, 프론트에 이미 화면(글쓰기/커뮤니티 탭)이 있고 팀 확인 후
전체 CRUD로 다시 포함하기로 결정함. 로그인이 없는 서비스라(CLAUDE.md §4) 작성자 식별은
**닉네임(화면 표시용) + `X-Client-Token`(권한 확인용, 응답엔 안 나옴)** 조합으로 처리한다 —
쿠폰 기능(§3)이 이미 쓰는 것과 같은 방식(브라우저가 생성해 들고 있는 UUID)이라 프론트가 같은
토큰을 재사용해도 된다.

⚠️ **DB 미연동 상태** — 지금은 서버 프로세스 메모리에만 저장한다(재시작하면 게시글이 사라짐).
B의 core/db.py가 붙으면 `board_service.py` 내부 함수만 실제 SQL(psycopg, raw SQL, 파라미터
바인딩)로 교체하면 되게 만들어뒀다 — 라우터/스키마는 안 바뀜. 내일(8/20) 오전 A·B 통합 때
save_candidates와 같이 묶어서 처리하면 될 것 같음. (DB 스키마는 아직 안 만듦 — 통합 시점에
`route_request`/`route_candidate`와 함께 `board_post` 테이블도 필요하다고 B에게 전달 필요.)

### API 명세

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| POST | `/api/v1/board/posts` | 글 작성 (`nickname`, `content`) | `X-Client-Token` 필수 (없으면 400) |
| GET | `/api/v1/board/posts?limit=20&offset=0` | 목록 조회 (최신순) | 없음 |
| GET | `/api/v1/board/posts/{id}` | 상세 조회 | 없음 |
| PUT | `/api/v1/board/posts/{id}` | 내용 수정 (`content`만) | `X-Client-Token`이 작성자와 일치해야 함 (다르면 403) |
| DELETE | `/api/v1/board/posts/{id}` | 삭제 | 위와 동일 |

응답 예시(`PostOut`):
```json
{"id": 1, "nickname": "익명", "content": "글 내용", "created_at": "2026-08-19T07:43:38Z", "updated_at": "2026-08-19T07:43:38Z"}
```

에러 코드: `MISSING_CLIENT_TOKEN`(400), `POST_NOT_FOUND`(404), `NOT_POST_OWNER`(403).

구현: `backend/app/routers/board.py`, `backend/app/schemas/board.py`, `backend/app/services/board_service.py`,
테스트는 `backend/tests/test_board.py`(10개, 실제 uvicorn 서버 띄워서 curl로도 재검증함).
`dev_server.py`에도 등록해서 지금 바로 프론트에서 붙여 테스트 가능.

**프론트 전달 필요**: 상은님 화면이 이 API를 쓰려면 `X-Client-Token`을 프론트에서 생성(예:
`crypto.randomUUID()` 후 localStorage에 저장)해서 작성/수정/삭제 요청마다 헤더로 보내야 함 —
쿠폰 클레임에서 이미 만든 토큰이 있으면 그거 재사용해도 됨. 이 내용도 `docs/api-contracts/
routing.md` 쪽에 전달 필요(다른 계약들과 같은 방식으로, 직접 수정은 안 함).

---

## 12. 지금 팀 확인이 필요한 것 (열린 이슈 모음)

**해결됨**
- ~~§7.2 Q3 계단식→완만한 감산~~ → A 단독 결정 사항으로 확정 (scoring.py는 A 전담 파일)
- ~~§7.3 버스 `localStationID` = `stop_std_id` 여부~~ → 마스터 CSV 대조로 확인 완료, ID 직접 매칭으로 구현
- ~~§8 개인정보 처리안~~ → 팀 합의 완료, CLAUDE.md 반영 완료
- ~~§8 `/system/meta` 필드 수~~ → 6개로 확정, CLAUDE.md §12 반영 완료
- ~~ODsay API 키 확보~~ → 2026-08-19 발급 완료. 라이브 호출로 파라미터(SX/SY/EX/EY/OPT)·응답 필드
  검증 완료(odsay_parser.py 기대값과 정확히 일치). `backend/.env`에 저장, 인증 실패 시 `{"error":[...]}`
  형태로 200 응답이 오는 것도 확인해서 502/404 구분 처리 반영함(odsay_client.py)
- ~~버스 노선 곡선 지원 여부~~ → **해결됨 (2026-08-19).** 지하철처럼 전체를 미리 받기엔 노선 수가
  너무 많아(수도권 1,588개, 지하철의 8.8배) 요청에 등장한 노선만 그때 Overpass로 조회 + 프로세스 메모리
  캐싱하는 방식으로 구현. DB 저장 없음, 데모 좌표 하드코딩도 아니고 실제 API 기반 전체 커버리지. §6.3 참고.

**아직 열려 있음**
1. §7.2 `bus_weight`에 `stop_sequence` 컬럼 추가 — 김재우님 확인 필요 (정류장마스터 CSV에 이미 순번 데이터 있음)
2. 쿠폰(§3) 진행 여부 — B가 통합 후 시간 되면 진행, 최종 여부는 8/20 오후에 결정
3. ODsay 호출은 서버의 등록된 IP에서만 허용됨(ODsay LAB "설정"에서 Server IP 등록 필요) — 각자 개발 환경 IP가
   다르면 매번 등록을 바꿔야 함. AWS 배포 시 실제 서버 고정 IP로 재등록 필요 (김재우님 인프라 확정 시 확인)
4. ~~§6.1 지하철 노선 곡선 데이터(OSM) 통합~~ → **해결됨 (2026-08-19).**
   (a) 프론트(카카오맵 연동, Polyline 렌더링 등 화면 코드)는 전부 윤상은님 담당, A/B는 프론트 디렉토리에
   직접 코드를 얹지 않음. (b) 구간 자르기는 백엔드가 `/routes/search` segment의 `polyline` 필드로 이미 잘라서
   내려줌 — §6.2/§5.1 참고. `docs/api-contracts/routing.md`에도 반영 필요(윤상은님 브랜치라 직접 수정 안 함).
5. **[신규] 도보 구간 실제 경로(Tmap 보행자경로 API)** — A가 키 발급 진행 중(2026-08-19 저녁). 키 받으면
   지하철/버스와 동일한 `polyline` 계약으로 연결 예정(세그먼트 필드가 이미 `polyline` 하나로 통일돼 있어
   프론트/문서 추가 변경 없이 붙는다). 버스와 달리 도보는 정적 지오메트리로 안 되고 실제 라우팅 엔진(Tmap)
   응답을 그대로 써야 함.
6. **[신규] §6.3 버스 노선 Overpass 아웃바운드 확인** — AWS 배포 시 API 서버가 `overpass-api.de`(443)로
   나가는 경로가 보안그룹/NACL에서 막히지 않는지 김재우님 확인 필요. ODsay와 같은 NAT 경로를 타지만,
   2026-08-19 저녁 개발 환경에서 Overpass 쪽만 TCP 연결이 안 되는 현상을 실제로 겪어서(§6.3 참고) 별도
   확인이 필요하다고 판단함 — 배포 후 반드시 재확인.
7. **[신규] `board_post` 테이블이 아직 DB 스키마에 없음** — 지금은 프로세스 메모리 저장(§11). 내일
   오전 통합 때 `01_schema.sql`에 추가 필요 — 김재우님/B에게 전달 필요. 컬럼: id, nickname, content,
   owner_token, created_at, updated_at (전부 표준 SQL 타입, PG 전용 문법 없음).
