# CLAUDE.md

> 이 파일은 Claude Code(및 이 리포지토리에서 작업하는 모든 Claude 인스턴스)가 **가장 먼저 읽어야 하는 프로젝트 규칙 문서**다.
> 모듈별 세부 규칙은 `.claude/skills/*/SKILL.md` 를 참고하되, 여기 적힌 전역 규칙이 항상 우선한다.
>
> ⚠️ 이 버전은 4조 최종 기획명세서(`4조_1차MVP_기획명세서2026_08_18.pdf`, 12p) 기준으로 갱신했다. 이전 8p 버전(김재우 작성 초안)과 다른 점은 §2, §5, §9, §10에 표시했다.
> 2026-08-19: 백엔드 개발 핸드오프 문서(`텅텅_백엔드개발핸드오프-2026_08_19생성.pdf`)와 정종우 확인을 거쳐 §2의 DB 스택을 **PostgreSQL + SQLAlchemy(ORM 사용)**로 확정하고, nginx를 리버스 프록시로 추가했다.

---

## 1. 프로젝트 개요

**텅텅 (TangTang)** — 재차인원(net onboard) 기반 서울 통근 혼잡회피 서비스

- 핵심 인사이트: 지하철·버스 앱이 보여주는 혼잡도는 "하차 전" 상태다. 대량 하차 직후 실제로 남아있는 인원(재차인원)을 계산하면, 표시된 혼잡도보다 사용자의 실제 경험에 가까운 신호를 얻을 수 있다.
- 서비스 목적: 사용자가 출발지·도착지·기준시간을 입력하면, 지하철·버스·따릉이를 통합한 경로 후보 중 재차인원·혼잡도 기반으로 실제로 덜 혼잡한 경로를 추천한다.
- 처리 구조는 두 축이다. ① 월 1회 오프라인 배치로 공공데이터를 가공해 역·정류장·대여소 단위 가중치를 미리 계산해두고, ② 사용자 요청 시에는 ODsay API 1회 호출 + 로컬 스코어링만으로 응답한다. (자세한 내용은 §7)
- 기획 원문(최종): `docs/spec/4조_1차MVP_기획명세서2026_08_18.pdf`. 코드 작업 중 요구사항이 모호하면 항상 이 문서를 먼저 확인한다.

## 2. 기술 스택 (버전/도구 고정 — 임의 변경 금지)

| 영역 | 기술 | 반드시 지킬 것 |
|---|---|---|
| Frontend | React | **Vite**로 빌드/개발 서버 구성. **Next.js 사용 금지** |
| Backend | FastAPI (Python) | 라우터/스키마/서비스/DB 접근 계층 분리 (§8) + 오프라인 배치 모듈 분리 |
| DB | **PostgreSQL** (확정) | **ORM 사용 금지** — `psycopg`(v3) + 원시 SQL. PG 전용 문법(`JSONB`/`ARRAY`/`RETURNING` 등)도 가급적 피하고 표준 SQL로 작성 |
| 캐시 | Redis | ODsay 응답 캐시(동일 출발/도착/시간대 재요청 시 TTL 캐시), 따릉이 실시간 재고 캐시, 일일 호출 카운터 — **로그인 세션 용도는 없음** (§4 참고) |
| 리버스 프록시 | nginx | FastAPI 앞단 리버스 프록시로 사용 (프론트 정적 서빙 여부는 배포 시 확인) |
| 배포(1차) | AWS | VPC `tangtang-vpc`, `10.0.0.0/16` — §10 참고 |
| 배포(2차, 연습) | Kubernetes | 1차 배포 이후 동일 앱으로 클러스터 배포 연습 예정 |
| 형상관리 | Git (GitHub) | README만 보고 클라우드에서 바로 실행 가능해야 함 (§11) |

> **DB 확정 (2026-08-19, 최종):** DB는 **PostgreSQL**로 확정. ORM은 최종적으로 **사용하지 않는 것으로 확정** — `psycopg`(v3) + 원시 SQL + 파라미터 바인딩. (같은 날 한때 "SQLAlchemy ORM 사용"으로 갔다가, 김창영(백엔드 B)과 조율 후 다시 원시 SQL로 확정됐다.) 커넥션 관리는 공용 코드(`backend/app/core/db.py`)에서 커넥션 풀로 제공한다.

## 3. 외부 API·데이터 연동 규칙 (중요)

이 서비스는 외부 API 호출 예산이 명세서에서 이미 확정돼 있다. **코드 작성 시 아래 규칙을 절대 위반하지 않는다.**

| API/데이터 | 호출 시점 | 규칙 |
|---|---|---|
| ODsay LAB 경로탐색 API | 사용자 요청 시 | **요청 1건당 1회만 호출**. 무료 한도 1,000건/일 내에서 운영 (N-03). 동일 조건 재요청은 Redis 캐시로 흡수해 호출 자체를 줄인다 |
| 국토교통부 API 4종 (재차인원·혼잡도·최빈환승정류장·최빈경로) | 오프라인 배치(월 1회) | 실시간 요청 경로에서 절대 호출하지 않는다. 배치 모듈에서만 사용 |
| 서울교통공사 파일(시간표·혼잡도) | 오프라인 배치(월 1회) | 파일 기반, API 키 불필요 |
| 서울시 파일(버스 승하차·정류장마스터·따릉이 대여소) | 오프라인 배치(월 1회) | 파일 기반, API 키 불필요 |
| 따릉이 실시간 대여소 재고 API | 사용자 요청 시, 저빈도 | ODsay 호출 예산과 무관하게 별도 관리. 자전거 후보를 보여주기 전에만 확인 |

## 4. 개인정보·데이터 원칙 (전역 지시사항 — 반드시 준수)

- **사용자의 위치 이력·식별정보를 저장하지 않는다 (N-04).** 요청 처리 목적으로만 일시적으로 사용하고, DB에 영속 저장하지 않는다.
- 회원가입/로그인 기능은 1차 MVP 범위에 없다. Claude는 요청받지 않은 회원 인증 기능을 임의로 추가하지 않는다.
- 사용 통계가 필요해지면 좌표를 일반화(구/동 단위)하거나 집계값만 저장하는 방식으로, 개별 요청을 재식별할 수 없게 설계한다.
- **`route_request`/`route_candidate` 저장 방식 확정 (2026-08-19):** 4조 최종 ERD(§9)의 이 두 테이블은 원래 좌표 원본을 저장해 N-04와 충돌 소지가 있었으나, 팀 합의로 **좌표를 소수점 3자리로 절삭(약 100m 격자로 일반화)해 저장**하고 사용자 식별자와 결합하지 않는 방식으로 해결했다. 이 조건 하에 두 테이블을 실제로 구현해도 된다. 상세 내용은 `backend.md` §8 참고.

## 5. 팀 구성 및 역할 (4인)

디렉토리 경계 = 담당자 경계로 설계한다. 이 서비스는 "오프라인 배치"와 "실시간 API 서버"가 완전히 다른 성격의 작업이라, 데이터/배치를 백엔드 API와 분리된 역할로 둔다. (4조 최종 명세서 기준 실제 팀 구조 — 백엔드 2인 + 프론트 1인 + DB·데이터·인프라 통합 1인)

| 담당 | 이름 | 역할 | 주요 담당 | 디렉토리 |
|---|---|---|---|---|
| 백엔드 A | 정종우 | 백엔드 (API) | 경로 요청 API, ODsay 연동, 가중치 매칭·스코어링, 분당개선 필터링 | `backend/app/modules/routing/*` |
| 백엔드 B | 김창영 | 백엔드 (API) | 경로 요청 API, ODsay 연동, 가중치 매칭·스코어링, 분당개선 필터링 (정종우와 모듈 내 기능 분담) | `backend/app/modules/routing/*` |
| 프론트엔드 | 윤상은 | 프론트엔드 | 출발지·도착지·기준시간 입력 화면, 추천 경로 목록, 지도 위 경로 시각화 | `frontend/src/screens/routing`, `.../components/routing` |
| DB·데이터·인프라 | 김재우 | DB 설계·데이터가공·인프라 (통합) | 서울교통공사·서울시 파일 파싱, 국토교통부 API 4종 연동, 재차인원/혼잡도/정차순번/대여소 거리 계산, 월 1회 배치 실행, ERD/DB 운영, AWS 인프라, 배치 스케줄링(cron), 추후 쿠버네티스 연습 | `backend/app/batch/*`, `backend/app/core`, 배포 스크립트 |

> 백엔드 A/B는 같은 `routing` 모듈을 나눠 작업하므로, 라우터 단위(예: `/api/routes/search` vs `/api/routes/recommend`)나 계층 단위(services vs queries)로 사전에 경계를 정해 머지 충돌을 줄인다. 메인 화면·버전 배너 등 공용 영역은 소유자를 고정하지 않고 전원 합의로 변경한다.

## 6. 디렉토리 구조

```
tangtang/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── spec/                       # 기획 명세서 원문
│   ├── architecture/                # 구성도(파이프라인·네트워크) — 가장 중요
│   ├── api-contracts/{module}.md
│   └── prompts/
├── frontend/                        # React + Vite
│   └── src/{screens,components,store,api,types,hooks,constants}/routing, home, common
├── backend/
│   └── app/
│       ├── core/                    # DB 커넥션 풀, 공용 설정
│       ├── modules/routing/         # routers / schemas / services / queries — 요청 처리 서버
│       └── batch/                   # 오프라인 배치 파이프라인 (월 1회 실행, routing과 분리)
└── .github/workflows/
```

## 7. 처리 파이프라인 (핵심 아키텍처)

기획 명세서 7절의 파이프라인을 그대로 구현 기준으로 삼는다. 상세 다이어그램은 `docs/architecture/`에 있다.

1. **오프라인 배치 파이프라인 (월 1회)**: 서울교통공사 파일, 서울시 파일, 국토교통부 API 4종을 가공해 역·정류장·대여소 단위 가중치를 계산한다.
2. **가중치 저장소**: 재차인원 / %혼잡도 / 정차순번 / 대여소-거점 거리를 DB 테이블로 저장한다(§9 ERD 참고). 월 1회만 갱신되는 읽기 전용 성격을 유지해, 정적 파일 배포 방식과 동일한 이점(서버 증설 시 별도 동기화 불필요, N-06)을 DB로도 확보한다.
3. **요청 처리 서버 (FastAPI)**: 사용자 요청 시 ODsay를 1회 호출해 후보 경로를 만들고, 가중치 저장소와 매칭·스코어링한 뒤 분당개선 지표로 필터링한다.
4. **클라이언트 (React)**: 추천 경로 목록과 지도 위 경로 시각화를 보여준다.

## 8. 코딩 컨벤션 요약

- **Frontend**: 함수형 컴포넌트 + TypeScript, 화면 컴포넌트명은 `XxxPage`, Vite 구조 유지.
- **Backend**: `routers`/`schemas`/`services`/`queries` 4단 구조. 배치 코드(`backend/app/batch/`)는 라우터와 완전히 분리하고, 배치 결과만 API가 조회한다.
- **DB 접근**: 커넥션 풀은 `backend/app/core/db.py`에서만 생성(psycopg v3). SQL 쿼리는 모듈별 `queries.py`에 직접 작성, 파라미터 바인딩 필수(SQL 인젝션 방지).
- **네이밍**: 프론트 폴더는 kebab-case, 백엔드 파이썬 모듈은 snake_case.
- **환경변수**: DB/Redis 접속정보, `ODSAY_API_KEY`, `SERVER_VERSION`, `SERVER_NAME` 등은 `.env`로 분리, `.env.example` 커밋.

## 9. 데이터베이스 (ERD 요약 — 4조 최종 명세서 §8 기준)

전체 ERD는 `docs/architecture/`에 있다. 이전 초안보다 테이블이 세분화됐다 — 지하철(station/station_weight)과 버스(bus_stop/bus_weight)를 별도 테이블로 분리한 것이 핵심 변경점이다.

| 테이블 | 역할 | 주요 제약 |
|---|---|---|
| `station` | 지하철역 마스터 | |
| `bus_stop` | 버스 정류장 마스터 | `stop_std_id` UNIQUE |
| `rental_dock` | 따릉이 대여소 마스터 | |
| `batch_run` | 배치 실행 로그 (데이터 최신성 모니터링, N-05) | |
| `station_weight` | 지하철 역 단위 가중치(재차인원·혼잡도 등) | UNIQUE(`station_id`, `batch_id`, `time_slot`, `dow`) |
| `bus_weight` | 버스 정류장·노선 단위 가중치 (지하철과 분리 — 노선별로 값이 다르기 때문) | UNIQUE(`stop_id`, `route_id`, `batch_id`, `time_slot`, `dow`) |
| `dock_hub_distance` | 대여소-교통거점 거리 | UNIQUE(`dock_id`, `hub_type`, `hub_id`, `batch_id`) |
| `route_request` | 사용자 요청 로그(좌표는 소수점 3자리 절삭 저장, 요청시각) | §4 참고 — 구현 확정 |
| `route_candidate` | 추천 결과·스코어링 로그, `request_id`에 INDEX | §4 참고 — 구현 확정 |

좌표를 소수점 3자리로 절삭해 일반화하고 사용자 식별자와 결합하지 않는 조건으로 두 테이블 모두 실제 구현한다 (§4 참고).

## 10. 배포 환경 (4조 최종 명세서 §7.2 기준 — AWS 제안)

| 구분 | 값 |
|---|---|
| VPC | `tangtang-vpc`, CIDR `10.0.0.0/16` |
| 서브넷 구조 | 2 AZ × 4계층 (Public / Front-예약 / API / DB), 각 AZ에 `/24` 8개: `10.0.0.0/24`, `10.0.1.0/24`, `10.0.10.0/24`, `10.0.11.0/24`, `10.0.20.0/24`, `10.0.21.0/24`, `10.0.30.0/24`, `10.0.31.0/24` |
| 보안그룹 원칙 | IP 대역이 아닌 **보안그룹 ID 참조**로 계층 간 접근 제한 (예: DB 보안그룹은 API 보안그룹에서만 인바운드 허용) |
| DB 포트 | `5432/tcp` (PostgreSQL, 확정) |
| 2차(연습) | Kubernetes — 1차 AWS 배포 이후 동일 앱으로 클러스터 배포 연습 |

원칙: Dockerfile로 컨테이너화, 서버는 무상태로 설계(개인정보 미저장 원칙과도 부합), 설정값은 전부 환경변수로 주입. 실제 인스턴스는 AZ 하나에만 배치하고 나머지 AZ 서브넷은 예약해두어, 추후 ALB+Auto Scaling 추가 시 구조 변경 없이 확장 가능하게 한다.

## 11. README.md 작성 규칙

클라우드에서 `git clone` 직후 실행 가능하도록 작성한다. 기술 스택, 팀 구성, 실행 방법(프론트/백엔드/DB/배치), 필수 환경변수(`ODSAY_API_KEY` 포함), 배포 정보를 포함한다.

## 12. 화면에 반드시 표시할 정보

Front version, Server version, 서버명, 서버 IP, 클라이언트 IP, X-Forwarded-For 6개를 화면 하단 공용 배너로 항상 노출한다. 백엔드 `GET /api/v1/system/meta` 엔드포인트에서 값을 받아온다 (김창영 담당, `backend.md` §5/§8 참고).

## 13. Claude에게 주는 전역 지시사항

- 항상 §5 역할 표에 명시된 디렉토리 범위 안에서만 파일을 생성/수정한다.
- **§4의 개인정보 원칙을 최우선으로 지킨다.** route_request/route_candidate 테이블은 좌표를 소수점 3자리로 
절삭 저장하는 방식으로 팀 합의 완료. 구현해도 된다.
(N-04 대응: 약 100m 격자 → 개인 재식별 불가, 사용자 식별자 없음)
- **§3의 외부 API 호출 규칙을 절대 위반하지 않는다.** ODsay는 요청당 1회만, 국토교통부 API·서울교통공사/서울시 파일은 오프라인 배치에서만 사용한다.
- DB는 PostgreSQL을 사용하되 ORM은 쓰지 않는다. `psycopg`(v3) + 원시 SQL + 파라미터 바인딩 (2026-08-19 최종 확정, §2 참고).
- React 세팅 시 Next.js를 사용하지 않는다.
- 회원가입/로그인 등 명세서에 없는 기능을 임의로 추가하지 않는다. 필요하다고 판단되면 먼저 사용자에게 확인한다.
- 새 화면/API를 만들 때는 `docs/api-contracts/{module}.md`에 계약이 있는지 먼저 확인한다.


---

## [B 작업 컨텍스트] 2026-08-19 기준 — Claude Code 시작 시 이 섹션부터 읽을 것

> 이 섹션은 백엔드 B(김창영)가 Claude Code에서 작업을 이어가기 위한 컨텍스트다.
> 위 섹션들(§1~§13)이 프로젝트 전체 규칙이고, 이 섹션은 현재 개발 상태와 B의 작업 범위를 추가로 정의한다.

---

### 현재 상태

- 마감: **2026-08-20(목) 16:00 코드 동결**
- 레포: `SeSac-Team4` private, `zer0` 브랜치에서 작업
- 백엔드 A(정종우)와 분담 확정 — 라우터 단위 분리, 공용 파일은 B가 먼저 올림
- 레포에는 현재 `CLAUDE.md`, `README.md`만 있음

---

### B 담당 파일 (이것만 만든다)

```
backend/
├── app/
│   ├── main.py                   공용 — B가 먼저 만들고 이후 건드리지 않음
│   ├── core/
│   │   ├── db.py                 공용 — psycopg 커넥션 풀
│   │   └── redis.py              공용 — Redis 클라이언트
│   ├── routers/
│   │   ├── system.py             GET /api/v1/system/meta, GET /health, GET /admin/batch/latest
│   │   ├── result.py             GET /api/v1/routes/{request_id}
│   │   ├── bike.py               GET /api/v1/bike/docks (따릉이 F-04)
│   │   └── coupon.py             POST /api/v1/coupons/claim (조건부)
│   ├── services/
│   │   └── candidate_log.py      save_candidates(), save_request() — A가 호출하는 함수
│   └── schemas/
│       ├── result.py
│       ├── bike.py
│       └── system.py
└── sql/
    ├── 01_schema.sql             PostgreSQL DDL
    └── 02_seed.sql               개발용 더미 데이터
docker-compose.yml                PostgreSQL 16 + Redis 7
backend/.env.example
```

### A 담당 파일 (절대 건드리지 않는다)

```
backend/app/routers/search.py
backend/app/services/odsay.py
backend/app/services/scoring.py
```

---

### 확정된 기술 결정사항

| 항목 | 결정값 | 이유 |
|---|---|---|
| DB | PostgreSQL 16 | 핸드오프 확정 |
| ORM | **금지** | CLAUDE.md §2 — psycopg(v3) + raw SQL |
| PG 전용 문법 | **사용 금지** | JSONB/ARRAY/RETURNING 쓰면 MySQL 되돌릴 때 재작성 필요 |
| 정규화 방향 | **0에 가까울수록 쾌적** | A와 반드시 통일 — 어긋나면 추천이 반대로 나옴 |
| N-04 처리 | 좌표 소수점 3자리 절삭 저장 | 약 100m 격자 → 개인 재식별 불가 |
| ORM 대신 | psycopg(v3) 직접 사용 | `pip install psycopg[binary]` |
| include_router 순서 | A 먼저, B 나중 | 충돌 시 해결 즉시 가능 |

---

### 스코어링 공식 (A가 구현, B는 참고만)

Q1~Q4는 아래 값으로 확정. 전부 상수로 분리돼 있어 변경 비용 없음.

```python
# Q1: 점수 통합 (0에 가까울수록 쾌적)
subway_score = min(congestion_pct / 150, 1.0)
bus_score    = min(net_onboard / 50, 1.0)
# 경로 점수 = 구간별 소요시간 가중평균

# Q2: baseline = ODsay 후보 중 total_time_min 최솟값

# Q3: 정차순번 감산 계수 (필터 아님)
if stop_sequence <= 3:
    score *= 0.7

# Q4: 매칭 반경
# 지하철 100m, 버스 50m
# 실패 시 matched=False, 중립값 0.5 사용
```

---

### A와의 접점 — save_candidates

B가 제공하고 A가 `/routes/search` 마지막 줄에서 호출하는 함수.
**내일(8/20) 오전 통합 시점에 연결.**

```python
# backend/app/services/candidate_log.py

def save_request(origin_lat, origin_lng, dest_lat, dest_lng) -> int:
    """route_request INSERT → request_id 반환. 좌표는 소수점 3자리 절삭."""

def save_candidates(request_id: int, candidates: list[dict]) -> None:
    """route_candidate 일괄 INSERT.
    candidates 각 항목 필수 키:
      path_type, total_time_min, congestion_score,
      minute_improvement_ratio, is_recommended
    """
```

---

### API 명세 (B 담당)

#### GET /api/v1/system/meta
과제 필수 표시 6개. Nginx의 X-Forwarded-For를 읽어야 하므로 `request.headers` 사용.

```json
{
  "front_version": "0.1.0",
  "server_version": "0.1.0",
  "server_name": "tangtang-api01",
  "server_ip": "10.0.20.11",
  "client_ip": "1.2.3.4",
  "x_forwarded_for": "1.2.3.4, 10.0.0.5"
}
```

#### GET /api/v1/health
DB + Redis 핑 + 최신 batch_run 상태 포함.

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "latest_batch": { "run_month": "2026-08", "status": "success", "finished_at": "..." }
}
```

#### GET /api/v1/routes/{request_id}
route_request + route_candidate 조회. A의 `/search`가 저장한 데이터를 읽는다.

#### GET /api/v1/bike/docks
따릉이 F-04. hub_type=STATION|BUS_STOP, hub_id, max_distance(m) 쿼리파라미터.
dock_hub_distance 테이블 조회. 실시간 재고(F-05)는 `stock: null` 스텁.

```json
{
  "docks": [
    { "dock_id": 1, "dock_name": "강남역 2번출구", "lat": 37.498, "lng": 127.027,
      "distance_m": 120, "stock": null }
  ]
}
```

#### POST /api/v1/coupons/claim (조건부 — 통합 끝나고 여유 있으면)
X-Client-Token 헤더로 식별(브라우저가 생성한 UUID). Redis INCR 원자적 순번.

```python
# Redis 키 구조
"coupon:count"          # INCR 원자 카운터
"coupon:issued:{token}" # SET NX 중복 차단
```

---

### 스코프 결정사항

| 항목 | 결정 |
|---|---|
| 게시판 CRUD | **제외** — 서비스 서사와 무관, 프론트 부담 증가 |
| 따릉이 대여소 통합 (F-04) | **필수 포함** — dock_hub_distance 조회, 외부 API 없음 |
| 따릉이 실시간 재고 (F-05) | **스텁** — API 미확정, 명세서 §10 1차 범위 밖 |
| 비교 기능 | **A의 /search 안에 포함** — 별도 API 불필요 |
| 쿠폰 선착순 | **조건부** — 통합 완료 후 여유 있으면 B가 진행 |

---

### 오늘(8/19) B 작업 순서

지금 당장 시작 가능한 것 (A 답변 불필요):

1. `sql/01_schema.sql` — ERD §8 기준
2. `sql/02_seed.sql` — 강남·신도림·성수·신답 등 5~6역 더미
3. `docker-compose.yml`
4. `backend/.env.example`
5. `backend/app/core/db.py`
6. `backend/app/core/redis.py`
7. `backend/app/main.py`
8. `GET /api/v1/health`
9. `GET /api/v1/system/meta`
10. `GET /api/v1/routes/{request_id}` (골격만, save_candidates 붙기 전)
11. `GET /api/v1/bike/docks`
12. `backend/app/services/candidate_log.py` — 시그니처 + 구현

A 답변 온 후 확인:
- 공용 파일(main.py, core/*) 중복 여부
- ODsay 응답에 정류장 좌표 포함 여부
- segments 좌표 포함 형식 최종 확인

---

### 내일(8/20) 일정

| 시간 | 작업 |
|---|---|
| 오전 | A와 통합 준비 — save_candidates 연결, 실제 가중치 데이터 확인 |
| 12시 | **A·B 통합 — /routes/search ↔ save_candidates 연결** |
| 오후 | 프론트 연동, 에러 처리, 시연 좌표 튜닝 |
| **16시** | **코드 동결** |
| 이후 | 배포, README 갱신, 발표 데모 리허설 |

---

### 시연 기본 좌표 (발표용)

명세서 §4에서 차이가 검증된 구간:
- 출발: 래미안위브아파트 `lat=37.5012, lng=127.0396`
- 도착: 독산사거리 `lat=37.4784, lng=126.8874`
- 출발시간: `2026-08-21T08:30:00+09:00`

이 좌표로 테스트하면 최속 경로(68분)와 추천 경로(74분)가 확실히 갈라짐.
