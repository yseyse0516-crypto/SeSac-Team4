"""line_geometry.get_curve() — 실제 OSM 데이터(backend/app/data/subway_lines.geojson)를
그대로 사용하는 테스트. 좌표는 odsay_sample_response.json에서 실제로 확인된 값(답십리·
왕십리, 수도권 5호선)이라 하드코딩 가중치가 아니라 진짜 지리 데이터로 검증한다.
"""
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
