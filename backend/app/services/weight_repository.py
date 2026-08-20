"""station/bus_stop 마스터, station_weight/bus_weight 실 데이터 조회 계층.

## 배경 (2026-08-20, 김재우)

`app/batch/`가 이제 station/bus_stop/station_weight/bus_weight에 실제 공공데이터를
채워 넣는다. 지금까지 matching.py/scoring.py는 이 테이블 대신
`hardcoded_weights.py`의 소수 하드코딩 값(로직 검증용 가짜 값, 파일 자체에 명시)을
써왔다 — 이 모듈은 그 자리를 실제 DB 조회로 대체하기 위한 계층이다.

⚠️ matching.py/scoring.py는 A(정종우) 전담 파일이라, 이 모듈과 그 연동 변경은
A 확인 전 초안(draft)이다. main 병합 전 반드시 A 리뷰를 받을 것.

## 조회 실패 시 정책

배치가 아직 안 돌았거나(batch_run에 success 행이 없음), 해당 역/구간·시간대·방향
조합의 행이 아직 없으면 전부 None을 반환한다. 값을 임의로 추정/대체하지 않고,
호출부(scoring.py)가 기존 Q4 매칭 실패 정책과 동일하게 중립값(0.5)을 적용하도록
맡긴다 — direction.py가 판정 불가 시 None을 반환하고 호출부가 중립 처리하는 것과
같은 원칙이다.

## time_slot 변환

station_weight/bus_weight 둘 다 시간당 버킷('HH:00-HH:00', batch/station_weight_sync.py
/batch/bus_weight_sync.py와 동일 포맷)을 쓴다. station_weight는 01:00~05:00 구간
버킷 자체가 없다(그 시간대는 지하철이 다니지 않아 원본 데이터에도 없음) — 이 경우
`time_slot_for()`가 만들어낸 문자열이 애초에 DB에 존재하지 않는 값이 되어, 쿼리가
자연히 빈 결과를 반환하고 그대로 중립 처리로 이어진다(별도 예외 처리 불필요).
"""
import math
from datetime import datetime
from typing import Optional

SUBWAY_MATCH_RADIUS_M = 100  # matching.py의 기존 반경 정책과 동일


def time_slot_for(dt: datetime) -> str:
    """dt를 station_weight/bus_weight의 time_slot 포맷으로 변환한다."""
    h = dt.hour
    return f"{h:02d}:00-{h + 1:02d}:00"


def latest_batch_id(cur) -> Optional[int]:
    """가장 최근에 성공한 배치의 batch_id. 아직 성공한 배치가 없으면 None."""
    cur.execute(
        "SELECT batch_id FROM batch_run WHERE status = 'success' ORDER BY batch_id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row["batch_id"] if row else None


def match_subway_station(cur, lat: Optional[float], lng: Optional[float]) -> Optional[dict]:
    """station 테이블에서 반경 SUBWAY_MATCH_RADIUS_M 이내 최근접 역을 찾는다.

    269개 규모라 전부 불러와 haversine으로 최근접을 찾아도 요청당 부담이 크지
    않다(PostGIS 등 확장 미사용 — CLAUDE.md §2 ORM 미사용 원칙과 같은 기조로,
    원시 SQL만으로 해결). 매칭 성공 시 station_id/line_name/station_no를 담은
    dict(row)를 반환하고, 실패 시 None을 반환한다.
    """
    if lat is None or lng is None:
        return None

    cur.execute("SELECT station_id, line_name, station_no, lat, lng FROM station")
    rows = cur.fetchall()

    nearest = None
    nearest_dist = SUBWAY_MATCH_RADIUS_M
    for row in rows:
        dist = _haversine_m(lat, lng, float(row["lat"]), float(row["lng"]))
        if dist <= nearest_dist:
            nearest, nearest_dist = row, dist
    return nearest


def match_bus_stop(cur, stop_std_id: Optional[str]) -> Optional[int]:
    """bus_stop.stop_std_id(=ODsay localStationID)로 stop_id를 직접 조회한다."""
    if not stop_std_id:
        return None
    cur.execute("SELECT stop_id FROM bus_stop WHERE stop_std_id = %s", (stop_std_id,))
    row = cur.fetchone()
    return row["stop_id"] if row else None


def get_station_weight(cur, station_id: int, direction: Optional[str], dt: datetime) -> Optional[dict]:
    """station_weight에서 (station_id, 최신 batch_id, direction, time_slot, dow)로 조회한다.

    direction이 None이면(매칭 실패/판정 불가) 애초에 조회를 시도하지 않는다 —
    scoring.py가 기존에 하드코딩 딕셔너리를 (station_id, direction)으로 조회할 때
    적용하던 것과 동일한 정책이다.
    """
    if direction is None:
        return None
    batch_id = latest_batch_id(cur)
    if batch_id is None:
        return None
    cur.execute(
        "SELECT congestion_pct, stop_sequence FROM station_weight "
        "WHERE station_id = %s AND batch_id = %s AND direction = %s "
        "AND time_slot = %s AND dow = %s",
        (station_id, batch_id, direction, time_slot_for(dt), dt.weekday()),
    )
    return cur.fetchone()


def get_bus_weight(cur, stop_id: int, route_id: Optional[str], dt: datetime) -> Optional[dict]:
    """bus_weight에서 (stop_id, route_id, 최신 batch_id, time_slot, dow)로 조회한다."""
    if not route_id:
        return None
    batch_id = latest_batch_id(cur)
    if batch_id is None:
        return None
    cur.execute(
        "SELECT net_onboard, stop_sequence FROM bus_weight "
        "WHERE stop_id = %s AND route_id = %s AND batch_id = %s "
        "AND time_slot = %s AND dow = %s",
        (stop_id, route_id, batch_id, time_slot_for(dt), dt.weekday()),
    )
    return cur.fetchone()


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_m = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))
