from fastapi import APIRouter, HTTPException

from app.core import db
from app.schemas.result import RouteCandidate, RouteResult

router = APIRouter(tags=["result"])


@router.get("/routes/{request_id}", response_model=RouteResult)
def get_route_result(request_id: int) -> RouteResult:
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT request_id FROM route_request WHERE request_id = %s",
            (request_id,),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="NO_CANDIDATE")

        cur.execute(
            "SELECT path_type, total_time_min, congestion_score, "
            "minute_improvement_ratio, is_recommended "
            "FROM route_candidate WHERE request_id = %s ORDER BY candidate_id",
            (request_id,),
        )
        rows = cur.fetchall()

    return RouteResult(
        request_id=request_id,
        candidates=[RouteCandidate(**row) for row in rows],
    )
