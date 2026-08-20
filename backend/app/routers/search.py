"""POST /api/v1/routes/search — 텅텅의 핵심 엔드포인트.

ODsay 1회 호출 → 좌표 매칭(Q4) → 혼잡 스코어링(Q1/Q3) → 분당개선 필터링(Q2) →
비교 응답(최단시간 vs 추천) 순서로 처리한다 (backend.md §3/§7).

담당: 정종우(A). main.py/core/*는 B 담당이라 여기서 건드리지 않는다.

2026-08-20 수정(김재우, 초안 — A 리뷰 전): matching.py/scoring.py가 이제 DB 커서를
받으면 hardcoded_weights.py의 가짜 값 대신 실제 station/bus_stop/station_weight/
bus_weight를 조회한다(app/services/weight_repository.py). 이 라우터는 요청 하나당
커서 하나를 열어(db.get_cursor()) 모든 세그먼트 매칭·스코어링에 재사용한다.
departure_time이 요청에 없으면 now()를 기준 시각으로 쓴다.
"""
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core import db
from app.schemas.route import Candidate, Coordinate, SearchRequest, SearchResponse, Segment
from app.services import candidate_log
from app.services import direction as direction_service
from app.services import filtering, line_geometry, matching, scoring, walk_geometry
from app.services import weight_repository
from app.services.odsay_client import (
    OdsayError,
    OdsayNoCandidateError,
    OdsayQuotaExceededError,
    call_odsay,
)
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
    except OdsayQuotaExceededError as exc:
        raise HTTPException(status_code=503, detail={"code": "UPSTREAM_QUOTA_EXCEEDED"}) from exc
    except OdsayError as exc:
        raise HTTPException(status_code=502, detail={"code": "UPSTREAM_ERROR"}) from exc

    parsed_candidates = parse_odsay_result(raw)
    if not parsed_candidates:
        raise HTTPException(status_code=404, detail={"code": "NO_CANDIDATE"})

    origin_tuple = (payload.origin.lat, payload.origin.lng)
    destination_tuple = (payload.destination.lat, payload.destination.lng)
    # departure_time 없으면 지금 시각 기준으로 station_weight/bus_weight를 조회한다.
    dt = payload.departure_time or datetime.now()

    scored_candidates: list[filtering.ScoredCandidate] = []
    with db.get_cursor() as cur:
        for pc in parsed_candidates:
            fill_walk_coordinates(pc.segments, origin_tuple, destination_tuple)

            segment_scores: list[tuple[int, float]] = []
            response_segments: list[Segment] = []

            for seg in pc.segments:
                match, direction = _match_segment(seg, cur)
                seg_score = scoring.score_segment(
                    seg.mode, match, direction, cur=cur, dt=dt, route_id=seg.route_id
                )
                if seg_score is not None:
                    segment_scores.append((seg.duration_min, seg_score))

                stop_sequence = None
                if seg.mode == "subway" and match.station_id is not None:
                    # direction=None이면 어차피 그 조합의 행이 없으므로 stop_sequence도
                    # 자연히 None(중립)이 된다.
                    weight = weight_repository.get_station_weight(
                        cur, match.station_id, direction, dt
                    )
                    stop_sequence = weight["stop_sequence"] if weight else None
                elif seg.mode == "bus" and match.stop_id is not None:
                    weight = weight_repository.get_bus_weight(cur, match.stop_id, seg.route_id, dt)
                    stop_sequence = weight["stop_sequence"] if weight else None

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
                elif seg.mode == "walk":
                    curve = walk_geometry.get_walk_curve(
                        seg.start_lat, seg.start_lng, seg.end_lat, seg.end_lng
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
                        stop_sequence=stop_sequence,
                        matched=match.matched,
                        direction=direction,
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


def _match_segment(seg: ParsedSegment, cur=None) -> tuple[matching.MatchResult, Optional[str]]:
    """세그먼트를 매칭하고(Q4), 지하철이면 방향(direction.py)까지 계산해 함께 반환한다.

    응답에 쓰이는 대표 매칭 결과(station_id 등)는 지금까지와 동일하게 탑승역
    (시작역) 기준이다 — 하차역은 방향 계산에만 쓰고 별도로 노출하지 않는다.

    cur를 넘기면 matching.py가 실제 station/bus_stop 테이블을 조회한다(초안 —
    weight_repository.py 참고). cur=None이면 기존 하드코딩 fixture 경로를 탄다.
    """
    if seg.mode == "subway":
        start_match = matching.match_subway_station(seg.start_lat, seg.start_lng, cur)
        if not start_match.matched:
            return start_match, None
        end_match = matching.match_subway_station(seg.end_lat, seg.end_lng, cur)
        if not end_match.matched:
            return start_match, None
        direction = direction_service.determine_direction(
            start_match.line_name, start_match.station_no, end_match.station_no
        )
        return start_match, direction
    if seg.mode == "bus":
        return matching.match_bus_stop(seg.stop_std_id, cur), None
    return matching.MatchResult(matched=False), None
