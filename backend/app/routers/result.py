import json

from fastapi import APIRouter, HTTPException

from app.core.redis import get_client
from app.schemas.result import RouteCandidate, RouteResult
from app.services.candidate_log import request_key

router = APIRouter(tags=["result"])


@router.get("/routes/{request_id}", response_model=RouteResult)
def get_route_result(request_id: int) -> RouteResult:
    raw = get_client().get(request_key(request_id))
    if raw is None:
        raise HTTPException(status_code=404, detail="NO_CANDIDATE")

    candidates = json.loads(raw)["candidates"]
    return RouteResult(
        request_id=request_id,
        candidates=[RouteCandidate(**c) for c in candidates],
    )
