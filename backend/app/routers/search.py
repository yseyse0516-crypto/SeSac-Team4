"""POST /api/v1/routes/search — 텅텅의 핵심 엔드포인트.

ODsay 1회 호출 → 좌표 매칭(Q4) → 혼잡 스코어링(Q1/Q3) → 분당개선 필터링(Q2) →
비교 응답(최단시간 vs 추천) 순서로 처리한다 (backend.md §3/§7).

담당: 정종우(A). main.py/core/*는 B 담당이라 여기서 건드리지 않는다 — 이 라우터는
B의 main.py가 `include_router(search.router)`로 등록할 예정.
"""
import os

from fastapi import APIRouter, HTTPException

from app.schemas.route import Candidate, Coordinate, SearchRequest, SearchResponse, Segment
from app.services import candidate_log_stub as candidate_log
from app.services import filtering, line_geometry, matching, scoring
from app.services.odsay_client import OdsayError, OdsayNoCandidateError, call_odsay
from app.services.odsay_parser import ParsedSegment, fill_walk_coordinates, parse_odsay_result

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.post("/search", response_model=SearchResponse)
def search_routes(payload: SearchRequest) -> SearchResponse:
    _validate_coordinates(payload)
    api_key = os.getenv("ODSAY_API_KEY")

    try:
        raw = call_odsay(
            payload.origin.lat,
            payload.origin.lng,
            payload.destination.lat,
            payload.destination.lng,
            api_key=api_key,
        )
    except OdsayNoCandidateError as exc:
        raise HTTPException(status_code=404, detail={"code": "NO_CANDIDATE"}) from exc
    except OdsayError as exc:
        raise HTTPException(status_code=502, detail={"code": "UPSTREAM_ERROR"}) from exc

    parsed_candidates = parse_odsay_result(raw)
    if not parsed_candidates:
        raise HTTPException(status_code=404, detail={"code": "NO_CANDIDATE"})

    origin_tuple = (payload.origin.lat, payload.origin.lng)
    destination_tuple = (payload.destination.lat, payload.destination.lng)

    scored_candidates: list[filtering.ScoredCandidate] = []
    for pc in parsed_candidates:
        fill_walk_coordinates(pc.segments, origin_tuple, destination_tuple)

        segment_scores: list[tuple[int, float]] = []
        response_segments: list[Segment] = []

        for seg in pc.segments:
            match = _match_segment(seg)
            seg_score = scoring.score_segment(seg.mode, match)
            if seg_score is not None:
                segment_scores.append((seg.duration_min, seg_score))

            polyline = None
            if seg.mode == "subway":
                curve = line_geometry.get_curve(
                    seg.route_id, seg.start_lat, seg.start_lng, seg.end_lat, seg.end_lng
                )
                if curve is not None:
                    polyline = [Coordinate(lat=lat, lng=lng) for lat, lng in curve]
            elif seg.mode == "bus":
                curve = line_geometry.get_bus_curve(
                    seg.route_id, seg.start_lat, seg.start_lng, seg.end_lat, seg.end_lng
                )
                if curve is not None:
                    polyline = [Coordinate(lat=lat, lng=lng) for lat, lng in curve]

            response_segments.append(
                Segment(
                    mode=seg.mode,
                    duration_min=seg.duration_min,
                    distance_m=seg.distance_m,
                    start=Coordinate(lat=seg.start_lat, lng=seg.start_lng),
                    end=Coordinate(lat=seg.end_lat, lng=seg.end_lng),
                    station_id=match.station_id,
                    stop_id=match.stop_id,
                    stop_std_id=seg.stop_std_id,
                    route_id=seg.route_id,
                    matched=match.matched,
                    polyline=polyline,
                )
            )

        congestion_score = round(scoring.score_candidate(segment_scores), 4)
        scored_candidates.append(
            filtering.ScoredCandidate(
                path_type=pc.path_type,
                total_time_min=pc.total_time_min,
                congestion_score=congestion_score,
                segments=response_segments,
            )
        )

    enriched, is_same = filtering.select_candidates(scored_candidates)

    request_id = candidate_log.save_request(payload.origin, payload.destination)

    response_candidates = [
        Candidate(
            id=i,
            path_type=e["candidate"].path_type,
            total_time_min=e["candidate"].total_time_min,
            congestion_score=e["candidate"].congestion_score,
            minute_improvement_ratio=e["minute_improvement_ratio"],
            is_recommended=e["is_recommended"],
            is_fastest=e["is_fastest"],
            segments=e["candidate"].segments,
        )
        for i, e in enumerate(enriched)
    ]

    candidate_log.save_candidates(
        request_id,
        [c.model_dump() for c in response_candidates],
    )

    return SearchResponse(request_id=request_id, candidates=response_candidates, is_same=is_same)


def _validate_coordinates(payload: SearchRequest) -> None:
    """400 INVALID_INPUT — 좌표 범위를 벗어나면 ODsay를 호출하기 전에 걸러낸다 (backend.md §5)."""
    for point in (payload.origin, payload.destination):
        if not (-90 <= point.lat <= 90) or not (-180 <= point.lng <= 180):
            raise HTTPException(status_code=400, detail={"code": "INVALID_INPUT"})


def _match_segment(seg: ParsedSegment) -> matching.MatchResult:
    if seg.mode == "subway":
        return matching.match_subway_station(seg.start_lat, seg.start_lng)
    if seg.mode == "bus":
        return matching.match_bus_stop(seg.stop_std_id)
    return matching.MatchResult(matched=False)
