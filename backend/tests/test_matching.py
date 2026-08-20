from app.services import matching


def test_subway_exact_coordinate_matches():
    # 답십리역 정확한 좌표 (hardcoded_weights.STATION_MASTER)
    result = matching.match_subway_station(37.567091, 127.052362)
    assert result.matched is True
    assert result.station_id == 1


def test_subway_within_100m_still_matches():
    # 답십리역에서 약 50m 정도 떨어진 좌표 (위도 0.00045도 ≈ 50m)
    result = matching.match_subway_station(37.567091 + 0.00045, 127.052362)
    assert result.matched is True
    assert result.station_id == 1


def test_subway_far_away_does_not_match():
    # 부산 좌표 — 어떤 역과도 100m 이내가 아님
    result = matching.match_subway_station(35.1796, 129.0756)
    assert result.matched is False
    assert result.station_id is None


def test_subway_none_coordinates_does_not_match():
    result = matching.match_subway_station(None, None)
    assert result.matched is False


def test_bus_matches_by_stop_std_id_directly():
    result = matching.match_bus_stop("118000070")
    assert result.matched is True
    assert result.stop_id == 101


def test_bus_unknown_stop_std_id_does_not_match():
    result = matching.match_bus_stop("999999999")
    assert result.matched is False


def test_bus_missing_stop_std_id_does_not_match():
    result = matching.match_bus_stop(None)
    assert result.matched is False
