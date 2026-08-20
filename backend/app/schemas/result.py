from pydantic import BaseModel


class RouteCandidate(BaseModel):
    path_type: str
    total_time_min: float
    congestion_score: float | None = None
    minute_improvement_ratio: float | None = None
    is_recommended: bool
    is_fastest: bool = False


class RouteResult(BaseModel):
    request_id: int
    candidates: list[RouteCandidate]
