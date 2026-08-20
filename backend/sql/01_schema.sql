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
    lat          NUMERIC(9,6) NOT NULL,
    lng          NUMERIC(9,6) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
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
    -- 행정안전부 "전국 공영자전거 실시간 정보" API의 rntstnId(예: "ST-10")를 그대로 저장한다.
    -- 서울시 원본 파일의 "대여소 번호"(예: "102")와는 다른 체계라 서로 매칭되지 않는 것을
    -- 실제 API 응답으로 확인했다(docs/decisions/backend-b.md §3-1) — 원본 파일의 대여소
    -- 번호를 그대로 넣지 않도록 주의. 배치가 아직 이 값을 채우지 않은 기존 행을 위해 NULL 허용.
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
    time_slot         VARCHAR(20) NOT NULL, -- 예: '08:00-08:30'
    dow               SMALLINT NOT NULL,    -- 0=월 .. 6=일
    net_onboard       NUMERIC(10,2),        -- 재차인원
    congestion_pct    NUMERIC(6,2),         -- %혼잡도 (Q1 subway_score = min(congestion_pct/150, 1.0))
    stop_sequence     SMALLINT,             -- 정차순번 (Q3 감산 계수: stop_sequence <= 3이면 score *= 0.7)
    UNIQUE (station_id, batch_id, time_slot, dow)
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
-- 요청/추천 로그 (N-04 대응: 좌표 소수점 3자리 절삭 = 약 100m 격자, 사용자 식별자 없음)
-- ============================================================

CREATE TABLE route_request (
    request_id   SERIAL PRIMARY KEY,
    origin_lat   NUMERIC(6,3) NOT NULL,
    origin_lng   NUMERIC(6,3) NOT NULL,
    dest_lat     NUMERIC(6,3) NOT NULL,
    dest_lng     NUMERIC(6,3) NOT NULL,
    requested_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE route_candidate (
    candidate_id             SERIAL PRIMARY KEY,
    request_id               INT NOT NULL REFERENCES route_request(request_id),
    path_type                VARCHAR(20) NOT NULL, -- 'SUBWAY' | 'BUS' | 'BIKE' | 'MIXED'
    total_time_min           NUMERIC(6,2) NOT NULL,
    congestion_score         NUMERIC(6,3),
    minute_improvement_ratio NUMERIC(6,3),
    is_recommended           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at               TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_route_candidate_request_id ON route_candidate(request_id);

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
