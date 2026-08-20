"""POST /routes/search 요청/응답 스키마.

API 명세 출처: backend.md §5.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["walk", "subway", "bus"]


class Coordinate(BaseModel):
    lat: float
    lng: float


class SearchRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    departure_time: Optional[datetime] = None


class Segment(BaseModel):
    mode: Mode
    duration_min: int
    distance_m: int
    start: Coordinate
    end: Coordinate

    # 매칭 결과 (Q4) — 매칭 실패 시 station_id/stop_id는 None, matched=False, 중립값 0.5 적용됨
    station_id: Optional[int] = None
    stop_id: Optional[int] = None
    stop_std_id: Optional[str] = None
    route_id: Optional[str] = None
    stop_sequence: Optional[int] = None
    matched: bool = True

    # 지하철·버스·도보 구간의 실제 경로 곡선 (backend.md §6.1~§6.3, §13 — 도보는 Tmap
    # 키 발급 후 반영). None이면 매칭 실패/키 미설정/조회 실패 — 프론트는 이 경우
    # start/end를 직선으로 이어서 그리면 됨.
    polyline: Optional[list[Coordinate]] = None


class Candidate(BaseModel):
    id: int
    path_type: str
    total_time_min: int
    congestion_score: float
    minute_improvement_ratio: float
    is_recommended: bool
    is_fastest: bool
    segments: list[Segment]


class SearchResponse(BaseModel):
    request_id: int
    candidates: list[Candidate]
    is_same: bool = Field(
        default=False,
        description="최단시간 후보와 추천 후보가 동일한 경로인지 (backend.md §10 데모 처리)",
    )
