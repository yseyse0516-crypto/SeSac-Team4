# 텅텅 (TangTang)

재차인원(net onboard) 기반 서울 통근 혼잡회피 서비스. 표시되는 혼잡도는 "하차 전" 상태라, 실제로는 대량 하차 직후 훨씬 여유로운 경우가 많다는 데이터 기반 인사이트에서 출발했다.

## 시작하기 전에

반드시 **[`CLAUDE.md`](./CLAUDE.md)** 를 먼저 읽으세요. 팀 역할, 외부 API 호출 규칙, 개인정보 원칙이 정의되어 있습니다.
백엔드 상세 계획(담당 분담, API 명세, 스코어링 로직 확정값)은 **[`backend.md`](./backend.md)** 참고.

기획 명세서 원문: [`docs/spec/4조_1차MVP_기획명세서2026_08_18.pdf`](./docs/spec) · 구성도(파이프라인·네트워크·ERD): [`docs/architecture/`](./docs/architecture)

## 기술 스택

| 영역 | 기술 | 비고 |
|---|---|---|
| Frontend | React (Vite) | Next.js 미사용 |
| Backend | FastAPI (Python) | 요청 처리 서버 + 오프라인 배치(월 1회) 분리 |
| DB | **PostgreSQL** (확정) | **ORM 미사용** — `psycopg`(v3) + 원시 SQL |
| 캐시 | Redis | ODsay 응답 캐시, 일일 호출 카운터, 따릉이 재고 캐시 (로그인 세션 없음) |
| 리버스 프록시 | nginx | FastAPI 앞단 |
| 외부 API | ODsay LAB 경로탐색 API | 요청 1건당 1회 호출 |
| 배포 | AWS (`tangtang-vpc`, `10.0.0.0/16`) → Kubernetes (2차, 연습용) | |

## 팀

| 담당 | 이름 | 역할 |
|---|---|---|
| 백엔드 | 정종우 | `POST /routes/search` — ODsay 연동, 좌표 매칭, 스코어링, 분당개선 필터링 |
| 백엔드 | 김창영 | 조회·보조 API(`/routes/{id}`, `/bike/docks`, `/system/meta`, `/health` 등), DB/Redis 인프라 |
| 프론트엔드 | 윤상은 | 지도, 경로 UI, 화면 |
| DB·데이터·인프라 | 김재우 | 공공데이터 배치, 가중치 계산, DB 설계, AWS 인프라 |

## 처리 구조

1. 오프라인 배치(월 1회): 서울교통공사·서울시 파일 + 국토교통부 API 4종 → 가중치 저장소(DB)
2. 사용자 요청 시: ODsay 1회 호출 → 가중치 매칭·스코어링 → 분당개선 필터링 → 클라이언트 응답
3. 따릉이 실시간 재고는 별도 저빈도 API로 확인 (오프라인 배치·ODsay 예산과 무관)

## 실행 방법

### 0. 사전 준비
- Node.js {버전}, Python {버전}
- PostgreSQL, Redis, nginx (로컬 설치 또는 Docker Compose)
- ODsay LAB API 키 (사전 발급 필요)
- 프론트엔드는 별도 리포지토리(`SeSac-Team4-Frontend`)다 — 이 리포엔 `frontend/`가 없다.

```bash
git clone https://github.com/yseyse0516-crypto/SeSac-Team4-Frontend.git ../SeSac-Team4-Frontend
cp ../SeSac-Team4-Frontend/.env.example ../SeSac-Team4-Frontend/.env
cp backend/.env.example backend/.env
```

### 1. DB / Redis
```bash
docker compose up -d db redis
```
`db` 컨테이너 기동 시 `backend/sql/01_schema.sql` + `02_seed.sql`이 자동 적재되어 개발용 더미 데이터로 바로 스코어링 테스트가 가능합니다.

### 2. Backend (요청 처리 서버)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 오프라인 배치 (최초 1회 수동 실행 — 가중치 저장소를 채워야 API가 정상 동작합니다)
```bash
cd backend
pip install openpyxl   # bus_stop 마스터 파일(xlsx) 파싱에 필요
python -m app.batch.run_batch
```
`rental_dock` 단계는 행안부 실시간 API를 호출합니다(`BIKE_STOCK_API_KEY` 환경변수 필요) —
키가 없으면 그 단계만 빈 결과로 넘어가고 나머지 단계는 정상 진행됩니다. 대여소만 단독으로
재동기화하고 싶다면 `python -m app.batch.run_dock_batch`를 대신 쓰면 됩니다.

### 4. Frontend (별도 리포지토리)
```bash
cd ../SeSac-Team4-Frontend
npm install
npm run dev
```

## 필수 환경변수

| 변수명 | 설명 |
|---|---|
| `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` | PostgreSQL 접속 정보 (`core/db.py`가 개별 변수로 읽음, `psycopg` v3) |
| `REDIS_HOST`/`REDIS_PORT` | Redis 접속 정보 (`core/redis.py`가 개별 변수로 읽음) |
| `ODSAY_API_KEY` | ODsay LAB 경로탐색 API 키 |
| `ODSAY_DAILY_QUOTA` | ODsay 일일 호출 한도 (실측 30 — 문서상 1,000이었으나 2026-08-19 라이브 테스트로 정정) |
| `JWT_SECRET` | 로그인 토큰 서명 비밀키 (배포 전 반드시 무작위 값으로 교체) |
| `TMAP_APP_KEY` | 도보 구간 실제 경로(SK Tmap 보행자경로안내) API 키. 비어있으면 도보는 직선으로 표시됨 |
| `SERVER_VERSION` / `SERVER_NAME` / `SERVER_IP` | 화면 하단 버전 배너 표시용 |

## 배포 정보

| 구분 | 값 |
|---|---|
| VPC | `tangtang-vpc`, `10.0.0.0/16` (2 AZ × Public/Front(예약)/API/DB 4계층) |
| 배포 환경 | AWS ({EC2 / ECS 등 — 확정 후 기입}) |
| URL | {배포 URL} |
| 2차(연습) | Kubernetes |

## 개인정보 원칙

사용자의 위치 이력·식별정보는 저장하지 않으며, 요청 처리 목적으로만 일시적으로 사용합니다. 검색 요청/추천 결과 로그는 Postgres 테이블이 아니라 Redis에 짧은 TTL(1시간)로만 유지하고, 좌표는 저장하지 않습니다. 사용자가 명시적으로 저장을 선택한 즐겨찾기(favorites)만 별도로 영구 보관됩니다 (자세한 내용은 `backend.md` §8, CLAUDE.md §4 참고).

## 브랜치: `feature/station-weight-direction` — `main` 대비 변경 내역

`station_weight`의 UNIQUE 키에 `direction`(상선/하선/내선/외선)이 추가되면서 `station_id`만으로는
조회 결과가 유일하지 않게 된 문제를 해결하는 브랜치입니다. `odsay_parser.py`가 이미 파싱해두고
쓰지 않던 하차역(`end_lat`/`end_lng`) 좌표를 매칭에 활용해 방향을 계산하고, 가중치 조회를
`(station_id, direction)` 조합으로 바꿨습니다. 로컬 Postgres 연동 테스트 포함 전체 스위트 124개
전부 통과 확인했습니다.

**수정된 파일 (6개)**

| 파일 | 변경 내용 |
|---|---|
| `backend/app/routers/search.py` | 하차역 좌표도 매칭해 direction 계산 후 scoring에 전달. 기존 `STATION_WEIGHT` 조회(응답의 `stop_sequence` 필드용)도 `(station_id, direction)` 키로 함께 수정 |
| `backend/app/schemas/route.py` | 응답 `Segment`에 `direction` 필드 추가(디버깅/프론트 노출용) |
| `backend/app/services/hardcoded_weights.py` | `StationMaster`에 `line_name`/`station_no` 추가, `STATION_WEIGHT` 키를 `(station_id, direction)`으로 변경 |
| `backend/app/services/matching.py` | `MatchResult`에 `line_name`/`station_no` 추가(매칭 성공 시 채워짐) |
| `backend/app/services/scoring.py` | `score_segment()`에 `direction` 파라미터 추가, `(station_id, direction)`으로 조회 |
| `backend/tests/test_matching.py`, `backend/tests/test_scoring.py` | 새 시그니처/필드에 맞춰 테스트 갱신 |

**추가된 파일 (2개)**

| 파일 | 내용 |
|---|---|
| `backend/app/services/direction.py` | `determine_direction()` — 2호선은 원형 산술(외선/내선), 1·8호선은 물리순서 리스트 비교(동묘앞/남위례 역번호 예외 처리), 나머지 노선은 역번호 대소 비교. 2호선 지선(성수/신정)은 원형 규칙이 안 통해 의도적으로 `None`(중립값) 처리 |
| `backend/tests/test_direction.py` | `direction.py` 단위 테스트 12개(원형 규칙, 지선 예외, 물리순서 예외, 퇴화 케이스 등) |

## 브랜치: feature/batch-etl — main 대비 변경 내역

`SeSac-Team4-zer0` 로컬 폴더에만 파일로 존재하고 git에는 한 번도 커밋된 적 없던 오프라인 배치(ETL) 스크립트를 이 저장소에 반영하는 브랜치입니다. `feature/station-weight-direction`과는 독립적으로 `main`에서 분기했습니다.

### 수정된 파일 (3개)

| 파일 | 변경 내용 |
|---|---|
| `backend/requirements.txt` | `openpyxl` 추가 (`bus_stop_sync.py`의 정류소 마스터 xlsx 파싱에 필요) |
| `backend/sql/01_schema.sql` | `bus_weight`에 `stop_sequence` 컬럼 추가 — backend.md §7.2/§7.3에서 A(정종우)가 요청했던 컬럼. `bus_weight_sync.py`가 이미 이 컬럼이 있다고 가정하고 작성돼 있어서, 실제로 배치를 돌려보기 전까지는 드러나지 않았던 스키마 간극이었습니다 |
| `README.md` | "실행 방법 §3 오프라인 배치" 절이 가리키던 존재하지 않는 `python -m app.batch.run_monthly_batch`를 실제 진입점 `run_batch`로 정정 |

### 추가된 파일 (11개)

| 파일 | 설명 |
|---|---|
| `backend/app/batch/__init__.py` | 패키지 초기화 |
| `backend/app/batch/station_sync.py` | `station` 마스터 UPSERT |
| `backend/app/batch/bus_stop_sync.py` | `bus_stop` 마스터 UPSERT (xlsx 파싱) |
| `backend/app/batch/dock_master_sync.py` | `rental_dock` 마스터 UPSERT (행안부 실시간 API, `BIKE_STOCK_API_KEY` 필요 — 없으면 빈 결과로 스킵) |
| `backend/app/batch/station_weight_sync.py` | 이번 `batch_id`로 `station_weight` INSERT (방향 포함) |
| `backend/app/batch/bus_weight_sync.py` | 이번 `batch_id`로 `bus_weight` INSERT |
| `backend/app/batch/dock_hub_distance_sync.py` | 이번 `batch_id`로 `dock_hub_distance` INSERT |
| `backend/app/batch/run_batch.py` | 위 6단계를 `batch_run` 한 행으로 묶는 통합 러너 (신규 정식 진입점, `python -m app.batch.run_batch`) |
| `backend/app/batch/run_dock_batch.py` | 대여소만 단독으로 재동기화하는 기존 러너 (참고용으로 유지) |
| `backend/app/batch/data/*.xlsx`, `*.csv` (4개) | 배치가 읽는 원천 데이터 파일 |

### 실제로 배치를 돌려보며 발견해 함께 고친 버그 2건

1. **커넥션 풀 미개방**: `run_batch.py`/`run_dock_batch.py`가 `main.py`의 FastAPI lifespan(`pool.open()`/`.close()`)에만 의존하고 있어, 독립 프로세스로 실행하면 `psycopg_pool.PoolClosed`로 즉시 실패했습니다. `.env` 로딩도 빠져 있었습니다. → 두 러너 모두 자체적으로 `load_dotenv()` + `pool.open()`/`.close()`를 하도록 수정.
2. **FK 트리거 비활성화 권한 문제**: `bus_weight_sync.py`/`dock_hub_distance_sync.py`의 대량 병합 최적화가 `ALTER TABLE ... DISABLE TRIGGER ALL`로 FK 트리거를 끄는 방식이었는데, FK RI 트리거는 시스템 트리거라 테이블 소유자라도 superuser가 아니면 `permission denied: ... is a system trigger`로 실패합니다(운영 DB 계정도 superuser가 아닐 것이므로 그대로면 운영에서도 항상 실패했을 것). → FK 제약을 `DROP` 했다가 병합 후 다시 `ADD`하는 방식(소유자 권한만 필요)으로 교체.

### 검증

로컬 Postgres(이 저장소의 스키마 그대로, tangtang 역할)에 대해 `python -m app.batch.run_batch`를 실제로 끝까지 실행: `station=269건`, `bus_stop=12898건`, `station_weight=75320건`, `bus_weight=4565880건`(`stop_sequence` 채워짐), `dock_hub_distance=405건`, `rental_dock=0건`(API 키 없어 정상 스킵). 이후 DB를 깨끗한 시드 상태로 리셋하고 `pytest` 전체 110/110 통과 확인(배치 코드 추가가 기존 테스트에 영향 없음).

## 브랜치: feature/weight-db-lookup — `feature/station-weight-direction` + `feature/batch-etl` 통합 기준 변경 내역

⚠️ **초안(draft) — A(정종우) 리뷰 전.** `matching.py`/`scoring.py`는 A 전담 파일이고, 이 브랜치가 그 두 파일과 A의 테스트 파일(`test_matching.py`, `test_scoring.py`, `test_search_router.py`)을 수정합니다. main 병합 전 반드시 A 리뷰가 필요합니다.

배치가 이제 `station`/`bus_stop`/`station_weight`/`bus_weight`에 실제 데이터를 채우므로, `search.py`가 `hardcoded_weights.py`의 가짜 값 대신 이 테이블들을 조회하도록 연결하는 브랜치입니다. `station_weight`가 `direction` 컬럼으로 유니크 키를 잡기 때문에 `feature/station-weight-direction`이 선행돼야 하고, `bus_weight.stop_sequence` 컬럼과 실제 배치 데이터가 필요해 `feature/batch-etl`도 선행돼야 합니다 — 그래서 이 브랜치는 `main`이 아니라 두 브랜치를 먼저 병합한 `integration/direction-and-batch-etl`에서 분기했습니다.

### 설계 결정 — DB에 값이 없을 때

배치가 아직 안 돌았거나, 매칭은 됐는데 해당 역/구간·시간대·방향 조합 데이터가 없으면 기존 Q4 매칭 실패 정책과 동일하게 중립값(`NEUTRAL_CONGESTION_SCORE=0.5`)으로 처리합니다. 없는 값을 임의로 추정하거나 다른 방향/시간대 값을 대신 쓰지 않습니다.

### 추가된 파일 (2개)

| 파일 | 설명 |
|---|---|
| `backend/app/services/weight_repository.py` | station/bus_stop/station_weight/bus_weight 실 데이터 조회 계층. `time_slot_for()`(시각→시간당 버킷 변환), `latest_batch_id()`, `match_subway_station()`/`match_bus_stop()`(반경/ID 매칭), `get_station_weight()`/`get_bus_weight()`(방향·시간대·요일 조합 조회) |
| `backend/tests/test_weight_repository.py` | 위 조회 함수들의 단위 테스트(전용 행을 심고 지움 — seed 데이터는 `direction=NULL`/30분 버킷이라 이 모듈의 조회 조건과 안 맞아 의도적으로 안 씀) |

### 수정된 파일 (4개)

| 파일 | 변경 내용 |
|---|---|
| `backend/app/services/matching.py` | `match_subway_station()`/`match_bus_stop()`에 `cur=None` 파라미터 추가. `cur`를 넘기면 `weight_repository.py`로 실제 DB 조회, 안 넘기면(기존 단위 테스트 호출 방식) 지금까지의 하드코딩 fixture 그대로 사용 — 기존 단위 테스트 무변경 보존 |
| `backend/app/services/scoring.py` | `score_segment()`에 `cur=None`, `dt=None`, `route_id=None` 파라미터 추가. 같은 원칙(`cur` 있으면 실제 DB, 없으면 기존 하드코딩) |
| `backend/app/routers/search.py` | 요청 하나당 `db.get_cursor()`로 커서 하나를 열어 모든 세그먼트의 매칭·스코어링에 재사용. `departure_time` 미지정 시 `now()`를 조회 기준 시각으로 사용 |
| `backend/tests/test_matching.py`, `test_scoring.py` | `cur`를 넘기는 DB 조회 경로에 대한 단위 테스트 추가(기존 하드코딩 경로 테스트는 그대로 유지) |
| `backend/tests/test_search_router.py` | `search.py`가 이제 항상 실제 DB를 조회하므로, `02_seed.sql`의 더미 데이터만으론 `odsay_sample_response.json`이 참조하는 실제 역/정류장(답십리·여의도, `118000070`)이 없어 두 테스트가 깨졌습니다. 이 파일 전용으로 그 역/정류장에 맞는 최소 데이터를 심고 지우는 `_real_weight_fixture`를 추가하고, `stop_id == 101`처럼 하드코딩 값에 의존하던 단언을 실제 매칭 여부 확인으로 바꿨습니다 |

### 검증

로컬 Postgres에 실제 배치(`python -m app.batch.run_batch`)를 돌린 뒤, 실제 서버(`uvicorn`)를 띄워 답십리→여의도 좌표로 `/api/v1/routes/search`를 호출: `station_id=158`(배치가 실제로 부여한 ID), `direction="상선"`(실제 계산값), `stop_sequence=13`(실제 배치 데이터), `congestion_score=0.5751`처럼 하드코딩이 아닌 실제 값이 응답에 나오는 것을 확인했습니다. 이후 DB를 깨끗한 시드 상태로 리셋하고 `pytest` 전체 140/140 통과 확인(기존 124개 + 이번에 추가한 16개).
