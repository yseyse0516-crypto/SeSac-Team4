# 텅텅 (TangTang)

재차인원(net onboard) 기반 서울 통근 혼잡회피 서비스. 표시되는 혼잡도는 "하차 전" 상태라, 실제로는 대량 하차 직후 훨씬 여유로운 경우가 많다는 데이터 기반 인사이트에서 출발했다.

## 시작하기 전에

반드시 **[`CLAUDE.md`](./CLAUDE.md)** 를 먼저 읽으세요. 팀 역할, 외부 API 호출 규칙, 개인정보 원칙, 그리고 **아직 미확정인 두 가지(DB 종류 MySQL vs PostgreSQL, route_request/route_candidate 테이블의 개인정보 원칙 충돌)** 가 정의되어 있습니다.

기획 명세서 원문: [`docs/spec/4조_1차MVP_기획명세서2026_08_18.pdf`](./docs/spec) · 구성도(파이프라인·네트워크·ERD): [`docs/architecture/`](./docs/architecture)

## 기술 스택

| 영역 | 기술 | 비고 |
|---|---|---|
| Frontend | React (Vite) | Next.js 미사용 |
| Backend | FastAPI (Python) | 요청 처리 서버 + 오프라인 배치(월 1회) 분리 |
| DB | ⚠️ MySQL 8 (과제 공통 지침) — 명세서 인프라 제안은 PostgreSQL. 팀 확정 후 갱신 | ORM 미사용, 원시 SQL |
| 캐시 | Redis | ODsay 응답 캐시, 따릉이 재고 캐시 (로그인 세션 없음) |
| 외부 API | ODsay LAB 경로탐색 API | 요청 1건당 1회 호출 |
| 배포 | AWS (`tangtang-vpc`, `10.0.0.0/16`) → Kubernetes (2차, 연습용) | |

## 팀

| 담당 | 이름 | 역할 |
|---|---|---|
| 백엔드 | 정종우 | API — 경로 요청, ODsay 연동, 스코어링 |
| 백엔드 | 김창영 | API — 경로 요청, ODsay 연동, 스코어링 (정종우와 모듈 분담) |
| 프론트엔드 | 윤상은 | 지도, 경로 UI, 화면 |
| DB·데이터·인프라 | 김재우 | 공공데이터 배치, 가중치 계산, DB 설계, AWS 인프라 |

## 처리 구조

1. 오프라인 배치(월 1회): 서울교통공사·서울시 파일 + 국토교통부 API 4종 → 가중치 저장소(DB)
2. 사용자 요청 시: ODsay 1회 호출 → 가중치 매칭·스코어링 → 분당개선 필터링 → 클라이언트 응답
3. 따릉이 실시간 재고는 별도 저빈도 API로 확인 (오프라인 배치·ODsay 예산과 무관)

## 실행 방법

### 0. 사전 준비
- Node.js {버전}, Python {버전}
- MySQL 8 (또는 팀 확정 시 PostgreSQL), Redis (로컬 설치 또는 Docker Compose)
- ODsay LAB API 키 (사전 발급 필요)

```bash
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
```

### 1. DB / Redis
```bash
docker compose up -d db redis
```

### 2. Backend (요청 처리 서버)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. 오프라인 배치 (최초 1회 수동 실행 — 가중치 저장소를 채워야 API가 정상 동작합니다)
```bash
cd backend
python -m app.batch.run_monthly_batch
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

## 필수 환경변수

| 변수명 | 설명 |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | DB 접속 정보 (MySQL/PostgreSQL 확정 후 드라이버 맞춰 설정) |
| `REDIS_HOST` / `REDIS_PORT` | Redis 접속 정보 |
| `ODSAY_API_KEY` | ODsay LAB 경로탐색 API 키 |
| `SERVER_VERSION` / `SERVER_NAME` / `SERVER_IP` | 화면 하단 버전 배너 표시용 |

## 배포 정보

| 구분 | 값 |
|---|---|
| VPC | `tangtang-vpc`, `10.0.0.0/16` (2 AZ × Public/Front(예약)/API/DB 4계층) |
| 배포 환경 | AWS ({EC2 / ECS 등 — 확정 후 기입}) |
| URL | {배포 URL} |
| 2차(연습) | Kubernetes |

## 개인정보 원칙

사용자의 위치 이력·식별정보는 저장하지 않으며, 요청 처리 목적으로만 일시적으로 사용합니다. ERD의 `route_request`/`route_candidate` 테이블은 이 원칙과 충돌 가능성이 있어 팀 합의 전까지 보류합니다. 자세한 내용은 CLAUDE.md §4, §9 참고.
