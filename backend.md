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

### 6.0 좌표 기반 근처 조회 추가 (2026-08-21, 백엔드 B)

위 `hub_type`/`hub_id` 계약은 "경로 검색 결과의 역/정류장 기준"으로만 설계됐었다(이 문서 §6, 2026-08-19
시점). 이후 프론트 자전거 탭이 "내 위치 근처"처럼 임의 좌표 기준으로 동작하도록 만들어지면서, 계약에
없는 `GET /bike/docks/nearby?lat&lng&radius_m` 형태를 호출하는 상태였다. 이번에 그 좌표 기반 조회 자체를
추가해 계약을 맞췄다:

```
GET /api/v1/bike/docks/nearby?lat=37.5665&lng=126.9780&radius_m=800 (기본 800, 최대 5000)
→ rental_dock 전체를 haversine으로 스캔(weight_repository.match_subway_station과 동일 패턴,
   PostGIS 미사용) → 반경 내 대여소를 거리순으로 반환
```

기존 `/bike/docks`(hub_type/hub_id)는 그대로 유지 — 경로 검색 결과 기준 조회는 계속 그걸 쓴다. 구현:
`backend/app/routers/bike.py`, 테스트: `backend/tests/test_bike.py`(`nearby_dock_fixture` 관련 2건 추가).

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

> 📄 **상세 워크스루는 [`scoring-logic.md`](scoring-logic.md) 참고** — 공식별 예시 계산, 방향
> 검증(0=쾌적이 실제로 안 뒤집혔는지), 2026-08-19 재검토에서 찾은 버그 2건(문서 불일치 1건
> +코드 버그 1건, 둘 다 수정 완료)까지 기록해뒀다. 여긴 결정 사항 요약만 남긴다.

시간이 없어 아래 값으로 **일단 진행**한다. 상수는 전부 코드 상단에 분리해서 나중에 바꾸기 쉽게 만든다.
**정규화 방향은 "0에 가까울수록 쾌적"으로 통일** — 이게 어긋나면 추천이 정확히 거꾸로 나온다.

### 7.1 확정 값

| | 값 |
|---|---|
| Q1 점수 통합 | 지하철 `min(congestion_pct/150, 1.0)`, 버스 `min(net_onboard/50, 1.0)`<br>경로 점수 = 구간 소요시간 가중평균 |
| Q2 baseline | ODsay 후보 중 `total_time_min` 최솟값 |
| Q4 매칭 | 지하철: 좌표 100m 반경 매칭. 버스: ~~50m 반경~~ → §7.3에서 ID 직접 매칭(`stop_std_id = localStationID`)으로 변경 확정, 반경 매칭 아예 없음. 실패 시 `matched: false` + 중립값 0.5 |

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
- **(2026-08-20 반영)** `bus_weight.stop_sequence`는 배치가 실제로 채워서 붙었다(`feature/batch-etl`).
  또한 `station_weight`/`bus_weight` 조회가 `weight_repository.py`를 통해 실제 DB로 연결됐고(`feature/
  weight-db-lookup`), `station_weight`의 UNIQUE 키에 `direction`이 추가됐다 — 아래 §7.2.1은 이 두 변경
  이후 상태를 기준으로 작성했다.

### 7.2.1 Q3 재개정 — 순증감(하차−승차) 기반 보정으로 전환 (2026-08-21)

`TangTang_혼잡도_스코어링_로직_기술보고서_수정.md`(외부 검토 보고서)가 위 7.2의 구조적 결함을 지적했다:
`stop_sequence` 감산은 "출고역에서 멀수록 혼잡하다"는 가정 하나에만 기대는 대리 지표라, **환승역처럼
초반 정차순번에서 대량 하차가 몰리는 지점**에서는 실제로는 덜 혼잡해지는데도(순감소) 낮은 stop_sequence
때문에 오히려 큰 보너스를 주거나, 반대로 초반에 대량 승차가 몰리는 구간(실제로는 더 혼잡해짐)에도 보너스
방향이 못 갈린다 — `stop_sequence_discount()`는 항상 1.0 이하만 내놓는 단방향 함수이기 때문이다.

**대체 로직**: 배치가 채워주는 승차/하차 추정치(`boarding_est`/`alighting_est`)가 둘 다 있으면, 정차순번
대신 이 값으로 직접 보정한다.

```python
NET_CHANGE_CLAMP = 0.3
SUBWAY_CAR_CAPACITY = 160.0  # 근거 데이터 없는 추정 정원 — K/MAX_BONUS와 같은 위상의 상수

def net_change_discount(alighting_est, boarding_est, capacity):
    net_change_ratio = (alighting_est - boarding_est) / capacity
    clamped = max(-NET_CHANGE_CLAMP, min(NET_CHANGE_CLAMP, net_change_ratio))
    return 1.0 - clamped

def stop_correction_factor(stop_sequence, boarding_est=None, alighting_est=None):
    if boarding_est is not None and alighting_est is not None:
        return net_change_discount(alighting_est, boarding_est, SUBWAY_CAR_CAPACITY)
    return stop_sequence_discount(stop_sequence)  # 폴백 — 배치가 아직 못 채운 행
```

기존 `stop_sequence_discount()`는 **완전히 대체되는 게 아니라 폴백으로 남는다** — `boarding_est`/
`alighting_est` 둘 중 하나라도 없으면(배치 미반영) 그대로 쓴다. 두 값이 다 있을 때만 우선 적용.

**7.2의 감산과 정반대인 지점**: `stop_sequence_discount()`는 항상 `factor ≤ 1.0`(보너스만 있고 페널티는
없음)이지만, `net_change_discount()`는 순증가(승차>하차) 상황에서 `factor > 1.0`이 나올 수 있다 — 즉
"더 혼잡해진다"는 방향도 표현할 수 있다. 이 때문에 `score_segment()`의 `base * factor`가 이론상 1.0을
넘을 수 있어(예: `congestion_pct=140`인 역에 순증가가 겹치면), 최종적으로 `min(base * factor, 1.0)`
클램프를 다시 적용해 Q1의 정규화 상한(0~1)을 지킨다.

**DB 반영**: `station_weight`/`bus_weight`에 `boarding_est`/`alighting_est NUMERIC(10,2)` NULL 허용
컬럼을 추가했다(01_schema.sql). NULL이면 위 폴백이 자동으로 적용되므로 배치 쪽 별도 마이그레이션
순서 제약은 없다 — 컬럼이 비어 있는 동안은 기존 동작과 100% 동일하다.

**테스트**: `test_scoring.py`에 `net_change_discount`/`stop_correction_factor`의 양방향성(순감소→factor<1,
순증가→factor>1), 클램프, 폴백 우선순위, 환승역 시나리오에서 레거시 감산과 정반대 방향이 나오는지,
그리고 `base*factor>1.0`이 되는 조합에서도 최종 점수가 1.0을 넘지 않는지를 추가했다. `weight_repository.py`
쪽 SELECT에 새 컬럼 두 개를 추가하고 `test_weight_repository.py`에도 그 값이 실제로 조회되는지 확인을
추가했다.

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

**[2026-08-20 갱신, 백엔드 B]** 위 절삭 저장안을 다시 검토해 Postgres 테이블(`route_request`/
`route_candidate`) 자체를 없애고 Redis TTL(`route:request:{id}`, 1시간)로 전환했다. `favorites`가
"사용자가 다시 보고 싶어하는 결과"를 이미 영구 보관(`route_snapshot` JSONB)으로 전담하고 있어서,
이 두 테이블은 애초에 영구 저장될 이유가 없었다는 판단 — 좌표도 절삭 없이 저장하지 않는다. Postgres는
그대로 메인 DB이고(마스터/가중치/`users`/`board_post`/`coupon` 무관), `GET /routes/{request_id}`
응답 스키마·A의 `save_candidates` 호출 인터페이스는 그대로다. 상세: `docs/decisions/backend-b.md` 4번.

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

**⚠️ 업데이트(같은 날 저녁, §12 참고)**: 위 X-Client-Token 방식은 로그인 기능이 추가되면서
**대체됐다.** 게시판 작성/수정/삭제는 이제 로그인(§12의 JWT)이 필요하고, 닉네임도 매번
입력하는 대신 가입 닉네임을 자동으로 쓴다. 목록/상세 조회는 여전히 비회원도 가능(공개).
아래 문단은 옛 방식 기록으로 남겨두고 히스토리 참고용으로만 둔다.

**프론트 전달 필요(갱신됨)**: 상은님 화면은 게시판 글쓰기/수정/삭제 버튼을 눌렀을 때 로그인
여부를 확인해서, 비로그인 상태면 "로그인이 필요한 서비스입니다" 안내와 함께 회원가입/로그인
화면으로 유도해야 함 — 백엔드는 `401 {"code": "LOGIN_REQUIRED"}`로 이 상태를 알려준다
(§12 참고). 이 내용도 `docs/api-contracts/routing.md` 쪽에 전달 필요(직접 수정은 안 함).

---

## 12. 로그인/회원 기능 (2026-08-19 저녁 추가)

CLAUDE.md §4/§13은 원래 "1차 MVP엔 회원가입/로그인 없음, 임의로 추가 금지"였다. 이번엔
팀(사용자) 요청으로 직접 추가하기로 결정 — 기본 서비스(경로 검색)는 여전히 로그인 없이
그대로 쓸 수 있고, **게시판 작성/수정, 즐겨찾기**처럼 계정에 딸린 기능만 로그인을 요구하는
방향이다. 비회원이 이런 기능을 누르면 `401 LOGIN_REQUIRED` → 프론트가 "로그인이 필요한
서비스입니다" + 회원가입 화면 안내로 처리(§11 참고, 게시판에 이미 반영됨).

### 인증 방식 — JWT (B 요청사항 반영)

김창영(B)이 쿠폰 등 다른 라우터에서도 로그인 결과를 바로 쓸 수 있게 아래 4가지를
요청했고, 전부 반영했다:

1. **공용 Dependency** — `app.services.auth_service.get_current_user_id`. 다른 라우터(쿠폰
   포함)에서 그대로 가져다 쓰면 됨:
   ```python
   from app.services.auth_service import get_current_user_id

   @router.post("/coupons/claim")
   def claim_coupon(current_user_id: int = Depends(get_current_user_id)):
       ...
   ```
   비회원/만료/위조 토큰은 전부 이 Dependency가 알아서 401 `{"code": "LOGIN_REQUIRED"}`로
   던진다 — 호출부에서 따로 검증할 것 없음.
2. **JWT, `Authorization: Bearer <token>` 헤더** — 그대로 채택. 토큰 안에 `user_id`만 담고
   서명(HS256)만 검증하면 끝나서, **DB/Redis 조회가 전혀 없다.** A/B 파일이 저장소를 공유할
   필요가 없어진다는 부수 이점도 있음(지금처럼 core/db.py·core/redis.py가 아직 안 붙은
   상태에서도 서로 독립적으로 진행 가능). 비밀키는 `.env`의 `JWT_SECRET` — 배포 전 반드시
   교체 필요(`.env.example`에 경고 문구 남겨둠).
3. **users 테이블 PK** — `id`(정수, 자동증가) 확정. 지금은 프로세스 메모리 카운터로
   구현했지만 실제 스키마에서도 그대로 `id`가 PK가 된다 — B 쪽 테이블에서 FK로 참조해도 됨.
4. **쿠폰 조회/받기 정책** — "조회는 비회원도, 받기(claim)만 로그인 필요"는 게시판에 이미
   적용한 것과 같은 원칙(읽기는 공개, 계정에 남는 행위만 회원전용)이라 그대로 맞는 방향.
   실제 반영은 B의 `routers/coupon.py`에서 진행 — `get_current_user_id`를 그 라우터의
   claim 엔드포인트에 붙이기만 하면 됨. 기존 `X-Client-Token`(익명 기기토큰) 기반 중복
   방지는 `coupon:issued:{user_id}`처럼 user_id 기준으로 바꾸는 걸 권장하지만, 이 파일은
   B 담당이라 최종 결정/구현은 B가 함.

### 알아두어야 할 트레이드오프

JWT는 서버가 세션 상태를 안 들고 있어서, **로그아웃해도 그 토큰은 만료 전까지 계속
유효하다**(서버가 강제로 무효화할 방법이 없음). 그래서 만료시간을 24시간으로 짧게 잡았다.
완전히 막으려면 블록리스트(Redis)가 필요한데, 그러면 결국 공유 저장소가 다시 필요해져서
JWT를 쓰는 이유가 옅어진다 — 이번 스프린트에서는 과한 대응이라 판단해 로그아웃 API 자체를
안 만들었다(프론트가 토큰을 지우는 것으로 끝).

### API 명세

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 회원가입 (`username`, `password`, `nickname`) → 토큰+유저 | 없음 |
| POST | `/api/v1/auth/login` | 로그인 (`username`, `password`) → 토큰+유저 | 없음 |
| GET | `/api/v1/auth/me` | 내 정보 조회 | `Authorization: Bearer` 필요 |

`username`은 영문/숫자/`_`만, 3~20자. `password`는 8~100자(bcrypt 해시로만 저장). `email`은
아예 안 받음 — N-04(개인정보 최소화) 취지와 일관되게 이번 스프린트에 안 쓰는 개인정보는
처음부터 요구하지 않음.

에러 코드: `USERNAME_TAKEN`(409), `INVALID_CREDENTIALS`(401, 아이디 없음/비번 틀림 구분 안
함 — 계정 열거 공격 방지), `LOGIN_REQUIRED`(401, 토큰 없음/만료/위조 전부 동일 처리).

### 게시판 변경사항

작성/수정/삭제가 로그인 필요로 바뀌었다(§11 참고). `PostCreate`에서 `nickname` 필드가
빠졌다 — 이제 로그인한 계정의 닉네임을 자동으로 쓴다.

### 즐겨찾기 (신규 기능)

"즐겨찾기"는 특정 역/정류장이 아니라 **출발지-도착지 조합**을 저장하는 것으로 정의했다
(예: "집→회사") — `SearchRequest`와 좌표 모양이 같아서 프론트가 그대로 재검색에 쓸 수 있음.

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/favorites` | 즐겨찾기 추가 (`label`, `origin`, `destination`) |
| GET | `/api/v1/favorites` | 내 즐겨찾기 목록 |
| DELETE | `/api/v1/favorites/{id}` | 삭제 (본인 것만) |

전부 로그인 필요. 본인 것이 아닌 즐겨찾기 삭제 시도는 403 `NOT_FAVORITE_OWNER`.

### DB/인프라 확인 필요 (내일 오전 통합 시)

- `users`(id PK, username UNIQUE, password_hash, nickname, role, created_at), `favorite`
  (id PK, user_id FK, label, origin_lat/lng, destination_lat/lng, created_at) 테이블이
  스키마에 없음 — `01_schema.sql`에 추가 필요(김재우님/B 확인).
- `board_post`도 아직 스키마에 없음(§11에 이미 기록) — 이번에 `owner_user_id`(FK)로 바뀜.
- **[2026-08-20 갱신, 백엔드 B]** 실제 DB 연동 완료. `01_schema.sql`에 `favorite` 테이블
  추가, `auth_service.py`/`board_service.py`/`favorite_service.py`를 프로세스 메모리에서
  실제 Postgres 쿼리로 교체함(다른 프로세스 간에도 계정/글/즐겨찾기가 그대로 보이는 것까지
  확인) — k8s로 복제본 여러 개를 띄우면 프로세스 메모리 저장은 파드마다 따로 놀아서
  깨지기 때문에 다음 주 배포 작업 전에 먼저 처리했다. 인터페이스(함수 시그니처/반환 타입)는
  그대로라 라우터 쪽은 변경 없음.

### 구현 위치

`backend/app/schemas/auth.py`, `favorite.py` / `backend/app/services/auth_service.py`,
`favorite_service.py` / `backend/app/routers/auth.py`, `favorites.py`. 테스트는
`test_auth.py`(10개), `test_favorites.py`(7개), `test_board.py`(로그인 기반으로 재작성,
10개) — 전부 `dev_server.py`에도 등록해서 실제 서버로 재검증함.

---

## 13. ODsay 쿼터 실측 — 일 30건(문서상 1,000건 아님) + 캐싱/회로차단기 (2026-08-19 밤)

**실측 경위**: 어떤 API는 일 30건, 어떤 건 월 1,000건 등 단위가 다 달라서 어디가 진짜
부족한지 판단이 안 된다는 이유로, 실제로 우리 키로 라이브 40회 연속 호출해봄. 결과:
**29번째까진 성공, 30번째부터 `{"code":"429","message":"Daily quota exceeded"}`.**
CLAUDE.md §3에 있던 "무료 한도 1,000건/일"은 잘못된 정보였음 — **실제로는 30건/일**로
확정(사용자 본인 확인). CLAUDE.md §3 정정 완료.

**왜 이게 제일 급한 문제인가**: Tmap(도보)/Overpass(버스노선)는 소진돼도 폴리라인만
직선으로 폴백되고 서비스 자체는 안 죽는다. **ODsay는 대체 불가능한 핵심 데이터소스라
소진되면 `/routes/search` 전체가 죽는다.** 30건/일이면 팀원 4명이 리허설 중 몇 번씩만
눌러봐도 순식간에 바닥날 수 있는 규모.

**대응 — `backend/app/services/odsay_client.py`에 두 가지 추가**:
1. **응답 캐싱**: 동일 (출발, 도착) 좌표 재요청은 실제 API를 다시 안 부르고 캐시 반환.
   TTL 30분(자리표시자, Redis 붙으면 교체 — core/db.py·core/redis.py 통합 전까지는
   프로세스 메모리, board_service.py 등과 동일 패턴). `call_odsay()`가 애초에
   departure_time을 ODsay에 안 넘기므로 캐시 키는 좌표 4개만 사용함 — 나중에 시간대별
   조회가 실제로 붙으면 캐시 키에 departure_time도 포함시켜야 함.
2. **쿼터 소진 회로차단기**: ODsay가 쿼터 소진(코드 429 또는 메시지에 "quota" 포함)을
   한 번이라도 반환하면, 그 시점부터 1시간(자리표시자) 동안 좌표 조합이 달라도 실제
   호출 자체를 생략하고 바로 503으로 응답 — 이미 소진된 걸 알면서 새 검색마다 계속
   두들기는 걸 막음.
3. 새 에러 코드 `UPSTREAM_QUOTA_EXCEEDED`(503) 추가 — 기존 `UPSTREAM_ERROR`(502, 그 외
   ODsay 오류)와 구분해서 프론트/운영이 "쿼터 때문에 안 되는 것"과 "그냥 오류"를 구별할
   수 있게 함.

**한계**: 프로세스 메모리라 서버 재시작하면 캐시/쿨다운 상태 다 날아감(내일 오전 Redis
연동 시 해결 예정). 그리고 캐시는 "같은 좌표 재요청"만 막아주고, **서로 다른 좌표로 계속
새로 검색하면 캐싱이 도움이 안 됨** — 리허설 때 되도록 데모 좌표(§10)로 반복 테스트하고,
매번 다른 좌표로 무작정 테스트하는 건 자제하는 게 안전함.

구현: `backend/app/services/odsay_client.py`, 라우터 처리는 `backend/app/routers/search.py`.
테스트는 `backend/tests/test_odsay_client.py`(8개 추가, httpx 모킹으로 검증). 전체
90개 테스트 통과.

---

## 14. 지금 팀 확인이 필요한 것 (열린 이슈 모음)

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
5. ~~도보 구간 실제 경로(Tmap 보행자경로 API)~~ → **해결됨 (2026-08-19 밤, 라이브 검증
   완료).** `backend/app/services/walk_geometry.py`. 최초엔 발급받은 앱키로 403
   `INVALID_API_KEY`가 났었는데 — SK Open API 콘솔에서 "보행자경로안내" 상품을 앱키에
   개별로 활성화해야 하는 구조였고, 활성화 후 재시도해서 정상 동작 확인함(답십리→왕십리
   실좌표로 132개 점짜리 실제 보행로 반환, 시작/끝 좌표 오차 10m 이내). 버스와 달리 캐싱은
   안 함(임의 좌표쌍이라 재사용 효과 없음) — 도보 구간마다 매번 실시간 호출이 나가므로
   세그먼트가 많은 후보는 그만큼 응답이 느려질 수 있다는 점은 알아두어야 함. `TMAP_APP_KEY`
   없으면 여전히 네트워크 호출 없이 조용히 직선 폴백.
6. **[참고] OSRM 자전거 라우팅 — 지금은 범위 밖, 준비는 돼 있음.** 김재우님이 자체 호스팅
   OSRM(자전거 프로필)으로 "출발~도착 사이 실제 자전거 경로선"까지 검증 완료해둔 상태.
   지금 스코프는 대여소 조회(§6)까지만이라 당장 연동 안 함 — 나중에 자전거 경로 폴리라인이
   필요해지면 OSRM 서버 URL만 env로 받아서 연동 가능.
7. **[신규] §6.3 버스 노선 Overpass 아웃바운드 확인** — AWS 배포 시 API 서버가 `overpass-api.de`(443)로
   나가는 경로가 보안그룹/NACL에서 막히지 않는지 김재우님 확인 필요. ODsay와 같은 NAT 경로를 타지만,
   2026-08-19 저녁 개발 환경에서 Overpass 쪽만 TCP 연결이 안 되는 현상을 실제로 겪어서(§6.3 참고) 별도
   확인이 필요하다고 판단함 — 배포 후 반드시 재확인.
8. **`board_post`/`users`/`favorite` 테이블이 아직 DB 스키마에 없음** — 지금은 전부 프로세스
   메모리 저장(§11/§12). 내일 오전 통합 때 `01_schema.sql`에 추가 필요 — 김재우님/B에게 전달 필요.
   `board_post` 컬럼: id, nickname, content, **owner_user_id(users.id FK, 2026-08-19 저녁
   로그인 도입 후 X-Client-Token에서 변경됨)**, created_at, updated_at. `users`/`favorite`
   컬럼은 §12 "DB/인프라 확인 필요" 참고. 전부 표준 SQL 타입, PG 전용 문법 없음.
