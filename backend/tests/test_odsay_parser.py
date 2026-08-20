import json
from pathlib import Path

from app.services.odsay_parser import fill_walk_coordinates, parse_odsay_result

FIXTURE = Path(__file__).resolve().parents[1] / "app" / "data" / "odsay_sample_response.json"


def _load_raw():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_parses_all_17_candidates_from_sample():
    candidates = parse_odsay_result(_load_raw())
    assert len(candidates) == 17


def test_subway_segment_fields():
    candidates = parse_odsay_result(_load_raw())
    subway_segments = [
        seg for c in candidates for seg in c.segments if seg.mode == "subway"
    ]
    assert subway_segments, "샘플에 지하철 구간이 있어야 함"

    seg = subway_segments[0]
    assert seg.odsay_station_id is not None
    assert seg.start_lat is not None and seg.start_lng is not None
    assert seg.stop_std_id is None  # 지하철은 표준정류장ID 개념 없음


def test_bus_segment_has_stop_std_id():
    candidates = parse_odsay_result(_load_raw())
    bus_segments = [seg for c in candidates for seg in c.segments if seg.mode == "bus"]
    assert bus_segments, "샘플에 버스 구간이 있어야 함"

    seg = bus_segments[0]
    assert seg.stop_std_id is not None
    assert seg.odsay_station_id is None


def test_walk_segments_have_no_coordinates_before_stitching():
    candidates = parse_odsay_result(_load_raw())
    walk_segments = [seg for c in candidates for seg in c.segments if seg.mode == "walk"]
    assert walk_segments
    assert all(seg.start_lat is None for seg in walk_segments)


def test_fill_walk_coordinates_stitches_from_neighbors_and_endpoints():
    candidates = parse_odsay_result(_load_raw())
    origin = (37.5012, 127.0396)
    destination = (37.4784, 126.8874)

    for c in candidates:
        fill_walk_coordinates(c.segments, origin, destination)
        for seg in c.segments:
            assert seg.start_lat is not None
            assert seg.end_lat is not None

        # 첫 구간이 도보라면 origin에서 시작해야 함
        if c.segments[0].mode == "walk":
            assert c.segments[0].start_lat == origin[0]
            assert c.segments[0].start_lng == origin[1]

        # 마지막 구간이 도보라면 destination에서 끝나야 함
        if c.segments[-1].mode == "walk":
            assert c.segments[-1].end_lat == destination[0]
            assert c.segments[-1].end_lng == destination[1]


def test_path_type_combines_modes():
    candidates = parse_odsay_result(_load_raw())
    path_types = {c.path_type for c in candidates}
    # 샘플은 subwayCount=0, busCount=10, subwayBusCount=7 → bus 단독 + subway+bus 조합만 존재
    assert "bus" in path_types
    assert "subway+bus" in path_types
    assert "subway" not in path_types
