"""ODsay 응답(result.path[])을 내부 후보/구간 구조로 변환한다.

ODsay 실응답(`backend/tests/fixtures/odsay_sample_response.json`, 17개 후보,
래미안위브아파트→독산사거리, backend.md §10 데모 좌표와 동일 케이스)을 직접 뜯어서
확인한 구조 기준으로 작성함:

- subPath.trafficType: 1=지하철, 2=버스, 3=도보
- 좌표 필드는 ODsay 관례상 X=경도(lng), Y=위도(lat) — 순서 뒤집지 않도록 주의
- 도보 구간은 좌표 필드 자체가 없음 → fill_walk_coordinates()로 인접 구간에서 채워야 함
- 버스 구간의 startLocalStationID/endLocalStationID는 표준정류장ID로 확인됨
  (backend.md §7.3 — 서울시 노선 정류장마스터 CSV의 정류장_ID와 완전히 일치)
"""
from dataclasses import dataclass, field
from typing import Optional

TRAFFIC_TYPE_SUBWAY = 1
TRAFFIC_TYPE_BUS = 2
TRAFFIC_TYPE_WALK = 3

_MODE_BY_TRAFFIC_TYPE = {
    TRAFFIC_TYPE_SUBWAY: "subway",
    TRAFFIC_TYPE_BUS: "bus",
    TRAFFIC_TYPE_WALK: "walk",
}


@dataclass
class ParsedSegment:
    mode: str
    duration_min: int
    distance_m: int
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None

    # 지하철: ODsay 자체 내부 station id — 텅텅 DB station_id와 다른 체계라
    # matching.py에서 좌표(Q4: 100m 반경)로 재매칭해야 함
    odsay_station_id: Optional[int] = None

    # 버스: 표준정류장ID로 확인됨 — bus_stop.stop_std_id와 직접 매칭(반경 매칭 불필요)
    stop_std_id: Optional[str] = None

    route_id: Optional[str] = None
    station_name: Optional[str] = None


@dataclass
class ParsedCandidate:
    path_type_code: int
    total_time_min: int
    segments: list[ParsedSegment] = field(default_factory=list)

    @property
    def path_type(self) -> str:
        modes = {s.mode for s in self.segments if s.mode != "walk"}
        if modes == {"subway"}:
            return "subway"
        if modes == {"bus"}:
            return "bus"
        if modes == {"subway", "bus"}:
            return "subway+bus"
        return "walk"


def parse_odsay_result(raw: dict) -> list[ParsedCandidate]:
    """ODsay 원본 JSON(dict, 이미 파싱된 상태) → 내부 후보 리스트."""
    candidates: list[ParsedCandidate] = []
    for path in raw.get("result", {}).get("path", []):
        info = path.get("info", {})
        segments = [_parse_subpath(sp) for sp in path.get("subPath", [])]
        total_time = info.get("totalTime")
        if total_time is None:
            total_time = sum(s.duration_min for s in segments)
        candidates.append(
            ParsedCandidate(
                path_type_code=path.get("pathType", 0),
                total_time_min=total_time,
                segments=segments,
            )
        )
    return candidates


def _parse_subpath(sp: dict) -> ParsedSegment:
    traffic_type = sp.get("trafficType")
    mode = _MODE_BY_TRAFFIC_TYPE.get(traffic_type, "walk")
    segment = ParsedSegment(
        mode=mode,
        duration_min=sp.get("sectionTime", 0),
        distance_m=sp.get("distance", 0),
    )
    if mode == "walk":
        return segment  # 좌표 없음 — fill_walk_coordinates()로 후처리

    segment.start_lng = sp.get("startX")
    segment.start_lat = sp.get("startY")
    segment.end_lng = sp.get("endX")
    segment.end_lat = sp.get("endY")
    segment.station_name = sp.get("startName")

    lane = (sp.get("lane") or [{}])[0]
    if mode == "subway":
        # 세그먼트를 대표하는 station은 탑승역(시작역) 기준 — stop_sequence도 이 역 기준
        segment.odsay_station_id = sp.get("startID")
        subway_code = lane.get("subwayCode")
        segment.route_id = str(subway_code) if subway_code is not None else None
    elif mode == "bus":
        segment.stop_std_id = sp.get("startLocalStationID")
        bus_no = lane.get("busNo")
        bus_id = lane.get("busID")
        segment.route_id = bus_no or (str(bus_id) if bus_id is not None else None)

    return segment


def fill_walk_coordinates(
    segments: list[ParsedSegment],
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> None:
    """도보 구간의 시작/끝 좌표를 제자리에서(in-place) 채운다.

    ODsay가 도보 subPath엔 좌표를 안 주기 때문에, 인접한 지하철/버스 구간의 끝/시작 좌표를
    이어 붙이고, 맨 앞/뒤 도보 구간(출발지→첫 정류장, 마지막 정류장→도착지)은 요청에 들어온
    origin/destination으로 채운다. origin/destination은 (lat, lng) 순서.
    """
    for i, seg in enumerate(segments):
        if seg.mode != "walk":
            continue

        prev_seg = segments[i - 1] if i > 0 else None
        if prev_seg is not None and prev_seg.end_lat is not None:
            seg.start_lat, seg.start_lng = prev_seg.end_lat, prev_seg.end_lng
        else:
            seg.start_lat, seg.start_lng = origin

        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        if next_seg is not None and next_seg.start_lat is not None:
            seg.end_lat, seg.end_lng = next_seg.start_lat, next_seg.start_lng
        else:
            seg.end_lat, seg.end_lng = destination
