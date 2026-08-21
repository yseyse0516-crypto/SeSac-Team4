from app.core import db
from app.services import matching


def test_subway_exact_coordinate_matches():
    # 답십리역 정확한 좌표 (hardcoded_weights.STATION_MASTER)
    result = matching.match_subway_station(37.567091, 127.052362)
    assert result.matched is True
    assert result.station_id == 1


def test_subway_match_includes_line_name_and_station_no():
    # 2026-08-20 추가: direction.py 계산에 필요한 line_name/station_no가
    # 매칭 성공 시 함께 채워져야 한다 (답십리=5호선 2543).
    result = matching.match_subway_station(37.567091, 127.052362)
    assert result.line_name == "5호선"
    assert result.station_no == "2543"


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


# 2026-08-20 추가(김재우, 초안): cur가 주어지면 하드코딩 fixture 대신 실제
# station/bus_stop 테이블을 조회한다 — test_weight_repository.py가 조회 로직 자체는
# 검증하니 여기서는 matching.py가 cur 유무에 따라 올바른 경로로 분기하는지만 확인한다.
def test_subway_with_cur_queries_real_db():
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO station (station_name, line_name, station_no, lat, lng) "
            "VALUES ('매칭테스트역', '9호선', '9201', 37.4, 127.4)"
        )
    try:
        with db.get_cursor() as cur:
            result = matching.match_subway_station(37.4, 127.4, cur)
        assert result.matched is True
        assert result.line_name == "9호선"
        assert result.station_no == "9201"
    finally:
        with db.get_cursor() as cur:
            cur.execute("DELETE FROM station WHERE station_no = '9201' AND line_name = '9호선'")


def test_bus_with_cur_queries_real_db():
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO bus_stop (stop_std_id, stop_name, lat, lng) "
            "VALUES ('999000002', '매칭테스트정류장', 37.5, 127.5)"
        )
    try:
        with db.get_cursor() as cur:
            result = matching.match_bus_stop("999000002", cur)
        assert result.matched is True
        assert result.stop_id is not None
    finally:
        with db.get_cursor() as cur:
            cur.execute("DELETE FROM bus_stop WHERE stop_std_id = '999000002'")
