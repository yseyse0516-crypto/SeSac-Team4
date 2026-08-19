"""지하철 segment(시작역~끝역) 사이의 실제 선로 곡선을 잘라서 돌려준다.

데이터: backend/app/data/subway_lines.geojson (OpenStreetMap 수집, 2026-08-19,
backend.md §6.1 참고). 노선마다 짧은 way 단위로 쪼개져 있어서, 먼저 노선별로
하나의 연속된 LineString으로 합친 뒤(linemerge), 그 위에 시작/끝 좌표를 투영해서
그 사이 구간만 잘라낸다(shapely.ops.substring).

route_id(ODsay subwayCode)가 1~9 숫자면 노선 번호와 바로 매칭되지만, 신분당선·
수인분당선·GTX-A처럼 비숫자인 노선은 ODsay가 실제로 이 값을 뭐라고 주는지 아직
샘플로 확인 못 했다 — 이 경우 좌표 기반 최근접 노선 탐색으로 대체한다. 두 경로 다
최종적으로 "시작/끝 좌표가 그 노선에서 얼마나 가까운가"를 검증하기 때문에, route_id
매칭이 틀리거나 없어도 결과 정확도 자체는 떨어지지 않는다(느려지기만 함).

버스는 대상이 아니다 — 이번엔 지하철 탭 요청만 있었어서 범위를 좁혔다. 버스도 필요해지면
같은 방식(OSM route=bus 관계)으로 확장 가능.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring

_GEOJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "subway_lines.geojson"

# 정차역 좌표(ODsay)가 실제 선로 중심선과 이 정도까지 떨어져 있을 수 있다고 보고 넉넉히 잡은
# 매칭 허용 거리(m) — Q4의 역 매칭 반경(100m)보다 크게 잡음(역 입출구 좌표 오차 추가 고려).
MAX_PROJECTION_DISTANCE_M = 300

# 위경도 degree 단위 거리를 미터로 바꾸는 대략적인 환산 — 서울 위도 기준 근사치라 정밀하진
# 않지만, "이 노선이 명백히 아니다"를 걸러내는 필터 용도라 이 정도 오차는 문제 없음.
_METERS_PER_DEGREE = 111_320


@lru_cache(maxsize=1)
def _load_merged_lines() -> dict:
    with open(_GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    pieces_by_ref: dict = {}
    for feature in geojson["features"]:
        ref = feature["properties"]["line_ref"]
        coords = feature["geometry"]["coordinates"]  # [[lng, lat], ...]
        pieces_by_ref.setdefault(ref, []).append(LineString(coords))

    merged: dict = {}
    for ref, pieces in pieces_by_ref.items():
        result = linemerge(pieces)
        merged[ref] = [result] if result.geom_type == "LineString" else list(result.geoms)
    return merged


def _distance_m(line: LineString, point: Point) -> float:
    return line.distance(point) * _METERS_PER_DEGREE


def get_curve(
    route_id: Optional[str],
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> Optional[list]:
    """시작역~끝역 사이 실제 선로 곡선을 [(lat, lng), ...]로 반환. 매칭 실패 시 None
    (프론트는 None이면 기존처럼 start/end를 직선으로 이어서 그리면 됨)."""
    merged = _load_merged_lines()
    start_pt = Point(start_lng, start_lat)
    end_pt = Point(end_lng, end_lat)

    candidates = []
    if route_id and route_id.isdigit() and route_id in merged:
        candidates = merged[route_id]
    else:
        for pieces in merged.values():
            candidates.extend(pieces)

    best_line, best_score = None, None
    for line in candidates:
        d_start = _distance_m(line, start_pt)
        d_end = _distance_m(line, end_pt)
        if d_start > MAX_PROJECTION_DISTANCE_M or d_end > MAX_PROJECTION_DISTANCE_M:
            continue
        score = d_start + d_end
        if best_score is None or score < best_score:
            best_line, best_score = line, score

    if best_line is None:
        return None

    start_dist = best_line.project(start_pt)
    end_dist = best_line.project(end_pt)
    if start_dist == end_dist:
        return None
    lo, hi = min(start_dist, end_dist), max(start_dist, end_dist)

    try:
        sub = substring(best_line, lo, hi)
    except Exception:
        return None

    if sub.is_empty or sub.geom_type != "LineString":
        return None

    coords = [(lat, lng) for lng, lat in sub.coords]

    # substring()은 항상 lo->hi 순서로 좌표를 내놓는데, 원래 진행 방향(start->end)과
    # 반대일 수 있어서 실제 이동 방향에 맞게 뒤집어준다 (렌더링엔 영향 없지만 일관성 위해).
    first, last = coords[0], coords[-1]
    dist_first_to_start = (first[0] - start_lat) ** 2 + (first[1] - start_lng) ** 2
    dist_last_to_start = (last[0] - start_lat) ** 2 + (last[1] - start_lng) ** 2
    if dist_last_to_start < dist_first_to_start:
        coords.reverse()

    return coords
