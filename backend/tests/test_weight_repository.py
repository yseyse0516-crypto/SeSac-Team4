"""weight_repository.py 단위 테스트 (2026-08-20, 김재우 — A 리뷰 전 초안).

matching.py/scoring.py의 cur=None 경로(하드코딩 fixture)는 기존 test_matching.py/
test_scoring.py가 이미 검증한다. 여기서는 이 모듈이 실제로 station/bus_stop/
station_weight/bus_weight를 올바르게 조회하는지만 직접 검증한다 — 테스트마다
전용 행을 심고 끝나면 지운다(seed 데이터는 direction=NULL/30분 버킷이라 이
모듈의 실제 조회 조건과 안 맞음 — 의도적으로 seed에 의존하지 않는다).
"""
from datetime import datetime

import pytest

from app.core import db
from app.services import weight_repository


def test_time_slot_for_formats_hourly_bucket():
    assert weight_repository.time_slot_for(datetime(2026, 8, 20, 8, 15)) == "08:00-09:00"
    assert weight_repository.time_slot_for(datetime(2026, 8, 20, 23, 59)) == "23:00-24:00"
    assert weight_repository.time_slot_for(datetime(2026, 8, 20, 0, 0)) == "00:00-01:00"


@pytest.fixture
def seeded_rows():
    """station/bus_stop/batch_run/station_weight/bus_weight에 전용 행을 심고 정리한다."""
    dt = datetime.now()
    time_slot = weight_repository.time_slot_for(dt)
    dow = dt.weekday()

    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO station (station_name, line_name, station_no, lat, lng) "
            "VALUES ('테스트역', '9호선', '9001', 37.111111, 127.111111)"
        )
        cur.execute("SELECT lastval() AS id")
        station_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO bus_stop (stop_std_id, stop_name, lat, lng) "
            "VALUES ('999000001', '테스트정류장', 37.222222, 127.222222)"
        )
        cur.execute("SELECT lastval() AS id")
        stop_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO batch_run (run_month, status, started_at, finished_at, note) "
            "VALUES ('2026-08', 'success', now(), now(), 'test_weight_repository.py 전용')"
        )
        cur.execute("SELECT lastval() AS id")
        batch_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO station_weight "
            "(station_id, batch_id, direction, time_slot, dow, net_onboard, congestion_pct, stop_sequence) "
            "VALUES (%s, %s, '상선', %s, %s, 50.0, 90.0, 3)",
            (station_id, batch_id, time_slot, dow),
        )
        cur.execute(
            "INSERT INTO bus_weight (stop_id, route_id, batch_id, time_slot, dow, net_onboard, stop_sequence) "
            "VALUES (%s, '999', %s, %s, %s, 20.0, 6)",
            (stop_id, batch_id, time_slot, dow),
        )

    yield {
        "station_id": station_id,
        "stop_id": stop_id,
        "batch_id": batch_id,
        "dt": dt,
    }

    with db.get_cursor() as cur:
        cur.execute("DELETE FROM station_weight WHERE batch_id = %s", (batch_id,))
        cur.execute("DELETE FROM bus_weight WHERE batch_id = %s", (batch_id,))
        cur.execute("DELETE FROM batch_run WHERE batch_id = %s", (batch_id,))
        cur.execute("DELETE FROM bus_stop WHERE stop_std_id = '999000001'")
        cur.execute("DELETE FROM station WHERE station_no = '9001' AND line_name = '9호선'")


def test_latest_batch_id_returns_most_recent_success(seeded_rows):
    with db.get_cursor() as cur:
        assert weight_repository.latest_batch_id(cur) == seeded_rows["batch_id"]


def test_match_subway_station_finds_row_within_radius(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.match_subway_station(cur, 37.111111, 127.111111)
    assert row is not None
    assert row["station_id"] == seeded_rows["station_id"]
    assert row["line_name"] == "9호선"
    assert row["station_no"] == "9001"


def test_match_subway_station_no_match_far_away(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.match_subway_station(cur, 35.1796, 129.0756)  # 부산
    assert row is None


def test_match_subway_station_none_coordinates():
    with db.get_cursor() as cur:
        row = weight_repository.match_subway_station(cur, None, None)
    assert row is None


def test_match_bus_stop_by_std_id(seeded_rows):
    with db.get_cursor() as cur:
        stop_id = weight_repository.match_bus_stop(cur, "999000001")
    assert stop_id == seeded_rows["stop_id"]


def test_match_bus_stop_unknown_std_id(seeded_rows):
    with db.get_cursor() as cur:
        stop_id = weight_repository.match_bus_stop(cur, "no-such-id")
    assert stop_id is None


def test_get_station_weight_matches_direction_time_slot_dow(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_station_weight(
            cur, seeded_rows["station_id"], "상선", seeded_rows["dt"]
        )
    assert row is not None
    assert float(row["congestion_pct"]) == 90.0
    assert row["stop_sequence"] == 3
    # 2026-08-21 추가(§7.2.1): 순증감 보정 컬럼이 SELECT에 포함돼야 한다.
    # seeded_rows는 이 두 컬럼을 안 채우므로 NULL(None)로 나와야 정상.
    assert row["boarding_est"] is None
    assert row["alighting_est"] is None


def test_get_station_weight_none_direction_returns_none(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_station_weight(cur, seeded_rows["station_id"], None, seeded_rows["dt"])
    assert row is None


def test_get_station_weight_wrong_direction_returns_none(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_station_weight(cur, seeded_rows["station_id"], "하선", seeded_rows["dt"])
    assert row is None


def test_get_bus_weight_matches_stop_route_time_slot_dow(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_bus_weight(cur, seeded_rows["stop_id"], "999", seeded_rows["dt"])
    assert row is not None
    assert float(row["net_onboard"]) == 20.0
    assert row["stop_sequence"] == 6
    assert row["boarding_est"] is None
    assert row["alighting_est"] is None


def test_get_bus_weight_missing_route_id_returns_none(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_bus_weight(cur, seeded_rows["stop_id"], None, seeded_rows["dt"])
    assert row is None


def test_get_bus_weight_wrong_route_id_returns_none(seeded_rows):
    with db.get_cursor() as cur:
        row = weight_repository.get_bus_weight(cur, seeded_rows["stop_id"], "no-such-route", seeded_rows["dt"])
    assert row is None
