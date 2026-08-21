"""Q4 — ODsay 좌표를 텅텅 DB의 station_id/stop_id로 매칭한다.

지하철: ODsay의 stationID가 자체 내부 체계라 좌표 반경(100m) 매칭 필요.
버스: ODsay의 localStationID가 표준정류장ID(stop_std_id)와 일치함을 확인했으므로
      (backend.md §7.3) 반경 매칭 없이 ID 직접 매칭.
매칭 실패 시 matched=False — scoring.py에서 중립값(0.5)을 적용한다.

2026-08-20 수정(김재우, 초안 — A 리뷰 전): cur(DB 커서)를 넘기면 hardcoded_weights.py의
가짜 값 대신 weight_repository.py를 통해 실제 station/bus_stop 테이블을 조회한다.
cur를 넘기지 않으면(기존 단위 테스트 호출 방식) 지금까지처럼 하드코딩된 소수
fixture로 동작한다 — 기존 단위 테스트를 깨지 않기 위한 선택이다. 실제 요청 처리
경로(search.py)는 항상 cur를 넘긴다.
"""
import math
from dataclasses import dataclass
from typing import Optional

from app.services import weight_repository
from app.services.hardcoded_weights import BUS_STOP_MASTER, STATION_MASTER

SUBWAY_MATCH_RADIUS_M = 100


@dataclass
class MatchResult:
    matched: bool
    station_id: Optional[int] = None
    stop_id: Optional[int] = None
    # 2026-08-20 수정: direction.determine_direction() 계산에 필요해서 추가.
    # 지하철 매칭 성공 시에만 채워짐(버스는 방향 개념이 없어 항상 None).
    line_name: Optional[str] = None
    station_no: Optional[str] = None


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_m = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def match_subway_station(
    lat: Optional[float], lng: Optional[float], cur=None
) -> MatchResult:
    if lat is None or lng is None:
        return MatchResult(matched=False)

    if cur is not None:
        row = weight_repository.match_subway_station(cur, lat, lng)
        if row is None:
            return MatchResult(matched=False)
        return MatchResult(
            matched=True,
            station_id=row["station_id"],
            line_name=row["line_name"],
            station_no=row["station_no"],
        )

    # cur 미제공 시 기존 하드코딩 fixture 기반 매칭 (단위 테스트 전용 경로)
    nearest: Optional[object] = None
    nearest_dist = SUBWAY_MATCH_RADIUS_M
    for st in STATION_MASTER:
        dist = _haversine_m(lat, lng, st.lat, st.lng)
        if dist <= nearest_dist:
            nearest, nearest_dist = st, dist

    if nearest is None:
        return MatchResult(matched=False)
    return MatchResult(
        matched=True,
        station_id=nearest.station_id,
        line_name=nearest.line_name,
        station_no=nearest.station_no,
    )


def match_bus_stop(stop_std_id: Optional[str], cur=None) -> MatchResult:
    if not stop_std_id:
        return MatchResult(matched=False)

    if cur is not None:
        stop_id = weight_repository.match_bus_stop(cur, stop_std_id)
        if stop_id is None:
            return MatchResult(matched=False)
        return MatchResult(matched=True, stop_id=stop_id)

    stop = BUS_STOP_MASTER.get(stop_std_id)
    if stop is None:
        return MatchResult(matched=False)
    return MatchResult(matched=True, stop_id=stop.stop_id)
