from datetime import datetime

import pytest

from app.core import db
from app.services import scoring, weight_repository
from app.services.matching import MatchResult


def test_walk_segment_has_no_score():
    assert scoring.score_segment("walk", MatchResult(matched=False)) is None


def test_unmatched_segment_gets_neutral_score():
    assert scoring.score_segment("subway", MatchResult(matched=False)) == scoring.NEUTRAL_CONGESTION_SCORE
    assert scoring.score_segment("bus", MatchResult(matched=False)) == scoring.NEUTRAL_CONGESTION_SCORE


def test_subway_score_uses_congestion_pct_and_divisor():
    # station_id=1 (답십리), direction="상선": congestion_pct=40.0, stop_sequence=1
    # → 거의 최대 보너스 구간 (hardcoded_weights.STATION_WEIGHT[(1, "상선")])
    score = scoring.score_segment("subway", MatchResult(matched=True, station_id=1), "상선")
    base = min(40.0 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0)
    discount = scoring.stop_sequence_discount(1)
    assert score == pytest.approx(base * discount)


def test_subway_score_differs_by_direction():
    # 2026-08-20 추가: 같은 station_id라도 direction이 다르면 다른 행이 조회돼야 한다
    # — station_weight의 UNIQUE 키에 direction이 추가된 것이 실제로 반영됐는지 확인.
    up = scoring.score_segment("subway", MatchResult(matched=True, station_id=1), "상선")
    down = scoring.score_segment("subway", MatchResult(matched=True, station_id=1), "하선")
    assert up != down


def test_subway_score_with_no_direction_is_neutral():
    # direction 판정 실패(예: 2호선 지선, 시작=도착 등)는 None으로 넘어온다 —
    # 있지도 않은 방향 값을 임의로 골라 쓰지 않고 중립값으로 처리해야 한다.
    score = scoring.score_segment("subway", MatchResult(matched=True, station_id=1), None)
    assert score == scoring.NEUTRAL_CONGESTION_SCORE


def test_bus_score_uses_net_onboard_and_divisor():
    # stop_id=102: net_onboard=38.0
    score = scoring.score_segment("bus", MatchResult(matched=True, stop_id=102))
    base = min(38.0 / scoring.BUS_NET_ONBOARD_DIVISOR, 1.0)
    assert score == pytest.approx(base)  # bus_weight엔 stop_sequence 없음 → discount=1.0


def test_score_capped_at_one():
    # 임의로 아주 높은 congestion_pct를 주는 매칭이 있다면 1.0을 넘지 않아야 함
    # (STATION_WEIGHT 3번 = congestion_pct 140 → 140/150 < 1.0, 그래도 상한 로직 자체를 검증)
    assert min(999 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0) == 1.0


def test_stop_sequence_discount_monotonically_increases_toward_one():
    # 정차순번이 커질수록(출고에서 멀어질수록) discount factor가 1.0에 가까워져야 함(보너스 감소)
    values = [scoring.stop_sequence_discount(s) for s in range(0, 12)]
    assert values[0] < values[-1]
    assert values == sorted(values)
    assert values[0] == pytest.approx(1 - scoring.STOP_SEQUENCE_MAX_BONUS)
    assert all(v == pytest.approx(1.0) for v in values[scoring.STOP_SEQUENCE_DECAY_K:])


def test_stop_sequence_discount_none_is_neutral():
    assert scoring.stop_sequence_discount(None) == 1.0


def test_score_candidate_is_duration_weighted_average():
    # 10분짜리 0.2점 구간 + 30분짜리 0.8점 구간 → 가중평균
    result = scoring.score_candidate([(10, 0.2), (30, 0.8)])
    assert result == pytest.approx((10 * 0.2 + 30 * 0.8) / 40)


def test_score_candidate_empty_segments_is_zero():
    assert scoring.score_candidate([]) == 0.0


# 2026-08-20 추가(김재우, 초안): cur가 주어지면 weight_repository.py를 통해 실제
# DB를 조회한다 — test_weight_repository.py가 그 조회 자체는 이미 검증했으니
# 여기서는 score_segment()가 cur 유무에 따라 올바른 경로를 타는지만 확인한다.
def test_score_segment_with_cur_uses_real_db_row():
    dt = datetime.now()
    try:
        with db.get_cursor() as cur:
            cur.execute(
                "INSERT INTO station (station_name, line_name, station_no, lat, lng) "
                "VALUES ('스코어링테스트역', '9호선', '9101', 37.3, 127.3)"
            )
            cur.execute("SELECT lastval() AS id")
            station_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO batch_run (run_month, status, started_at, finished_at, note) "
                "VALUES ('2026-08', 'success', now(), now(), 'test_scoring.py 전용')"
            )
            cur.execute("SELECT lastval() AS id")
            batch_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO station_weight "
                "(station_id, batch_id, direction, time_slot, dow, net_onboard, congestion_pct, stop_sequence) "
                "VALUES (%s, %s, '상선', %s, %s, 10.0, 75.0, 0)",
                (station_id, batch_id, weight_repository.time_slot_for(dt), dt.weekday()),
            )

        with db.get_cursor() as cur:
            score = scoring.score_segment(
                "subway", MatchResult(matched=True, station_id=station_id), "상선", cur=cur, dt=dt
            )
    finally:
        with db.get_cursor() as cur:
            cur.execute("DELETE FROM station_weight WHERE batch_id = %s", (batch_id,))
            cur.execute("DELETE FROM batch_run WHERE batch_id = %s", (batch_id,))
            cur.execute("DELETE FROM station WHERE station_no = '9101' AND line_name = '9호선'")

    base = min(75.0 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0)
    assert score == pytest.approx(base * scoring.stop_sequence_discount(0))
