"""B(김창영)의 candidate_log.save_request()/save_candidates() 접점 함수 임시 자리표시자.

backend.md §3: B가 backend/app/services/candidate_log.py에 실제 구현을 올리면
search.py의 import만 그쪽으로 바꾸면 된다 (8/20 오전 통합 예정). 그 전까지는 DB 없이도
search.py가 동작하도록 여기서 아무것도 저장하지 않는 no-op으로 둔다.
"""
from typing import Any


def save_request(origin: Any, destination: Any) -> int:
    return 0


def save_candidates(request_id: int, candidates: list[dict]) -> None:
    pass
