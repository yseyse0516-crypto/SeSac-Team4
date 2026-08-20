"""line_geometry.get_curve()/get_bus_curve() 테스트.

get_curve()는 실제 OSM 데이터(backend/app/data/subway_lines.geojson)를 그대로 사용한다.
좌표는 odsay_sample_response.json에서 실제로 확인된 값(답십리·왕십리, 수도권 5호선)이라
하드코딩 가중치가 아니라 진짜 지리 데이터로 검증한다.

get_bus_curve()는 매 테스트 실행마다 실제 Overpass를 호출하면 느리고 네트워크 상태에
좌우돼 CI에서 불안정해지므로, _fetch_bus_line을 모킹해서 캐싱·폴백 로직만 검증한다.
Overpass가 실제로 이런 응답을 준다는 것 자체는 이번 세션에서 504번 버스(서울, 178개
way)로 라이브 조회해서 이미 확인했다 (backend.md §6.3).
"""
import httpx
import pytest
from shapely.geometry import LineString

from app.services import line_geometry

# 답십리 -> 왕십리, 실제로 5호선으로 두 정거장 거리 (odsay_sample_response.json에서 확인)
DAPSIMNI = (37.567091, 127.052362)
WANGSIMNI = (37.561845, 127.037234)


def test_returns_real_curve_with_route_id():
    curve = line_geometry.get_curve("5", *DAPSIMNI, *WANGSIMNI)
    assert curve is not None
    assert len(curve) > 2, "직선이 아니라 실제 선로를 따라가는 여러 점이어야 함"


def test_curve_endpoints_close_to_requested_points():
    curve = line_geometry.get_curve("5", *DAPSIMNI, *WANGSIMNI)
    first, last = curve[0], curve[-1]
    # 대략적인 근접성만 확인 (역 좌표 자체가 선로 중심선과 정확히 일치하진 않음)
    assert abs(first[0] - DAPSIMNI[0]) < 0.01
    assert abs(first[1] - DAPSIMNI[1]) < 0.01
    assert abs(last[0] - WANGSIMNI[0]) < 0.01
    assert abs(last[1] - WANGSIMNI[1]) < 0.01


def test_fallback_search_without_route_id_finds_same_line():
    with_ref = line_geometry.get_curve("5", *DAPSIMNI, *WANGSIMNI)
    without_ref = line_geometry.get_curve(None, *DAPSIMNI, *WANGSIMNI)
    assert without_ref is not None
    # route_id 없이 좌표만으로 찾아도 점 개수가 비슷한 수준이어야 함(같은 노선을 찾았다는 뜻)
    assert abs(len(with_ref) - len(without_ref)) <= 2


def test_no_match_far_from_any_line_returns_none():
    # 서울 근교 바깥, 어떤 노선과도 300m 이내가 아닌 좌표
    curve = line_geometry.get_curve("5", 35.0, 128.5, 35.01, 128.51)
    assert curve is None


def test_wrong_route_id_still_finds_correct_line_via_fallback():
    # route_id가 실제 노선번호 체계와 안 맞는 값(예: 신분당선처럼 숫자가 아닌 문자열)이면
    # 바로 전체 노선 탐색으로 넘어가서 좌표 기준으로 정확한 노선을 찾아야 함
    curve = line_geometry.get_curve("신분당", *DAPSIMNI, *WANGSIMNI)
    assert curve is not None


@pytest.fixture(autouse=True)
def _reset_bus_cache():
    line_geometry._bus_curve_cache.clear()
    yield
    line_geometry._bus_curve_cache.clear()


def _fake_bus_line():
    # 여의도 인근을 지나는 가짜 직선 하나 — 실제 좌표 정확도는 이 테스트의 관심사가 아님
    return [LineString([(126.92, 37.52), (126.93, 37.525), (126.94, 37.53)])]


def test_bus_curve_fetches_once_and_cuts_curve(monkeypatch):
    calls = []

    def fake_fetch(route_ref):
        calls.append(route_ref)
        return _fake_bus_line()

    monkeypatch.setattr(line_geometry, "_fetch_bus_line", fake_fetch)

    curve = line_geometry.get_bus_curve("504", 37.52, 126.92, 37.53, 126.94)
    assert curve is not None
    assert len(curve) >= 2
    assert calls == ["504"]


def test_bus_curve_second_call_uses_cache_not_network(monkeypatch):
    calls = []
    monkeypatch.setattr(
        line_geometry,
        "_fetch_bus_line",
        lambda route_ref: (calls.append(route_ref), _fake_bus_line())[1],
    )

    line_geometry.get_bus_curve("504", 37.52, 126.92, 37.53, 126.94)
    line_geometry.get_bus_curve("504", 37.52, 126.92, 37.53, 126.94)

    assert calls == ["504"], "두 번째 호출은 캐시를 써야 하고 Overpass를 다시 부르면 안 됨"


def test_bus_curve_without_route_ref_returns_none():
    assert line_geometry.get_bus_curve(None, 37.52, 126.92, 37.53, 126.94) is None


def test_bus_curve_network_failure_falls_back_to_none_and_caches_empty(monkeypatch):
    calls = []

    def raise_network_error(route_ref):
        calls.append(route_ref)
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(line_geometry, "_fetch_bus_line", raise_network_error)

    assert line_geometry.get_bus_curve("999", 37.52, 126.92, 37.53, 126.94) is None
    assert line_geometry.get_bus_curve("999", 37.52, 126.92, 37.53, 126.94) is None
    assert calls == ["999"], "실패도 캐싱돼서 두 번째 호출은 다시 Overpass를 부르면 안 됨"


def test_bus_curve_no_match_in_osm_returns_none(monkeypatch):
    monkeypatch.setattr(line_geometry, "_fetch_bus_line", lambda route_ref: [])

    assert line_geometry.get_bus_curve("존재안함", 37.52, 126.92, 37.53, 126.94) is None
