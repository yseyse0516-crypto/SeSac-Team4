"""지하철/버스 segment(시작~끝) 사이의 실제 선로·도로 곡선을 잘라서 돌려준다.

지하철(get_curve)과 버스(get_bus_curve)는 데이터를 "언제 가져오느냐"가 다르다 — 노선 수
차이 때문이다 (backend.md §6.1/§6.3):

- 지하철: 수도권 전체 25개 노선뿐이라 미리 다 받아 backend/app/data/subway_lines.geojson으로
  저장해두고 서버 시작 후 첫 호출 때 한 번만 읽는다(_load_merged_lines, lru_cache).
- 버스: 수도권 전체로 치면 노선(관계 기준) 수가 지하철의 8~9배(약 1,588개)라 미리 다 받는 건
  시간·용량·Overpass 공유서버 부담이 너무 크다(실측: relation 8.8배/way 15.7배/node 8.2배,
  2026-08-19 count 조회로 확인). 대신 실제 요청에 등장한 노선번호만 그때 Overpass에 물어보고
  (get_bus_curve), 프로세스 메모리에 캐싱해서 같은 노선 재요청 시 네트워크 호출 없이 재사용한다.

둘 다 최종적으로는 같은 방식(_cut_curve)으로 자른다 — 노선 조각들을 하나의 연속된
LineString으로 합친 뒤(linemerge), 그 위에 시작/끝 좌표를 투영해서 그 사이 구간만
잘라낸다(shapely.ops.substring).

route_id가 실제 노선과 못 맞는 경우(지하철: 신분당선처럼 비숫자인 노선 / 버스: busNo가
비어서 ODsay 내부 busID로 대체된 경우)는 좌표 기반 최근접 탐색으로 대체한다. 최종적으로
"시작/끝 좌표가 그 노선에서 얼마나 가까운가"를 검증하기 때문에, route_id 매칭이 틀리거나
없어도 결과 정확도 자체는 떨어지지 않는다(느려지기만 함).
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import httpx
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring

_GEOJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "subway_lines.geojson"

# 정차역 좌표(ODsay)가 실제 선로 중심선과 이 정도까지 떨어져 있을 수 있다고 보고 넉넉히 잡은
# 매칭 허용 거리(m) — Q4의 역 매칭 반경(100m)보다 크게 잡음(역 입출구 좌표 오차 추가 고려).
MAX_PROJECTION_DISTANCE_M = 300

# 위경도 degree 단위 거리를 미터로 바꾸는 대략적인 환산 — 서울 위도 기준 근사치라 정밀하진
# 않지만, "이 노선이 명백히 아니다"를 걸러내는 필터 용도라 이 정도 오차는 문제 없음.
_METERS_PER_DEGREE = 111_320

# 버스 노선 실시간 조회(get_bus_curve) 전용 — 지하철과 달리 정적 파일이 없다.
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

# 지하철 노선 수집 때와 동일한 수도권 범위 (backend.md §6.1) — 다른 지역의 동일
# 노선번호 버스가 잡히는 걸 막기 위한 스코프.
SEOUL_BBOX = "36.95,126.55,37.85,127.35"

# route_ref(ODsay busNo) -> 병합된 LineString 후보 리스트. 노선 하나당 최초 요청 때만
# Overpass를 호출하고 그 뒤엔 서버가 떠 있는 동안 재사용한다. 조회 실패/노선 없음도 빈
# 리스트로 캐싱해서 같은 실패를 매 요청마다 반복 조회하지 않는다(음성 캐싱).
# TODO(8/20 오전 A·B 통합 후): core/redis.py(B)가 붙으면 이 프로세스 캐시를 Redis로
# 옮겨서 재시작/다중 인스턴스 사이에도 공유되게 한다 (backend.md §6.3).
_bus_curve_cache: dict[str, list] = {}


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

    candidates = []
    if route_id and route_id.isdigit() and route_id in merged:
        candidates = merged[route_id]
    else:
        for pieces in merged.values():
            candidates.extend(pieces)

    return _cut_curve(candidates, start_lat, start_lng, end_lat, end_lng)


def _fetch_bus_line(route_ref: str) -> list:
    """Overpass에서 route_ref(예: "504")번 버스 노선을 실시간으로 가져와 병합한다.
    실패하면 예외를 던진다 — 캐싱/폴백은 호출부(get_bus_curve)에서 처리한다."""
    query = (
        "[out:json][timeout:25];"
        f'relation["route"="bus"]["ref"="{route_ref}"]({SEOUL_BBOX});'
        "(._;>;);"
        "out geom;"
    )
    response = httpx.post(OVERPASS_ENDPOINT, data={"data": query}, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    ways = [
        el
        for el in data.get("elements", [])
        if el.get("type") == "way" and el.get("geometry")
    ]
    if not ways:
        return []

    lines = [LineString([(pt["lon"], pt["lat"]) for pt in w["geometry"]]) for w in ways]
    merged = linemerge(lines)
    return [merged] if merged.geom_type == "LineString" else list(merged.geoms)


def get_bus_curve(
    route_ref: Optional[str],
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> Optional[list]:
    """ODsay busNo(=route_ref)로 Overpass에서 실시간으로 노선을 가져와 구간을 잘라 반환.
    지하철과 달리 미리 받아두지 않으므로, 처음 등장하는 노선번호는 Overpass 왕복 시간만큼
    이 호출이 느려진다 — 이후 같은 노선은 프로세스 캐시(_bus_curve_cache)에서 즉시 반환된다."""
    if not route_ref:
        return None

    if route_ref not in _bus_curve_cache:
        try:
            _bus_curve_cache[route_ref] = _fetch_bus_line(route_ref)
        except (httpx.HTTPError, ValueError, KeyError):
            _bus_curve_cache[route_ref] = []

    candidates = _bus_curve_cache[route_ref]
    if not candidates:
        return None

    return _cut_curve(candidates, start_lat, start_lng, end_lat, end_lng)


def _cut_curve(
    candidates: list,
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> Optional[list]:
    """LineString 후보들 중 start/end에 가장 가까운 노선을 찾아 그 사이 구간만 잘라 반환.
    get_curve(지하철·정적 파일)와 get_bus_curve(버스·Overpass 실시간)가 공유하는 핵심 로직."""
    start_pt = Point(start_lng, start_lat)
    end_pt = Point(end_lng, end_lat)

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
