"""POST /api/v1/routes/search 통합 테스트.

main.py는 B 담당이라 여기선 테스트 전용으로 라우터만 얹은 앱을 즉석에서 만든다.
ODSAY_API_KEY가 없는 상태이므로 odsay_client가 자동으로 fixture(샘플 응답)를 사용한다 —
실제 키가 들어오면 이 테스트는 그대로 두고 call_odsay()의 실호출 경로만 별도 검증하면 된다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.search import router
from app.services import line_geometry

app = FastAPI()
app.include_router(router)
client = TestClient(app)

REQUEST_BODY = {
    "origin": {"lat": 37.5012, "lng": 127.0396},
    "destination": {"lat": 37.4784, "lng": 126.8874},
}


@pytest.fixture(autouse=True)
def _stub_bus_curve_lookup(monkeypatch):
    """get_bus_curve()가 실제 Overpass를 호출하지 않게 막는다 — 이 파일은 라우터 동작을
    검증하는 것이라 외부망 호출까지 태울 필요가 없다(느리고 인터넷 상태에 좌우됨).
    line_geometry 자체의 캐싱/폴백 동작은 test_line_geometry.py에서 모킹으로 검증함."""
    line_geometry._bus_curve_cache.clear()
    monkeypatch.setattr(line_geometry, "_fetch_bus_line", lambda route_ref: [])
    yield
    line_geometry._bus_curve_cache.clear()


def test_search_returns_200_with_candidates():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidates"], "샘플 응답 기준 17개 후보가 나와야 함"
    assert len(body["candidates"]) == 17


def test_exactly_one_candidate_is_recommended():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    recommended = [c for c in body["candidates"] if c["is_recommended"]]
    assert len(recommended) == 1


def test_every_segment_has_coordinates():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    for candidate in body["candidates"]:
        for seg in candidate["segments"]:
            assert seg["start"]["lat"] is not None
            assert seg["end"]["lat"] is not None


def test_bus_segment_has_matched_stop_id_when_known():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    bus_segments = [
        seg
        for c in body["candidates"]
        for seg in c["segments"]
        if seg["mode"] == "bus"
    ]
    assert bus_segments
    # 118000070(여의도역6번출구)는 hardcoded_weights에 있는 정류장이라 매칭돼야 함
    matched_known = [s for s in bus_segments if s["stop_std_id"] == "118000070"]
    assert matched_known and matched_known[0]["matched"] is True
    assert matched_known[0]["stop_id"] == 101


def test_out_of_range_coordinates_return_400_invalid_input():
    bad_body = {
        "origin": {"lat": 999.0, "lng": 127.0},
        "destination": {"lat": 37.4, "lng": 126.8},
    }
    resp = client.post("/api/v1/routes/search", json=bad_body)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_INPUT"


def test_wrong_type_coordinates_return_422():
    bad_body = {
        "origin": {"lat": "not-a-number", "lng": 127.0},
        "destination": {"lat": 37.4, "lng": 126.8},
    }
    resp = client.post("/api/v1/routes/search", json=bad_body)
    assert resp.status_code == 422  # FastAPI/Pydantic 자체 타입 검증 실패 (스키마 단계)
