-- TangTang PostgreSQL 16 DDL
-- ERD 기준: CLAUDE.md §9 (4조 최종 명세서 §8)
-- ORM 미사용 원칙에 따라 원시 SQL로 직접 관리한다 (backend/app/core/db.py 커넥션 풀에서 실행).

-- ============================================================
-- 마스터 테이블
-- ============================================================

CREATE TABLE station (
    station_id   SERIAL PRIMARY KEY,
    station_name VARCHAR(100) NOT NULL,
    line_name    VARCHAR(50),
    -- 역번호(재우님 추가, 2026-08-20): 반경형 노선(1,3~8호선)은 역번호 증감으로 상행/하행을
    -- 판정할 수 있어 방향 계산에 필요하다. 2호선(순환선)은 이 규칙이 안 통해 통계적 추정 대상.
    -- NULL 허용: 배치 미반영 행, 방향 판정에 역번호가 필요 없는 노선.
    station_no   VARCHAR(10),
    lat          NUMERIC(9,6) NOT NULL,
    lng          NUMERIC(9,6) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (line_name, station_no)
);

CREATE TABLE bus_stop (
    stop_id      SERIAL PRIMARY KEY,
    stop_std_id  VARCHAR(20) NOT NULL UNIQUE,
    stop_name    VARCHAR(100) NOT NULL,
    lat          NUMERIC(9,6) NOT NULL,
    lng          NUMERIC(9,6) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE rental_dock (
    dock_id      SERIAL PRIMARY KEY,
    -- 행안부 자전거 API의 rntstnId를 저장한다. 서울시 원본 파일의 "대여소 번호"와는
    -- 다른 체계라 매칭 안 됨 — 배치가 아직 안 채운 행을 위해 NULL 허용.
    dock_std_id  VARCHAR(20) UNIQUE,
    dock_name    VARCHAR(100) NOT NULL,
    lat          NUMERIC(9,6) NOT NULL,
    lng          NUMERIC(9,6) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- 배치 실행 로그 (N-05: 데이터 최신성 모니터링용)
CREATE TABLE batch_run (
    batch_id     SERIAL PRIMARY KEY,
    run_month    VARCHAR(7) NOT NULL,  -- 'YYYY-MM'
    status       VARCHAR(20) NOT NULL, -- 'running' | 'success' | 'failed'
    started_at   TIMESTAMP NOT NULL,
    finished_at  TIMESTAMP,
    note         VARCHAR(255)
);

-- ============================================================
-- 가중치 테이블 (월 1회 배치 결과, 읽기 전용)
-- ============================================================

CREATE TABLE station_weight (
    station_weight_id SERIAL PRIMARY KEY,
    station_id        INT NOT NULL REFERENCES station(station_id),
    batch_id          INT NOT NULL REFERENCES batch_run(batch_id),
    -- 방향(재우님 추가, 2026-08-20): 같은 역도 상선/하선(2호선은 내선/외선)마다 혼잡도가
    -- 크게 달라서 UNIQUE에도 포함한다. 판정 규칙: 반경형 노선은 station.station_no 증감,
    -- 2호선은 통계적 추정.
    direction         VARCHAR(10) CHECK (direction IN ('상선', '하선', '내선', '외선')),
    time_slot         VARCHAR(20) NOT NULL, -- 예: '08:00-08:30'
    dow               SMALLINT NOT NULL,    -- 0=월 .. 6=일
    net_onboard       NUMERIC(10,2),        -- 재차인원
    congestion_pct    NUMERIC(6,2),         -- %혼잡도 (Q1 subway_score = min(congestion_pct/150, 1.0))
    stop_sequence     SMALLINT,             -- 정차순번 (완만한 가우시안 감쇠 계수, 실제 적용은 services/scoring.py)
    UNIQUE (station_id, batch_id, time_slot, dow, direction)
);

CREATE TABLE bus_weight (
    bus_weight_id  SERIAL PRIMARY KEY,
    stop_id        INT NOT NULL REFERENCES bus_stop(stop_id),
    route_id       VARCHAR(20) NOT NULL, -- 노선 표준ID (예: '260')
    batch_id       INT NOT NULL REFERENCES batch_run(batch_id),
    time_slot      VARCHAR(20) NOT NULL,
    dow            SMALLINT NOT NULL,
    net_onboard    NUMERIC(10,2), -- Q1 bus_score = min(net_onboard/50, 1.0)
    UNIQUE (stop_id, route_id, batch_id, time_slot, dow)
);

CREATE TABLE dock_hub_distance (
    dock_hub_distance_id SERIAL PRIMARY KEY,
    dock_id      INT NOT NULL REFERENCES rental_dock(dock_id),
    hub_type     VARCHAR(10) NOT NULL CHECK (hub_type IN ('STATION', 'BUS_STOP')),
    hub_id       INT NOT NULL, -- hub_type에 따라 station_id 또는 stop_id를 가리킴 (폴리모픽이라 FK 없음)
    batch_id     INT NOT NULL REFERENCES batch_run(batch_id),
    distance_m   INT NOT NULL,
    UNIQUE (dock_id, hub_type, hub_id, batch_id)
);

-- ============================================================
-- 요청/추천 로그는 Postgres 테이블 없음 — favorites가 영구 보관을 전담하므로
-- Redis TTL(candidate_log.py, route:request:{id}, 1시간)로만 유지한다.
-- ============================================================

-- ============================================================
-- 로그인 / 게시판
-- ============================================================

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(20) NOT NULL UNIQUE, -- 영문/숫자/_ 3~20자
    password_hash VARCHAR(255) NOT NULL,       -- bcrypt 해시만 저장(평문·단순해시 금지)
    nickname      VARCHAR(50) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'member', -- 지금은 미사용 — RBAC 도입 시 이 컬럼으로 확장
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE board_post (
    post_id       SERIAL PRIMARY KEY,
    owner_user_id INT NOT NULL REFERENCES users(user_id),
    nickname      VARCHAR(50) NOT NULL, -- 작성 시점 계정 닉네임 스냅샷(매번 JOIN하지 않음)
    content       TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_board_post_owner ON board_post(owner_user_id);
CREATE INDEX idx_board_post_created_at ON board_post(created_at DESC);

-- ============================================================
-- 선착순 쿠폰 (조건부 기능) — 정의만 DB에 두고, 실제 재고 차감은
-- backend/app/routers/coupon.py에서 Redis(coupon:{id}:stock 등)로 원자적으로 처리한다.
-- ============================================================

CREATE TABLE coupon (
    coupon_id    SERIAL PRIMARY KEY,
    title        VARCHAR(100) NOT NULL,
    total_stock  INT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);
