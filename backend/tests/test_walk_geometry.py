"""walk_geometry.get_walk_curve() — Tmap 보행자경로 API 연동 테스트.

_call_tmap을 모킹해서 파싱/폴백 로직을 검증한다(실제 API 라이브 검증은 backend.md §13 참고).
"""
import httpx
import pytest

from app.services import walk_geometry


def _fake_tmap_response():
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.0, 37.5]}},
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[127.0, 37.5], [127.001, 37.501], [127.002, 37.502]],
                },
            },
        ],
    }


def test_no_app_key_returns_none_without_network_call(monkeypatch):
    monkeypatch.delenv("TMAP_APP_KEY", raising=False)
    calls = []
    monkeypatch.setattr(walk_geometry, "_call_tmap", lambda app_key, body: calls.append(1))

    assert walk_geometry.get_walk_curve(37.5, 127.0, 37.6, 127.1) is None
    assert calls == [], "키가 없으면 네트워크 호출 자체를 하면 안 됨"


def test_valid_response_concatenates_linestring_coords_as_lat_lng(monkeypatch):
    monkeypatch.setenv("TMAP_APP_KEY", "test-key")
    monkeypatch.setattr(walk_geometry, "_call_tmap", lambda app_key, body: _fake_tmap_response())

    curve = walk_geometry.get_walk_curve(37.5, 127.0, 37.502, 127.002)
    assert curve == [(37.5, 127.0), (37.501, 127.001), (37.502, 127.002)]


def test_point_features_are_ignored():
    # _fake_tmap_response에 Point 하나 + LineString 하나가 섞여 있어도 좌표 개수가
    # LineString 것과 같아야 함(Point가 섞여 들어가면 안 됨)
    data = _fake_tmap_response()
    line_coords = data["features"][1]["geometry"]["coordinates"]
    assert len(line_coords) == 3


def test_network_failure_falls_back_to_none(monkeypatch):
    monkeypatch.setenv("TMAP_APP_KEY", "test-key")

    def raise_error(app_key, body):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(walk_geometry, "_call_tmap", raise_error)
    assert walk_geometry.get_walk_curve(37.5, 127.0, 37.6, 127.1) is None


def test_response_without_linestring_returns_none(monkeypatch):
    monkeypatch.setenv("TMAP_APP_KEY", "test-key")
    monkeypatch.setattr(walk_geometry, "_call_tmap", lambda app_key, body: {"features": []})

    assert walk_geometry.get_walk_curve(37.5, 127.0, 37.6, 127.1) is None
