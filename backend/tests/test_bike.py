"""GET /bike/docks, /bike/route 통합 테스트.

이 파일 전용 station/bus_stop/rental_dock/batch_run/dock_hub_distance 데이터를 심고
지운다 — bike.py의 쿼리가 "가장 최근에 성공한 배치" 기준으로 조회하므로, 공용 시드
데이터(02_seed.sql)에 의존하면 다른 배치가 실행될 때마다(예: 실제 월간 배치) 최신
배치가 바뀌면서 값이 달라져 테스트가 깨진다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import db
from app.routers.bike import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def dock_fixture():
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO station (station_name, line_name, lat, lng) VALUES (%s, %s, %s, %s)",
            ("_테스트역", "0호선", 0.0, 0.0),
        )
        cur.execute("SELECT lastval() AS id")
        station_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO bus_stop (stop_std_id, stop_name, lat, lng) VALUES (%s, %s, %s, %s)",
            ("_test_stop_bike", "_테스트정류장", 0.0, 0.0),
        )
        cur.execute("SELECT lastval() AS id")
        stop_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO rental_dock (dock_std_id, dock_name, lat, lng) VALUES (%s, %s, %s, %s)",
            ("_TEST-BIKE-1", "_테스트대여소", 0.0, 0.0),
        )
        cur.execute("SELECT lastval() AS id")
        dock_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO batch_run (run_month, status, started_at, finished_at) "
            "VALUES ('2099-01', 'success', now(), now())"
        )
        cur.execute("SELECT lastval() AS id")
        batch_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO dock_hub_distance (dock_id, hub_type, hub_id, batch_id, distance_m) "
            "VALUES (%s, 'STATION', %s, %s, 120), (%s, 'BUS_STOP', %s, %s, 140)",
            (dock_id, station_id, batch_id, dock_id, stop_id, batch_id),
        )

    yield {"station_id": station_id, "stop_id": stop_id, "dock_id": dock_id}

    with db.get_cursor() as cur:
        cur.execute("DELETE FROM dock_hub_distance WHERE dock_id = %s", (dock_id,))
        cur.execute("DELETE FROM rental_dock WHERE dock_id = %s", (dock_id,))
        cur.execute("DELETE FROM bus_stop WHERE stop_id = %s", (stop_id,))
        cur.execute("DELETE FROM station WHERE station_id = %s", (station_id,))
        cur.execute("DELETE FROM batch_run WHERE batch_id = %s", (batch_id,))


def test_docks_near_station_hub(dock_fixture):
    resp = client.get(
        f"/bike/docks?hub_type=STATION&hub_id={dock_fixture['station_id']}&max_distance=500"
    )
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    assert docks
    assert docks[0]["dock_id"] == dock_fixture["dock_id"]
    assert docks[0]["distance_m"] == 120


def test_docks_near_bus_stop_hub(dock_fixture):
    resp = client.get(
        f"/bike/docks?hub_type=BUS_STOP&hub_id={dock_fixture['stop_id']}&max_distance=500"
    )
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    assert docks
    assert docks[0]["distance_m"] == 140


def test_docks_respects_max_distance(dock_fixture):
    resp = client.get(
        f"/bike/docks?hub_type=STATION&hub_id={dock_fixture['station_id']}&max_distance=1"
    )
    assert resp.status_code == 200
    assert resp.json()["docks"] == []


def test_docks_rejects_invalid_hub_type():
    resp = client.get("/bike/docks?hub_type=station&hub_id=1")
    assert resp.status_code == 422


@pytest.fixture
def nearby_dock_fixture():
    # 서울시청 좌표(37.5665, 126.9780) 기준 가까운/먼 대여소 하나씩.
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO rental_dock (dock_std_id, dock_name, lat, lng) VALUES (%s, %s, %s, %s)",
            ("_TEST-NEAR", "_테스트대여소(근처)", 37.5670, 126.9785),
        )
        cur.execute("SELECT lastval() AS id")
        near_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO rental_dock (dock_std_id, dock_name, lat, lng) VALUES (%s, %s, %s, %s)",
            ("_TEST-FAR", "_테스트대여소(멀리)", 37.65, 127.05),
        )
        cur.execute("SELECT lastval() AS id")
        far_id = cur.fetchone()["id"]

    yield {"near_id": near_id, "far_id": far_id}

    with db.get_cursor() as cur:
        cur.execute("DELETE FROM rental_dock WHERE dock_id IN (%s, %s)", (near_id, far_id))


def test_docks_nearby_returns_only_within_radius(nearby_dock_fixture):
    resp = client.get("/bike/docks/nearby?lat=37.5665&lng=126.9780&radius_m=500")
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    ids = [d["dock_id"] for d in docks]
    assert nearby_dock_fixture["near_id"] in ids
    assert nearby_dock_fixture["far_id"] not in ids


def test_docks_nearby_sorted_by_distance(nearby_dock_fixture):
    resp = client.get("/bike/docks/nearby?lat=37.5665&lng=126.9780&radius_m=5000")
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    distances = [d["distance_m"] for d in docks]
    assert distances == sorted(distances)


def test_bike_route_returns_502_without_api_key(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    resp = client.get(
        "/bike/route?origin_lat=37.5&origin_lng=127.0&dest_lat=37.4&dest_lng=126.9"
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "ROUTE_UNAVAILABLE"
