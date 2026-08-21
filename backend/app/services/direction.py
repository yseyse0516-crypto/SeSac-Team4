"""station_weight 조회에 필요한 지하철 방향(상선/하선/내선/외선) 판정.

## 왜 필요한가

`station_weight`는 이제 같은 역·같은 시간대라도 방향이 다르면 값이 다른 행
2개가 존재한다(UNIQUE 키에 direction 포함, 01_schema.sql 2026-08-20 수정).
탑승역(station_id)만으로 조회하면 어느 방향 값을 써야 할지 결정할 수 없다.

## 규칙 (실측 검증 완료 — 텅텅_2호선재계산스크립트-2026_08_20생성.py,
   backend/app/batch/station_weight_sync.py와 동일 근거)

- 반경형 노선(1,3,4,5,6,7,8호선): station.station_no가 줄면 상행/상선, 늘면
  하행/하선 (getShtrmPath2 API의 upbdnbSe 필드로 예외 없이 확인됨).
- 2호선(순환): 201~243을 43개 역의 원형으로 보고, 오름차순 방향(243→201 순환
  포함)으로 더 가까우면 외선, 내림차순 방향(201→243 순환 포함)으로 더 가까우면
  내선 (getShtrmPath2 실제 11개 구간으로 검증됨).

## 알려진 예외 3가지 — 아래 각각 별도로 처리

1. **2호선 지선(성수지선/신정지선, 역번호 244~250)**: 원형 규칙이 적용되지
   않는 구간이라 이 모듈은 판정하지 않고 None을 반환한다(중립 처리 대상).
2. **1호선 동묘앞(159)·8호선 남위례**: 나중에 신설되며 번호를 새로 매기지
   않고 뒤에 붙여넣어 역번호 순서가 물리적 위치와 어긋나는 유일한 역이다
   (1호선: 155 동대문 - 159 동묘앞 - 156 신설동 순으로 물리적으로 위치,
   8호선: 2821 복정 - 2828 남위례 - 2822 산성 순). 이 두 노선은 역번호
   대소 비교 대신 실측 확인된 물리적 순서 리스트(_PHYS_ORDER_1/_PHYS_ORDER_8)로
   비교한다 — 이 리스트는 batch/station_weight_sync.py의 동일 상수와 정확히
   같은 근거(공식 KRIC 좌표 기준 실측)로 만들어졌으므로, 두 코드베이스가 서로
   다른 리스트를 쓰지 않도록 값이 바뀌면 반드시 함께 갱신해야 한다.
3. **5호선 트렁크+지선(하남검단산/마천)**: 별도 물리순서 리스트가 필요 없다.
   공식 KRIC 데이터로 실측 확인한 결과, 두 지선 모두 강동(2549) 기준으로
   바깥쪽으로 갈수록 역번호가 계속 커지도록 매겨져 있고 두 지선끼리 번호가
   섞이지 않는다 — 그래서 반경형 노선 공통 규칙(역번호 대소 비교)이 트렁크·
   지선 구분 없이 안전하게 그대로 통한다.

## 판정 불가 시 정책

None을 반환하는 모든 경우, 호출부(scoring.py)는 "판정 실패"를 "값이 없는
것"과 동일하게 취급해 중립값(NEUTRAL_CONGESTION_SCORE=0.5)을 적용해야 한다.
없는 값을 있는 것처럼 임의로 한쪽 방향을 골라 조회하면 안 된다(Q4 매칭 실패
정책과 동일).
"""
from typing import Optional

_LINE2_RING_START = 201
_LINE2_RING_END = 243
_LINE2_RING_SIZE = _LINE2_RING_END - _LINE2_RING_START + 1  # 43

# batch/app/batch/station_weight_sync.py의 _PHYS_ORDER_1 / _PHYS_ORDER_8와
# 반드시 동일하게 유지할 것 (공식 KRIC 좌표 기준 실측, 2026-08-20 확정).
_PHYS_ORDER_1 = ["150", "151", "152", "153", "154", "155", "159", "156", "157", "158"]
_PHYS_ORDER_8 = [
    "2810", "2811", "2812", "2813", "2814", "2815", "2816", "2817", "2818",
    "2819", "2820", "2821", "2828", "2822", "2823", "2824", "2825", "2826", "2827",
]
_PHYS_ORDER_BY_LINE = {"1호선": _PHYS_ORDER_1, "8호선": _PHYS_ORDER_8}


def determine_direction(
    line_name: Optional[str],
    start_station_no: Optional[str],
    end_station_no: Optional[str],
) -> Optional[str]:
    """탑승역(start)→하차역(end) station_no로 station_weight.direction 값을 계산한다.

    반환값은 '상선'/'하선'/'내선'/'외선' 중 하나이거나, 판정 불가 시 None이다.
    """
    if not line_name or start_station_no is None or end_station_no is None:
        return None
    if start_station_no == end_station_no:
        return None  # 시작=도착 — 방향 자체가 무의미(퇴화 케이스)

    if line_name == "2호선":
        return _direction_line2(start_station_no, end_station_no)

    order = _PHYS_ORDER_BY_LINE.get(line_name)
    if order is not None:
        return _direction_by_physical_order(order, start_station_no, end_station_no)

    return _direction_by_station_no(start_station_no, end_station_no)


def _direction_line2(start_no: str, end_no: str) -> Optional[str]:
    try:
        start_i, end_i = int(start_no), int(end_no)
    except (TypeError, ValueError):
        return None
    if not (_LINE2_RING_START <= start_i <= _LINE2_RING_END
            and _LINE2_RING_START <= end_i <= _LINE2_RING_END):
        return None  # 지선(244~250) — 알려진 예외 1, 판정하지 않음

    forward = (end_i - start_i) % _LINE2_RING_SIZE
    backward = (start_i - end_i) % _LINE2_RING_SIZE
    return "외선" if forward <= backward else "내선"


def _direction_by_physical_order(order: list[str], start_no: str, end_no: str) -> Optional[str]:
    if start_no not in order or end_no not in order:
        return None
    start_idx, end_idx = order.index(start_no), order.index(end_no)
    if end_idx > start_idx:
        return "하선"
    if end_idx < start_idx:
        return "상선"
    return None


def _direction_by_station_no(start_no: str, end_no: str) -> Optional[str]:
    try:
        start_i, end_i = int(start_no), int(end_no)
    except (TypeError, ValueError):
        return None
    if end_i > start_i:
        return "하선"
    if end_i < start_i:
        return "상선"
    return None
