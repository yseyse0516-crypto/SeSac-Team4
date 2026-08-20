"""GET /routes/{request_id} 통합 테스트."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.result import router
from app.services import candidate_log

app = FastAPI()
app.include_router(router)
client = TestClient(app)

CANDIDATES = [
    {
        "path_type": "subway",
        "total_time_min": 30.0,
        "congestion_score": 0.4,
        "minute_improvement_ratio": 2.0,
        "is_recommended": True,
        "is_fastest": True,
    }
]


def test_missing_request_id_returns_404():
    resp = client.get("/routes/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NO_CANDIDATE"


def test_saved_candidates_are_returned():
    request_id = candidate_log.save_request(
        type("P", (), {"lat": 37.5, "lng": 127.0})(),
        type("P", (), {"lat": 37.4, "lng": 126.9})(),
    )
    candidate_log.save_candidates(request_id, CANDIDATES)

    resp = client.get(f"/routes/{request_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"] == request_id
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["path_type"] == "subway"
    assert body["candidates"][0]["is_fastest"] is True


def test_request_with_no_candidates_returns_empty_list():
    request_id = candidate_log.save_request(
        type("P", (), {"lat": 37.5, "lng": 127.0})(),
        type("P", (), {"lat": 37.4, "lng": 126.9})(),
    )
    resp = client.get(f"/routes/{request_id}")
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []
