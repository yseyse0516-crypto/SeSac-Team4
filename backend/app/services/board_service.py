"""커뮤니티 게시판 CRUD.

⚠️ 임시 구현 — 서버 프로세스 메모리에만 저장한다(재시작하면 게시글이 사라짐). B의
core/db.py(PostgreSQL 커넥션 풀)가 붙으면 이 파일 내부만 실제 SQL(psycopg, raw SQL,
파라미터 바인딩)로 교체하면 된다 — 라우터/스키마는 이미 그 형태를 가정하고 만들어서
바뀔 필요 없음 (backend.md §11/§12 참고).

작성자 식별은 로그인 계정의 user_id로 한다(2026-08-19 저녁부터 — 그 전엔 X-Client-Token
익명 토큰 방식이었으나 로그인 기능 추가로 대체됨, §12 참고).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count


@dataclass
class Post:
    id: int
    nickname: str
    content: str
    owner_user_id: int
    created_at: datetime
    updated_at: datetime


class PostNotFoundError(Exception):
    pass


class NotPostOwnerError(Exception):
    pass


_posts: dict[int, Post] = {}
_next_id = count(1)


def create_post(nickname: str, content: str, owner_user_id: int) -> Post:
    now = datetime.now(timezone.utc)
    post = Post(
        id=next(_next_id),
        nickname=nickname,
        content=content,
        owner_user_id=owner_user_id,
        created_at=now,
        updated_at=now,
    )
    _posts[post.id] = post
    return post


def list_posts(limit: int = 20, offset: int = 0) -> list[Post]:
    ordered = sorted(_posts.values(), key=lambda p: p.created_at, reverse=True)
    return ordered[offset : offset + limit]


def count_posts() -> int:
    return len(_posts)


def get_post(post_id: int) -> Post:
    post = _posts.get(post_id)
    if post is None:
        raise PostNotFoundError(post_id)
    return post


def update_post(post_id: int, content: str, owner_user_id: int) -> Post:
    post = get_post(post_id)
    if post.owner_user_id != owner_user_id:
        raise NotPostOwnerError(post_id)
    post.content = content
    post.updated_at = datetime.now(timezone.utc)
    return post


def delete_post(post_id: int, owner_user_id: int) -> None:
    post = get_post(post_id)
    if post.owner_user_id != owner_user_id:
        raise NotPostOwnerError(post_id)
    del _posts[post_id]
