"""Q1 — 혼잡 스코어링, Q3 — 정차순번 감산 / 순증감 보정.

정규화 방향: 0에 가까울수록 쾌적 (backend.md §7.1 — 팀 전체 통일 규칙, 어기면 추천이
정확히 거꾸로 나온다).

Q3는 scoring.py가 A 전담 파일이라 B 확인 없이 A 단독으로 계단식 대신 완만한 감산으로
확정했다 (backend.md §7.2). 상수(K, MAX_BONUS)는 근거 데이터가 없는 추정치라 언제든
튜닝 가능하게 상단에 분리해뒀다.

2026-08-20 수정: station_weight의 UNIQUE 키에 direction이 추가돼(01_schema.sql),
같은 station_id라도 방향에 따라 값이 2개 존재한다. score_segment()에 direction
파라미터를 추가해 (station_id, direction)로 조회하도록 바꿨다 — direction이
None이면(매칭 실패, 판정 불가 예외 등 — direction.py 참고) 조회 자체를 시도하지
않고 중립값을 적용한다(있지도 않은 값을 임의로 골라 쓰지 않기 위함).

2026-08-20 추가 수정(김재우, 초안 — A 리뷰 전): cur(DB 커서)를 넘기면
hardcoded_weights.py의 가짜 값 대신 weight_repository.py로 실제 station_weight/
bus_weight를 조회한다. cur를 넘기지 않으면(기존 단위 테스트 호출 방식) 지금까지처럼
하드코딩된 딕셔너리로 동작한다 — matching.py와 동일한 이유(기존 단위 테스트 보존).
dt는 조회에 쓸 time_slot/dow 계산 기준 시각(SearchRequest.departure_time, 없으면
호출부가 now()를 넘김), route_id는 버스 구간에서 bus_weight.route_id 조회에 필요.

2026-08-21 재개정(backend.md §7.2.1): Q3를 stop_sequence 감산에서 순증감(하차-승차)
기반 보정으로 바꾼다. stop_sequence는 "출고역에서 멀수록 혼잡하다"는 가정 하나에만
기대는 대리 지표라, 환승역처럼 초반 정차순번에서 대량 하차가 몰리는 지점에는 실제와
반대 방향의 보너스를 준다. boarding_est/alighting_est(배치가 채워주는 승하차 추정치)가
둘 다 있으면 이 값으로 직접 보정하고, 없으면(배치 미반영) 기존 stop_sequence 감산으로
폴백한다 — 완전 교체가 아니라 더 좋은 신호가 있을 때만 우선 적용.
"""
from typing import Optional

from app.services import weight_repository
from app.services.hardcoded_weights import BUS_WEIGHT, STATION_WEIGHT
from app.services.matching import MatchResult

# Q1
SUBWAY_CONGESTION_DIVISOR = 150.0
BUS_NET_ONBOARD_DIVISOR = 50.0

# Q4 매칭 실패 시 중립값 (매칭 실패한 구간을 최선도 최악도 아닌 것으로 처리)
NEUTRAL_CONGESTION_SCORE = 0.5

# Q3(레거시) — 완만한 감산: stop_sequence=0(출고 직후)에서 최대 보너스, K 이상이면 보너스 없음.
# boarding_est/alighting_est가 없는 행에 대한 폴백으로만 쓰인다(§7.2.1).
STOP_SEQUENCE_DECAY_K = 8
STOP_SEQUENCE_MAX_BONUS = 0.3

# Q3(순증감 보정, §7.2.1) — (alighting_est - boarding_est) / capacity를 ±NET_CHANGE_CLAMP로
# 자른 뒤 1에서 빼서 보정 계수로 쓴다. 하차가 승차보다 많으면(순감소) factor<1(더 쾌적해짐),
# 승차가 하차보다 많으면(순증가) factor>1(더 혼잡해짐) — stop_sequence 감산과 달리 양방향이다.
NET_CHANGE_CLAMP = 0.3
SUBWAY_CAR_CAPACITY = 160.0  # 근거 데이터 없는 추정 정원 — STOP_SEQUENCE_DECAY_K와 같은 위상의 상수


def stop_sequence_discount(stop_sequence: Optional[int]) -> float:
    """정차순번이 낮을수록(출고역에 가까울수록) 완만하게 congestion_score를 깎는다."""
    if stop_sequence is None:
        return 1.0
    ramp = max(0.0, (STOP_SEQUENCE_DECAY_K - stop_sequence) / STOP_SEQUENCE_DECAY_K)
    return 1.0 - ramp * STOP_SEQUENCE_MAX_BONUS


def net_change_discount(alighting_est: float, boarding_est: float, capacity: float) -> float:
    """하차/승차 추정치로 순증감 비율을 계산해 보정 계수를 만든다.

    capacity<=0은 방어적 처리일 뿐 실제로 발생할 수 없다(SUBWAY_CAR_CAPACITY가
    상수라 호출부가 0/음수를 넘길 경로가 없음) — 나눗셈 에러 대신 중립(1.0)으로 방어.
    """
    if capacity <= 0:
        return 1.0
    net_change_ratio = (alighting_est - boarding_est) / capacity
    clamped = max(-NET_CHANGE_CLAMP, min(NET_CHANGE_CLAMP, net_change_ratio))
    return 1.0 - clamped


def stop_correction_factor(
    stop_sequence: Optional[int],
    boarding_est: Optional[float] = None,
    alighting_est: Optional[float] = None,
) -> float:
    """Q3 보정 계수. 순증감 데이터가 있으면 우선 사용하고, 없으면 stop_sequence로 폴백한다."""
    if boarding_est is not None and alighting_est is not None:
        return net_change_discount(alighting_est, boarding_est, SUBWAY_CAR_CAPACITY)
    return stop_sequence_discount(stop_sequence)


def score_segment(
    mode: str,
    match: MatchResult,
    direction: Optional[str] = None,
    cur=None,
    dt=None,
    route_id: Optional[str] = None,
) -> Optional[float]:
    """구간 하나의 congestion_score. 도보 구간은 혼잡 개념이 없어 None(가중평균에서 제외).

    direction은 지하철 구간에서만 쓴다(direction.determine_direction()의 반환값을
    그대로 전달). 버스는 방향 개념이 없어 무시한다.

    cur가 주어지면 실제 station_weight/bus_weight를 조회한다(dt=조회 기준 시각,
    route_id=버스 노선ID, 둘 다 이 경로에서 필요). cur가 없으면 기존처럼
    hardcoded_weights.py를 그대로 쓴다(단위 테스트 호환).
    """
    if mode == "walk":
        return None

    if not match.matched:
        return NEUTRAL_CONGESTION_SCORE

    if mode == "subway":
        if cur is not None:
            row = weight_repository.get_station_weight(cur, match.station_id, direction, dt)
            if row is None:
                return NEUTRAL_CONGESTION_SCORE
            base = min(float(row["congestion_pct"]) / SUBWAY_CONGESTION_DIVISOR, 1.0)
            factor = stop_correction_factor(
                row["stop_sequence"], _as_float(row["boarding_est"]), _as_float(row["alighting_est"])
            )
            return min(base * factor, 1.0)

        weight = STATION_WEIGHT.get((match.station_id, direction))
        if weight is None:
            # direction=None(매칭 실패/판정 불가) 또는 그 방향의 행이 아직 없음 —
            # 둘 다 "값을 신뢰할 수 없음"이므로 동일하게 중립 처리(Q4 정책과 동일).
            return NEUTRAL_CONGESTION_SCORE
        base = min(weight.congestion_pct / SUBWAY_CONGESTION_DIVISOR, 1.0)
        factor = stop_correction_factor(weight.stop_sequence, weight.boarding_est, weight.alighting_est)
        return min(base * factor, 1.0)

    if mode == "bus":
        if cur is not None:
            row = weight_repository.get_bus_weight(cur, match.stop_id, route_id, dt)
            if row is None:
                return NEUTRAL_CONGESTION_SCORE
            base = min(float(row["net_onboard"]) / BUS_NET_ONBOARD_DIVISOR, 1.0)
            factor = stop_correction_factor(
                row["stop_sequence"], _as_float(row["boarding_est"]), _as_float(row["alighting_est"])
            )
            return min(base * factor, 1.0)

        weight = BUS_WEIGHT.get(match.stop_id)
        if weight is None:
            return NEUTRAL_CONGESTION_SCORE
        base = min(weight.net_onboard / BUS_NET_ONBOARD_DIVISOR, 1.0)
        factor = stop_correction_factor(weight.stop_sequence, weight.boarding_est, weight.alighting_est)
        return min(base * factor, 1.0)

    return NEUTRAL_CONGESTION_SCORE


def _as_float(value: Optional[object]) -> Optional[float]:
    """DB 조회 결과(Decimal/None)를 stop_correction_factor가 받는 float/None으로 맞춘다."""
    return None if value is None else float(value)


def score_candidate(segment_scores: list[tuple[int, float]]) -> float:
    """경로 전체 점수 = 구간 소요시간 가중평균 (Q1). segment_scores = [(duration_min, score), ...]."""
    total_duration = sum(duration for duration, _ in segment_scores)
    if total_duration == 0:
        return 0.0
    weighted_sum = sum(duration * score for duration, score in segment_scores)
    return weighted_sum / total_duration
