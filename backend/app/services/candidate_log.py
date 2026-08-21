import json

from app.core.redis import get_client

# 즐겨찾기(favorites)가 "영구 보관"을 전담하므로, 검색 결과 재조회는 짧은 TTL만 허용한다.
# TTL이 지나면 GET /routes/{request_id}는 404를 반환한다(즐겨찾기하지 않은 결과는 재현 불가 — 의도된 동작).
_TTL_SECONDS = 3600
_SEQ_KEY = "route:request:seq"


def request_key(request_id: int) -> str:
    return f"route:request:{request_id}"


def save_request(origin, destination) -> int:
    """요청 ID를 발급하고 빈 후보 목록으로 예약한다.

    origin/destination은 저장하지 않는다(N-04) — search.py와의 인터페이스를
    유지하려고 인자는 그대로 받되, 스코어링 이후엔 버린다.
    """
    r = get_client()
    request_id = r.incr(_SEQ_KEY)
    r.set(request_key(request_id), json.dumps({"candidates": []}), ex=_TTL_SECONDS)
    return request_id


def save_candidates(request_id: int, candidates: list[dict]) -> None:
    """예약된 요청 레코드에 후보 목록을 채운다.

    candidates 각 항목 필수 키: path_type, total_time_min, congestion_score,
    minute_improvement_ratio, is_recommended, is_fastest
    """
    if not candidates:
        return
    r = get_client()
    key = request_key(request_id)
    ttl = r.ttl(key)
    payload = {
        "candidates": [
            {
                "path_type": c["path_type"],
                "total_time_min": c["total_time_min"],
                "congestion_score": c.get("congestion_score"),
                "minute_improvement_ratio": c.get("minute_improvement_ratio"),
                "is_recommended": c["is_recommended"],
                "is_fastest": c.get("is_fastest", False),
            }
            for c in candidates
        ]
    }
    r.set(key, json.dumps(payload), ex=ttl if ttl and ttl > 0 else _TTL_SECONDS)
