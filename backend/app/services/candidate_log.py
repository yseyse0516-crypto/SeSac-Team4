from app.core.db import get_cursor


def save_request(origin, destination) -> int:
    """route_request INSERT → request_id 반환. 좌표는 소수점 3자리 절삭(N-04, 약 100m 격자).

    origin/destination은 lat/lng 속성을 가진 객체를 받는다 — A의 /search가
    `candidate_log.save_request(payload.origin, payload.destination)`처럼 스키마 객체를
    그대로 넘기므로(backend/app/routers/search.py), 위경도를 낱개 인자로 받지 않는다.
    """
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO route_request (origin_lat, origin_lng, dest_lat, dest_lng) "
            "VALUES (trunc(%(origin_lat)s::numeric, 3), trunc(%(origin_lng)s::numeric, 3), "
            "trunc(%(dest_lat)s::numeric, 3), trunc(%(dest_lng)s::numeric, 3))",
            {
                "origin_lat": origin.lat,
                "origin_lng": origin.lng,
                "dest_lat": destination.lat,
                "dest_lng": destination.lng,
            },
        )
        cur.execute("SELECT lastval() AS request_id")
        return cur.fetchone()["request_id"]


def save_candidates(request_id: int, candidates: list[dict]) -> None:
    """route_candidate 일괄 INSERT.

    candidates 각 항목 필수 키: path_type, total_time_min, congestion_score,
    minute_improvement_ratio, is_recommended
    """
    if not candidates:
        return
    with get_cursor() as cur:
        cur.executemany(
            "INSERT INTO route_candidate "
            "(request_id, path_type, total_time_min, congestion_score, "
            "minute_improvement_ratio, is_recommended) "
            "VALUES (%(request_id)s, %(path_type)s, %(total_time_min)s, "
            "%(congestion_score)s, %(minute_improvement_ratio)s, %(is_recommended)s)",
            [
                {
                    "request_id": request_id,
                    "path_type": c["path_type"],
                    "total_time_min": c["total_time_min"],
                    "congestion_score": c.get("congestion_score"),
                    "minute_improvement_ratio": c.get("minute_improvement_ratio"),
                    "is_recommended": c["is_recommended"],
                }
                for c in candidates
            ],
        )
