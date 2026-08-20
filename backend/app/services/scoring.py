"""Q1 — 혼잡 스코어링, Q3 — 정차순번 감산.

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
"""
from typing import Optional

from app.services.hardcoded_weights import BUS_WEIGHT, STATION_WEIGHT
from app.services.matching import MatchResult

# Q1
SUBWAY_CONGESTION_DIVISOR = 150.0
BUS_NET_ONBOARD_DIVISOR = 50.0

# Q4 매칭 실패 시 중립값 (매칭 실패한 구간을 최선도 최악도 아닌 것으로 처리)
NEUTRAL_CONGESTION_SCORE = 0.5

# Q3 — 완만한 감산: stop_sequence=0(출고 직후)에서 최대 보너스, K 이상이면 보너스 없음
STOP_SEQUENCE_DECAY_K = 8
STOP_SEQUENCE_MAX_BONUS = 0.3


def stop_sequence_discount(stop_sequence: Optional[int]) -> float:
    """정차순번이 낮을수록(출고역에 가까울수록) 완만하게 congestion_score를 깎는다."""
    if stop_sequence is None:
        return 1.0
    ramp = max(0.0, (STOP_SEQUENCE_DECAY_K - stop_sequence) / STOP_SEQUENCE_DECAY_K)
    return 1.0 - ramp * STOP_SEQUENCE_MAX_BONUS


def score_segment(
    mode: str, match: MatchResult, direction: Optional[str] = None
) -> Optional[float]:
    """구간 하나의 congestion_score. 도보 구간은 혼잡 개념이 없어 None(가중평균에서 제외).

    direction은 지하철 구간에서만 쓴다(direction.determine_direction()의 반환값을
    그대로 전달). 버스는 방향 개념이 없어 무시한다.
    """
    if mode == "walk":
        return None

    if not match.matched:
        return NEUTRAL_CONGESTION_SCORE

    if mode == "subway":
        weight = STATION_WEIGHT.get((match.station_id, direction))
        if weight is None:
            # direction=None(매칭 실패/판정 불가) 또는 그 방향의 행이 아직 없음 —
            # 둘 다 "값을 신뢰할 수 없음"이므로 동일하게 중립 처리(Q4 정책과 동일).
            return NEUTRAL_CONGESTION_SCORE
        base = min(weight.congestion_pct / SUBWAY_CONGESTION_DIVISOR, 1.0)
        return base * stop_sequence_discount(weight.stop_sequence)

    if mode == "bus":
        weight = BUS_WEIGHT.get(match.stop_id)
        if weight is None:
            return NEUTRAL_CONGESTION_SCORE
        base = min(weight.net_onboard / BUS_NET_ONBOARD_DIVISOR, 1.0)
        # bus_weight엔 아직 stop_sequence 컬럼이 없음(backend.md §7.2) — 있으면 여기도 감산 적용
        return base * stop_sequence_discount(weight.stop_sequence)

    return NEUTRAL_CONGESTION_SCORE


def score_candidate(segment_scores: list[tuple[int, float]]) -> float:
    """경로 전체 점수 = 구간 소요시간 가중평균 (Q1). segment_scores = [(duration_min, score), ...]."""
    total_duration = sum(duration for duration, _ in segment_scores)
    if total_duration == 0:
        return 0.0
    weighted_sum = sum(duration * score for duration, score in segment_scores)
    return weighted_sum / total_duration
