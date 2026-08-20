"""따릉이 대여소 - 교통거점(지하철역/버스정류장) 거리 동기화 (dock_hub_distance).

기획명세서 §5.1: "대여소 거리는 위경도 기반 haversine에 도로보정계수를 곱해
오프라인으로 계산하며, 실시간 API 호출은 필요하지 않다." 이 모듈이 그 계산을
한다 — rental_dock(따릉이 대여소, dock_master_sync가 이미 채워둔 것)과
station/bus_stop(교통거점) 사이의 거리를 미리 다 계산해 저장해두면, 사용자
요청 시(`GET /bike/docks?hub_type=...&hub_id=...&max_distance=...`, backend.md
§6) 실시간 계산 없이 조회만 하면 된다.

## 도로보정계수 — 새 값을 만들지 않고 이미 검증된 값을 재사용

haversine(직선거리)은 실제 도보/자전거 이동 거리보다 항상 짧다. 이 프로젝트는
이미 OSRM 자전거 프로필을 2단계로 검증하면서 **우회계수 1.19배**를 확인해뒀다
(세그먼트 방위각 99.97% 일치, 평균속도 14.7km/h — 텅텅_API데이터소스현황
5절 "경로탐색" 참고). 새로 추정치를 만들지 않고 이 값을 그대로 쓴다:
    실제_거리_m = haversine_m × 1.19

## 계산 범위를 어떻게 자를 것인가 — 전수 조합은 불가능한 규모

대여소(서울 전체 약 3,200개) × station(269개) + 대여소 × bus_stop(12,898개)를
전부 계산하면 4천만 쌍이 넘는다 — 대부분은 수 km~수십 km 떨어져 있어 애초에
서비스에서 쓸 일이 없는 조합이다. `/bike/docks` 예시가 `max_distance=500`을
쓰는 걸 참고해서(backend.md §6), **직선거리 기준 1,000m 이내**인 쌍만 계산해
저장한다(요청 가능한 max_distance보다 넉넉히 여유를 둠). 이 컷오프 밖의
조합은 애초에 서비스가 "근처 대여소"로 보여줄 대상이 아니라고 판단했다 —
필요해지면 CUTOFF_M 상수만 늘리면 된다.

## 성능 — PostGIS/earthdistance 없이 격자 버케팅으로 후보를 줄인다

이 프로젝트 스택엔 PostGIS가 없다(설치 여부 확인 안 됨, 새 확장 의존성을
늘리고 싶지 않았음). 대신 순수 파이썬으로 위경도를 약 1km 격자로 나눠
(위도 0.01도 ≈ 1.11km, 경도는 서울 위도(37.5°N) 기준 0.0125도 ≈ 1.11km)
같은 칸 및 인접 8칸에 있는 후보만 정확한 haversine으로 검증한다 — 전수
비교(O(N×M))가 아니라 격자 기준 O(N)에 가깝게 줄어든다.

⚠️ 경도 격자 크기(0.0125도)는 서울 위도 기준 근사치다. 위도가 크게 달라지는
지역까지 이 배치를 확장한다면 격자 크기를 위도별로 다시 계산해야 한다(현재는
서울 스코프라 문제 없음).

사용법 (배치 러너에서, station_sync/bus_stop_sync/dock_master_sync 전부 끝난
뒤에 실행 — 세 마스터 테이블 전부의 FK 필요):
    from app.batch.dock_hub_distance_sync import sync_dock_hub_distance
    n = sync_dock_hub_distance(cur, batch_id)
"""
import math
from collections import defaultdict

ROAD_DETOUR_FACTOR = 1.19  # OSRM 실측 검증값 (위 docstring 참고)
CUTOFF_M = 1000  # 이 거리 밖은 저장하지 않음

_LAT_CELL_DEG = 0.01  # 위도 방향 격자 한 칸 ≈ 1.11km
_LNG_CELL_DEG = 0.0125  # 경도 방향 격자 한 칸 ≈ 1.11km (서울 위도 37.5°N 기준 근사)

_EARTH_RADIUS_M = 6371000.0


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _cell(lat, lng):
    return (int(lat // _LAT_CELL_DEG), int(lng // _LNG_CELL_DEG))


def _build_grid(hubs: list[dict]) -> dict:
    """hubs = [{'id':..., 'lat':..., 'lng':...}, ...] -> {cell: [hub, ...]}"""
    grid = defaultdict(list)
    for h in hubs:
        grid[_cell(h["lat"], h["lng"])].append(h)
    return grid


def _nearby_pairs(docks: list[dict], hubs: list[dict]):
    """docks 각각에 대해 CUTOFF_M 이내의 hub를 찾아 (dock, hub, distance_m)을 낸다."""
    grid = _build_grid(hubs)
    for dock in docks:
        dlat_cell, dlng_cell = _cell(dock["lat"], dock["lng"])
        for dlat in (-1, 0, 1):
            for dlng in (-1, 0, 1):
                for hub in grid.get((dlat_cell + dlat, dlng_cell + dlng), []):
                    d = _haversine_m(dock["lat"], dock["lng"], hub["lat"], hub["lng"])
                    if d <= CUTOFF_M:
                        yield dock["id"], hub["id"], d


_CREATE_TEMP_SQL = """
    CREATE TEMP TABLE _dock_hub_distance_staging (
        dock_id INT, hub_type VARCHAR(10), hub_id INT, batch_id INT, distance_m INT
    ) ON COMMIT DROP
"""

_MERGE_SQL = """
    INSERT INTO dock_hub_distance (dock_id, hub_type, hub_id, batch_id, distance_m)
    SELECT dock_id, hub_type, hub_id, batch_id, MIN(distance_m)
    FROM _dock_hub_distance_staging
    GROUP BY dock_id, hub_type, hub_id, batch_id
    ON CONFLICT (dock_id, hub_type, hub_id, batch_id)
    DO UPDATE SET distance_m = EXCLUDED.distance_m
"""


def sync_dock_hub_distance(cur, batch_id: int) -> int:
    """dock_hub_distance에 이번 batch_id로 행을 삽입한다. 반영된 행 수를 반환한다.

    rental_dock/station/bus_stop 세 마스터 테이블이 모두 먼저 채워져 있어야 한다.
    """
    cur.execute("SELECT dock_id AS id, lat::float AS lat, lng::float AS lng FROM rental_dock")
    docks = cur.fetchall()
    cur.execute("SELECT station_id AS id, lat::float AS lat, lng::float AS lng FROM station")
    stations = cur.fetchall()
    cur.execute("SELECT stop_id AS id, lat::float AS lat, lng::float AS lng FROM bus_stop")
    bus_stops = cur.fetchall()

    if not docks:
        print("[dock_hub_distance_sync] 경고: rental_dock이 비어 있어 계산할 것이 없음")
        return 0

    cur.execute(_CREATE_TEMP_SQL)
    with cur.copy("COPY _dock_hub_distance_staging FROM STDIN") as copy:
        for dock_id, station_id, dist in _nearby_pairs(docks, stations):
            copy.write_row((dock_id, "STATION", station_id, batch_id, round(dist * ROAD_DETOUR_FACTOR)))
        for dock_id, stop_id, dist in _nearby_pairs(docks, bus_stops):
            copy.write_row((dock_id, "BUS_STOP", stop_id, batch_id, round(dist * ROAD_DETOUR_FACTOR)))

    # bus_weight_sync.py와 동일한 이유로 DISABLE TRIGGER ALL 대신 FK DROP/ADD를 쓴다
    # (system trigger는 superuser가 아니면 못 끈다 — bus_weight_sync.py 참고).
    cur.execute("SET LOCAL work_mem = '256MB'")
    cur.execute("ALTER TABLE dock_hub_distance DROP CONSTRAINT dock_hub_distance_dock_id_fkey")
    cur.execute("ALTER TABLE dock_hub_distance DROP CONSTRAINT dock_hub_distance_batch_id_fkey")
    try:
        cur.execute(_MERGE_SQL)
        n = cur.rowcount
    finally:
        cur.execute(
            "ALTER TABLE dock_hub_distance ADD CONSTRAINT dock_hub_distance_dock_id_fkey "
            "FOREIGN KEY (dock_id) REFERENCES rental_dock(dock_id)"
        )
        cur.execute(
            "ALTER TABLE dock_hub_distance ADD CONSTRAINT dock_hub_distance_batch_id_fkey "
            "FOREIGN KEY (batch_id) REFERENCES batch_run(batch_id)"
        )
    return n
