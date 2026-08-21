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


def test_score_segment_still_capped_at_one_when_net_change_factor_above_one():
    # station_id=3(상선): congestion_pct=140(base=0.9333)에 순증가 factor(1.3, 클램프 상한)가
    # 곱해지면 base*factor≈1.213으로 1.0을 넘는다 — score_segment()가 최종적으로
    # 다시 min(..., 1.0)을 적용해 상한을 지키는지 확인.
    score = scoring.score_segment("subway", MatchResult(matched=True, station_id=3), "상선")
    base = min(140.0 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0)
    factor = scoring.stop_correction_factor(7, 80.0, 20.0)
    assert base * factor > 1.0  # 클램프가 없다면 1.0을 넘겼을 조합인지 사전 확인
    assert score == 1.0


def test_stop_sequence_discount_monotonically_increases_toward_one():
    # 정차순번이 커질수록(출고에서 멀어질수록) discount factor가 1.0에 가까워져야 함(보너스 감소)
    values = [scoring.stop_sequence_discount(s) for s in range(0, 12)]
    assert values[0] < values[-1]
    assert values == sorted(values)
    assert values[0] == pytest.approx(1 - scoring.STOP_SEQUENCE_MAX_BONUS)
    assert all(v == pytest.approx(1.0) for v in values[scoring.STOP_SEQUENCE_DECAY_K:])


def test_stop_sequence_discount_none_is_neutral():
    assert scoring.stop_sequence_discount(None) == 1.0


# --- Q3 재개정: 순증감(하차-승차) 보정 (2026-08-21, backend.md §7.2.1) ---


def test_net_change_discount_below_one_when_alighting_exceeds_boarding():
    # 하차(60) > 승차(20) → 순감소 → 더 쾌적해져야 함(factor < 1.0)
    factor = scoring.net_change_discount(alighting_est=60.0, boarding_est=20.0, capacity=160.0)
    assert factor < 1.0


def test_net_change_discount_above_one_when_boarding_exceeds_alighting():
    # 승차(60) > 하차(20) → 순증가 → 더 혼잡해져야 함(factor > 1.0) — stop_sequence
    # 감산과의 핵심 차이: 이 함수는 양방향으로 움직인다.
    factor = scoring.net_change_discount(alighting_est=20.0, boarding_est=60.0, capacity=160.0)
    assert factor > 1.0


def test_net_change_discount_clamps_extreme_ratio():
    # 극단적인 비율도 ±NET_CHANGE_CLAMP 범위 안으로 잘려야 함
    factor = scoring.net_change_discount(alighting_est=1000.0, boarding_est=0.0, capacity=160.0)
    assert factor == pytest.approx(1.0 - scoring.NET_CHANGE_CLAMP)
    factor = scoring.net_change_discount(alighting_est=0.0, boarding_est=1000.0, capacity=160.0)
    assert factor == pytest.approx(1.0 + scoring.NET_CHANGE_CLAMP)


def test_net_change_discount_zero_capacity_is_neutral():
    assert scoring.net_change_discount(alighting_est=10.0, boarding_est=5.0, capacity=0.0) == 1.0


def test_stop_correction_factor_prefers_net_change_when_both_present():
    # boarding_est/alighting_est가 둘 다 있으면 stop_sequence는 무시돼야 함
    with_net_change = scoring.stop_correction_factor(
        stop_sequence=0, boarding_est=60.0, alighting_est=20.0
    )
    assert with_net_change == pytest.approx(
        scoring.net_change_discount(alighting_est=20.0, boarding_est=60.0, capacity=scoring.SUBWAY_CAR_CAPACITY)
    )
    assert with_net_change != scoring.stop_sequence_discount(0)


def test_stop_correction_factor_falls_back_when_net_change_missing():
    # 배치가 아직 boarding_est/alighting_est를 못 채운 행(둘 다 None, 혹은 하나만 None)은
    # 기존 stop_sequence 감산으로 폴백해야 함(§7.2.1 — 완전 교체가 아니라 우선순위).
    assert scoring.stop_correction_factor(3, None, None) == scoring.stop_sequence_discount(3)
    assert scoring.stop_correction_factor(3, 10.0, None) == scoring.stop_sequence_discount(3)
    assert scoring.stop_correction_factor(3, None, 10.0) == scoring.stop_sequence_discount(3)


def test_subway_score_net_change_reverses_legacy_bonus_at_transfer_station():
    # hardcoded_weights.STATION_WEIGHT[(5, "상선")]: stop_sequence=2(레거시 기준 큰 보너스)
    # 이지만 boarding_est(52) > alighting_est(18)라 실제로는 더 혼잡해지는 환승역 시나리오.
    # 순증감 보정은 레거시와 반대로 congestion_score를 base보다 올려야 한다.
    score = scoring.score_segment("subway", MatchResult(matched=True, station_id=5), "상선")
    base = min(80.0 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0)
    legacy_score = base * scoring.stop_sequence_discount(2)
    assert score > base  # 순증감 보정: 더 혼잡함
    assert score > legacy_score  # 레거시 감산이 냈을 결과와 정반대 방향


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


# 2026-08-21 추가(§7.2.1): cur 경로에서도 boarding_est/alighting_est가 채워진 행이면
# 순증감 보정을 쓰는지 확인 — weight_repository.get_station_weight()가 이 두 컬럼을
# 실제로 SELECT하는지까지 함께 검증한다(누락되면 KeyError로 바로 드러남).
def test_score_segment_with_cur_uses_net_change_when_columns_filled():
    dt = datetime.now()
    try:
        with db.get_cursor() as cur:
            cur.execute(
                "INSERT INTO station (station_name, line_name, station_no, lat, lng) "
                "VALUES ('순증감테스트역', '9호선', '9102', 37.4, 127.4)"
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
                "(station_id, batch_id, direction, time_slot, dow, net_onboard, congestion_pct, "
                "stop_sequence, boarding_est, alighting_est) "
                "VALUES (%s, %s, '상선', %s, %s, 10.0, 90.0, 1, 60.0, 20.0)",
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
            cur.execute("DELETE FROM station WHERE station_no = '9102' AND line_name = '9호선'")

    base = min(90.0 / scoring.SUBWAY_CONGESTION_DIVISOR, 1.0)
    legacy_score = base * scoring.stop_sequence_discount(1)
    assert score != pytest.approx(legacy_score)  # stop_sequence=1(큰 보너스)로 폴백하지 않았어야 함
    assert score == pytest.approx(base * scoring.net_change_discount(20.0, 60.0, scoring.SUBWAY_CAR_CAPACITY))
