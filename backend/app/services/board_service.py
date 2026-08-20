"""커뮤니티 게시판 CRUD.

작성자 식별은 로그인 계정의 user_id로 한다.
"""
from dataclasses import dataclass
from datetime import datetime

from app.core import db

_POST_COLUMNS = "post_id AS id, nickname, content, owner_user_id, created_at, updated_at"


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


def _row_to_post(row: dict) -> Post:
    return Post(
        id=row["id"],
        nickname=row["nickname"],
        content=row["content"],
        owner_user_id=row["owner_user_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_post(nickname: str, content: str, owner_user_id: int) -> Post:
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO board_post (owner_user_id, nickname, content) VALUES (%s, %s, %s)",
            (owner_user_id, nickname, content),
        )
        cur.execute(f"SELECT {_POST_COLUMNS} FROM board_post WHERE post_id = lastval()")
        return _row_to_post(cur.fetchone())


def list_posts(limit: int = 20, offset: int = 0) -> list[Post]:
    with db.get_cursor() as cur:
        cur.execute(
            f"SELECT {_POST_COLUMNS} FROM board_post ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return [_row_to_post(row) for row in cur.fetchall()]


def count_posts() -> int:
    with db.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM board_post")
        return cur.fetchone()["n"]


def get_post(post_id: int) -> Post:
    with db.get_cursor() as cur:
        cur.execute(f"SELECT {_POST_COLUMNS} FROM board_post WHERE post_id = %s", (post_id,))
        row = cur.fetchone()
    if row is None:
        raise PostNotFoundError(post_id)
    return _row_to_post(row)


def update_post(post_id: int, content: str, owner_user_id: int) -> Post:
    post = get_post(post_id)
    if post.owner_user_id != owner_user_id:
        raise NotPostOwnerError(post_id)
    with db.get_cursor() as cur:
        cur.execute(
            "UPDATE board_post SET content = %s, updated_at = now() WHERE post_id = %s",
            (content, post_id),
        )
    return get_post(post_id)


def delete_post(post_id: int, owner_user_id: int) -> None:
    post = get_post(post_id)
    if post.owner_user_id != owner_user_id:
        raise NotPostOwnerError(post_id)
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM board_post WHERE post_id = %s", (post_id,))
