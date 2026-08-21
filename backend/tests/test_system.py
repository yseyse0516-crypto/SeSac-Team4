"""GET /system/meta, /health, /admin/batch/latest 통합 테스트."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.system import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_system_meta_returns_all_six_fields():
    resp = client.get("/system/meta")
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "front_version",
        "server_version",
        "server_name",
        "server_ip",
        "client_ip",
        "x_forwarded_for",
    ):
        assert field in body


def test_health_reports_db_and_redis_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


def test_admin_batch_latest_returns_seeded_batch():
    resp = client.get("/admin/batch/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_month"] == "2026-08"
    assert body["status"] == "success"
