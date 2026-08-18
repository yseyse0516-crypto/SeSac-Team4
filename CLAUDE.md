# CLAUDE.md

> 이 파일은 Claude Code(및 이 리포지토리에서 작업하는 모든 Claude 인스턴스)가 **가장 먼저 읽어야 하는 프로젝트 규칙 문서**다.
> 모듈별 세부 규칙은 `.claude/skills/*/SKILL.md` 를 참고하되, 여기 적힌 전역 규칙이 항상 우선한다.
>
> ※ 이 문서는 템플릿입니다. `{ }`로 표시된 부분(프로젝트명, 팀원, 모듈명, 서버 정보 등)은 팀 회의 후 채워 넣으세요.

---

## 1. 프로젝트 개요

**{PROJECT_NAME}** — {한 줄 소개, 예: OO 예약/관리 서비스}

- 바이브코딩(AI 코드 생성 도구)으로 팀원 각자 담당 모듈을 개발하는 협업 프로젝트다.
- 최종 목표: **AWS에 배포**하여 실제 서비스처럼 동작 확인한다.
- 그래서 처음부터 **컨테이너화(Docker)가 쉬운 구조, 환경변수 기반 설정, 무상태(stateless) 서버**를 전제로 설계한다. (자세한 내용은 §10 참고)

디자인/기획 산출물: `docs/spec/` (요약 명세서), `docs/architecture/` (구성도 — 제출물 중 가장 중요한 항목이므로 반드시 최신 상태 유지)

## 2. 기술 스택 (버전/도구 고정 — 임의 변경 금지)

바이브코딩 도구는 지시가 모호하면 매번 다른 방식으로 구현하므로, 아래 항목은 **명확하게 못 박아 프롬프트에도 그대로 포함**시킨다.

| 영역            | 기술             | 반드시 지킬 것                                                                                                                                                              |
| --------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend        | React            | **Vite**로 빌드/개발 서버 구성. **Next.js 사용 금지** (SSR·자체 라우팅 등 불필요한 구조가 생겨 배포/K8s 이관 시 복잡해짐)                                                   |
| Backend         | FastAPI (Python) | 라우터/스키마/서비스/DB 접근 계층 분리 (§7)                                                                                                                                 |
| DB              | **MySQL 8**      | 5.x 문법·인증 방식과 다르므로 버전 8 명시. **ORM 사용 금지** (SQLAlchemy ORM, Prisma 등 X) → `mysql-connector-python` 또는 `PyMySQL` 등으로 **원시 SQL(raw SQL)** 직접 작성 |
| 세션/캐시       | Redis            | 로그인 세션 등에 사용                                                                                                                                                       |
| 배포            | AWS              | EC2/컨테이너 등 — 팀 결정 후 §10에 기록                                                                                                                                     |
| 형상관리        | Git (GitHub)     | 추후 수업에서 클라우드 환경에 바로 `git clone` 하므로 README만 보고 실행 가능해야 함 (§9)                                                                                   |
| IDE             | VSCode           |                                                                                                                                                                             |

> ORM을 안 쓰는 이유: 바이브코딩이 알아서 짜주는 ORM 모델은 팀원마다 스타일이 갈려 충돌이 잦다. **SQL 쿼리는 모듈별 `db/queries.py`(또는 `repository.py`)에 직접 작성**하고, 커넥션 관리(pool)만 공용 코드(`backend/app/core/db.py`)에서 제공한다.

## 3. 팀 구성 및 모듈 소유권 (Ownership Map)

브랜치 충돌을 막기 위해 **디렉토리 경계 = 담당자 경계**로 설계한다. 각자 자신의 모듈 디렉토리 밖의 파일은 원칙적으로 수정하지 않는다 (공용 파일 수정 규칙은 §6 참고).

| 담당            | 이름   | 모듈 코드         | 담당 화면/기능                                                | Frontend 디렉토리                                                                                                   | Backend 디렉토리                                           |
| --------------- | ------ | ----------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **A**           | {이름} | `{module_a}`      | {화면/기능 나열}                                              | `frontend/src/screens/{module-a}`, `.../components/{module-a}`, `.../store/{module-a}`, `.../api/{module-a}`        | `backend/app/modules/{module_a}/*`                         |
| **B**           | {이름} | `{module_b}`      | {화면/기능 나열}                                              | `frontend/src/screens/{module-b}`, ...                                                                              | `backend/app/modules/{module_b}/*`                         |
| **C**           | {이름} | `{module_c}`      | {화면/기능 나열}                                              | `frontend/src/screens/{module-c}`, ...                                                                              | `backend/app/modules/{module_c}/*`                         |
| 공용(합의 필요) | 전원   | `home`, `_shared` | 메인 홈/대시보드, 공용 컴포넌트·네비게이션·버전 표시 배너(§5) | `frontend/src/screens/home`, `frontend/src/components/common`, `frontend/src/navigation`, `frontend/src/api/client` | `backend/app/core`, `backend/app/db`, `backend/app/common` |

메인 홈 화면·버전 표시 UI처럼 여러 모듈이 공유하는 화면은 소유자를 고정하지 않고 **PR 리뷰 시 전원 합의**로 변경한다.

## 4. 디렉토리 구조

```
{repo-name}/
├── CLAUDE.md                      # 이 파일
├── README.md                      # 실행 방법 포함 (§9)
├── .claude/skills/                 # 모듈별 세부 규칙 (§7)
├── docs/
│   ├── spec/                       # 요약 명세서
│   ├── architecture/               # 구성도(아키텍처 다이어그램) — 가장 중요
│   ├── api-contracts/{module}.md   # 모듈별 API 계약
│   └── prompts/                    # 바이브코딩 프롬프트 기록 (§8)
├── frontend/                       # React + Vite
│   └── src/{screens,components,store,api,types,hooks,constants}/
│       └── ({module-a} | {module-b} | {module-c} | home | common) 하위 분리
├── backend/                        # FastAPI
│   └── app/{core,db,common,modules}/
│       └── modules/({module_a} | {module_b} | {module_c})/{routers,schemas,services,queries}
└── .github/workflows/               # CI
```

## 5. 화면에 반드시 표시할 정보 (필수 요구사항)

과제 요구사항: **Front version, Server version, 서버 IP, 서버명**을 화면에서 항상 확인할 수 있어야 한다.

### 구현 방식
1. **Frontend**: 모든 화면 하단(또는 헤더)에 고정 노출되는 공용 컴포넌트 `frontend/src/components/common/BuildInfoBadge.tsx`를 만든다.
   - Front version은 `frontend/package.json`의 `version` 필드(또는 빌드 시 주입되는 git commit hash)를 사용한다.
   - Server version/IP/서버명은 아래 백엔드 API를 호출해 받아온다.
2. **Backend**: `backend/app/core`에 공용 엔드포인트 `GET /api/system/version`을 만들고 아래 값을 반환한다.
   ```json
   { "server_version": "1.0.0", "server_name": "api-01", "server_ip": "10.0.1.23" }
   ```
   - `server_version`: 환경변수(`SERVER_VERSION`) 또는 배포 시 주입.
   - `server_name`, `server_ip`: 환경변수 또는 실행 시점에 조회(`socket.gethostname()`, `socket.gethostbyname()`) — 환경변수 우선, 없으면 런타임 조회로 fallback.
3. 이 배너는 `_shared` 소유 영역이므로 **수정 시 전원 리뷰** 대상이다 (§3, §6).

## 6. Git 협업 규칙

### 브랜치 전략
- `main`: 배포 가능 상태만 유지, 직접 push 금지
- `develop`: 통합 브랜치
- 기능 브랜치: `feature/{module}/{screen-or-task}` 예) `feature/{module-a}/login-screen`
- 수정 브랜치: `fix/{module}/{issue}`

### 커밋 컨벤션 (Conventional Commits)
```
<type>(<module>): <description>

type: feat | fix | refactor | style | docs | test | chore
module: {module-a} | {module-b} | {module-c} | home | shared | infra
```

### 충돌 방지 규칙
1. **자기 모듈 디렉토리 밖은 건드리지 않는다.** 공용 컴포넌트(`components/common`, `navigation`, `core`, `db`)가 필요하면 직접 고치지 말고 이슈로 등록 후 담당 합의.
2. **공용 파일을 고쳐야 하는 경우** (`App.tsx`/`main.tsx` 루트, `navigation/*`, `main.py`, 버전 배너, DB 커넥션 공통 코드) → 반드시 별도 PR로 분리하고 전원 리뷰 필수.
3. SQL 쿼리는 모듈별 `queries.py`에만 작성. 여러 모듈이 같은 테이블을 조회해야 하면 공용 헬퍼로 승격하기 전에 이슈로 논의.
4. API 계약은 코드 작성 전 `docs/api-contracts/{module}.md`에 먼저 정의하고 PR로 리뷰받는다 (프론트/백엔드 담당이 다른 사람일 때 특히 중요).
5. DB 스키마 변경은 `docs/db/schema.sql`에 반영하고 실제 마이그레이션 SQL 파일(`backend/app/migrations/*.sql`)로 별도 관리 (ORM 마이그레이션 도구 미사용이므로 SQL 파일을 직접 버전 관리).

### PR 규칙
- PR 제목에 모듈 태그 포함: `[{module-a}] 로그인 화면 구현`
- 본인 모듈 범위를 벗어난 변경이 diff에 섞여 있으면 반려
- 머지 전 최소 1인 리뷰 (공용 파일 변경 시 전원 리뷰)

## 7. 코딩 컨벤션 요약

- **Frontend**: 함수형 컴포넌트 + TypeScript, 화면 컴포넌트명은 `XxxPage` 또는 `XxxScreen`, Vite 프로젝트 구조 유지, 절대 px 고정 남발 금지.
- **Backend**: 모듈 = `routers`(엔드포인트) / `schemas`(Pydantic) / `services`(비즈니스 로직) / `queries`(원시 SQL) 4단 구조 고정. 라우터에 비즈니스 로직·SQL 직접 작성 금지.
- **DB 접근**: 커넥션 풀은 `backend/app/core/db.py`에서만 생성, 각 모듈은 이를 가져다 쓴다. SQL 인젝션 방지를 위해 파라미터 바인딩(`%s` 플레이스홀더) 필수, 문자열 포매팅으로 쿼리 조립 금지.
- **네이밍**: 프론트 폴더는 kebab-case, 백엔드 파이썬 모듈은 snake_case.
- **환경변수**: DB 접속정보, Redis 접속정보, `SERVER_VERSION`, `SERVER_NAME` 등은 전부 `.env`로 분리하고 `.env.example`을 커밋한다 (AWS 배포 시 값만 바꾸면 되도록).

## 8. 바이브코딩 프롬프트 관리 (제출물)

수업/과제 제출용으로 **프롬프트 자체를 산출물로 관리**한다.

- `docs/prompts/00-overall-structure.md` — 프로젝트 전체 구조(디렉토리, 기술스택, 화면 목록 등)를 잡을 때 사용한 프롬프트. 수정할 때마다 **파일을 덮어쓰지 말고 같은 파일 안에 최신 버전만 남기되, 무엇을 바꿨는지 파일 하단에 변경 이력으로 남긴다.**
- `docs/prompts/{module}-structure.md` — 각자 담당 모듈 구조를 잡을 때 사용한 프롬프트 (담당자별로 분리, 본인 파일만 수정).
- 제출 시점에는 각 파일의 **최종 버전 프롬프트**만 제출하면 되도록 최상단에 "최종 프롬프트" 섹션을 두고, 그 아래 이전 시도들을 참고용으로 남긴다.

## 9. README.md 작성 규칙

`README.md`는 **클라우드 환경에서 `git clone` 직후 바로 실행 가능하도록** 작성한다. 최소 아래 내용을 포함한다.

- 프로젝트 한 줄 소개, 기술 스택(§2)
- 팀 구성 및 모듈 담당 (§3 요약)
- 로컬 실행 방법: 프론트(`npm install` → `npm run dev`), 백엔드(가상환경, `pip install -r requirements.txt`, 실행 명령), MySQL 8 / Redis 준비 방법(Docker Compose 권장)
- `.env.example` 안내 및 필수 환경변수 목록
- 배포 정보(§10)로 이동하는 링크
- `docs/CLAUDE.md`를 먼저 읽으라는 안내 문구

## 10. 배포 환경

| 구분    | 값                                                                             |
| ------- | ------------------------------------------------------------------------------ |
| 배포    | AWS ({EC2 / ECS / 기타 — 확정 후 기입})                                        |
| 서버명  | {server_name}                                                                  |
| 서버 IP | {server_ip} (§5 배너와 동일 값 사용)                                           |

컨테이너화 및 무상태 설계를 아래 원칙으로 유지한다 (운영 편의 및 향후 서버 교체/확장 대비):
1. 프론트/백엔드 모두 **Dockerfile**로 컨테이너화한다.
2. 서버는 로컬 파일/메모리에 상태를 저장하지 않는다(무상태). 세션은 반드시 Redis로.
3. 설정값(DB 접속정보, 포트, 버전 등)은 전부 환경변수로 주입한다 (하드코딩 금지) — AWS Systems Manager Parameter Store / Secrets Manager 등으로 그대로 옮길 수 있게.

## 11. 아직 정해지지 않은 것 (팀 확인 필요)

- 프로젝트 주제/이름 확정
- 팀원별 역할(§3) 확정
- AWS 배포 방식(EC2 단일 서버 vs ECS/컨테이너 서비스) 확정
- 요약 명세서의 구성도(아키텍처 다이어그램) 초안 작성 (가장 중요한 제출 항목)

## 12. Claude에게 주는 전역 지시사항

- 항상 **§3 소유권 표에 명시된 디렉토리 범위 안에서만** 파일을 생성/수정한다. 범위를 벗어나야 하는 작업이면 먼저 사용자에게 알린다.
- DB 접근 코드를 작성할 때 **ORM을 사용하지 않는다.** SQLAlchemy ORM, Prisma 등을 제안하거나 자동 생성하지 말 것. 원시 SQL + 파라미터 바인딩만 사용한다.
- React 프로젝트 세팅 시 **Next.js를 사용하지 않는다.** 반드시 Vite 기반으로 구성한다.
- MySQL 관련 코드/설정을 작성할 때 **버전 8 기준** 문법·인증 플러그인(`caching_sha2_password` 등)을 사용한다.
- 새 화면/API를 만들 때는 먼저 `docs/api-contracts/{module}.md`에 계약이 있는지 확인하고, 없으면 만들어 사용자 확인을 받은 뒤 구현한다.
- 화면 작업 시 §5의 버전/서버 정보 배너가 항상 노출되는지 확인한다 (레이아웃 컴포넌트에서 제거되지 않도록 주의).
- 커밋 메시지는 §6 컨벤션을 따른다.
