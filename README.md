# SeSac-Team4
# {PROJECT_NAME}

{한 줄 소개, 예: OO 예약/관리 서비스}

바이브코딩(AI 코드 생성 도구)으로 팀원별 모듈을 나눠 개발하는 팀 프로젝트입니다. AWS에 1차 배포 후, 동일 앱으로 쿠버네티스 배포 연습을 진행할 예정입니다.

## 시작하기 전에

반드시 **[`CLAUDE.md`](./CLAUDE.md)** 를 먼저 읽으세요. 팀 모듈 소유권, Git 협업 규칙, 코딩 컨벤션이 정의되어 있습니다.

## 기술 스택

| 영역 | 기술 | 비고 |
|---|---|---|
| Frontend | React (Vite) | Next.js 미사용 |
| Backend | FastAPI (Python) | |
| DB | MySQL 8 | ORM 미사용, 원시 SQL 사용 |
| 세션/캐시 | Redis | |
| 배포 | AWS (1차) → Kubernetes (2차, 연습용) | |

## 팀

| 담당 | 이름 | 모듈 |
|---|---|---|
| A | {이름} | {담당 화면/기능} |
| B | {이름} | {담당 화면/기능} |
| C | {이름} | {담당 화면/기능} |

## 실행 방법

### 0. 사전 준비
- Node.js {버전}
- Python {버전}
- MySQL 8, Redis (로컬 설치 또는 아래 Docker Compose 사용)

```bash
# .env 파일 준비 (각 디렉토리의 .env.example 참고)
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
```

### 1. DB / Redis 띄우기 (Docker Compose 사용 시)
```bash
docker compose up -d db redis
```

### 2. Backend 실행
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend 실행
```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:{포트}` 접속. 화면 하단(또는 상단)에 Front version / Server version / 서버 IP / 서버명이 표시되면 정상 동작입니다.

## 필수 환경변수

| 변수명 | 설명 | 예시 |
|---|---|---|
| `DB_HOST` | MySQL 호스트 | `localhost` |
| `DB_PORT` | MySQL 포트 | `3306` |
| `DB_NAME` | 데이터베이스명 | `{db_name}` |
| `DB_USER` / `DB_PASSWORD` | MySQL 계정 정보 | |
| `REDIS_HOST` / `REDIS_PORT` | Redis 접속 정보 | |
| `SERVER_VERSION` | 화면에 표시할 백엔드 버전 | `1.0.0` |
| `SERVER_NAME` | 화면에 표시할 서버명 | `api-01` |
| `SERVER_IP` | 화면에 표시할 서버 IP | `10.0.1.23` |

## 배포 정보

| 구분 | 값 |
|---|---|
| 배포 환경 | AWS ({EC2 / ECS 등}) |
| 서버명 | {server_name} |
| 서버 IP | {server_ip} |
| URL | {배포 URL} |

## 브랜치 / 커밋 규칙

자세한 내용은 [`CLAUDE.md`](./CLAUDE.md) §6 참고.

- 브랜치: `feature/{module}/{task}`, `fix/{module}/{issue}`
- 커밋: `<type>(<module>): <description>` (예: `feat(auth): 로그인 API 추가`)
