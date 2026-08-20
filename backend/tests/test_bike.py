"""GET /bike/docks, /bike/route 통합 테스트.

02_seed.sql 기준 데이터를 그대로 쓴다: station_id=1(강남역), dock_id=1(강남역 2번출구,
STATION hub_id=1까지 120m, BUS_STOP hub_id=1까지 140m).
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.bike import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_docks_near_station_hub():
    resp = client.get("/bike/docks?hub_type=STATION&hub_id=1&max_distance=500")
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    assert docks
    assert docks[0]["dock_id"] == 1
    assert docks[0]["distance_m"] == 120


def test_docks_near_bus_stop_hub():
    resp = client.get("/bike/docks?hub_type=BUS_STOP&hub_id=1&max_distance=500")
    assert resp.status_code == 200
    docks = resp.json()["docks"]
    assert docks
    assert docks[0]["distance_m"] == 140


def test_docks_respects_max_distance():
    resp = client.get("/bike/docks?hub_type=STATION&hub_id=1&max_distance=1")
    assert resp.status_code == 200
    assert resp.json()["docks"] == []


def test_docks_rejects_invalid_hub_type():
    resp = client.get("/bike/docks?hub_type=station&hub_id=1")
    assert resp.status_code == 422


def test_bike_route_returns_502_without_api_key(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    resp = client.get(
        "/bike/route?origin_lat=37.5&origin_lng=127.0&dest_lat=37.4&dest_lng=126.9"
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "ROUTE_UNAVAILABLE"
