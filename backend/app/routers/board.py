"""커뮤니티 게시판 CRUD 라우터 (backend.md §12).

로그인이 없어서(CLAUDE.md §4) X-Client-Token(프론트가 생성해 들고 있는 UUID — 쿠폰
기능과 동일한 값을 재사용해도 됨)으로 작성자를 식별한다. 작성 시 헤더가 없으면 400,
수정/삭제 시 글 작성자의 토큰과 다르면 403.
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.board import PostCreate, PostListOut, PostOut, PostUpdate
from app.services import board_service

router = APIRouter(prefix="/api/v1/board", tags=["board"])


def _require_client_token(x_client_token: Optional[str]) -> str:
    if not x_client_token:
        raise HTTPException(status_code=400, detail={"code": "MISSING_CLIENT_TOKEN"})
    return x_client_token


def _to_post_out(post: board_service.Post) -> PostOut:
    return PostOut(
        id=post.id,
        nickname=post.nickname,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.post("/posts", response_model=PostOut, status_code=201)
def create_post(
    payload: PostCreate, x_client_token: Optional[str] = Header(default=None)
) -> PostOut:
    token = _require_client_token(x_client_token)
    post = board_service.create_post(payload.nickname, payload.content, token)
    return _to_post_out(post)


@router.get("/posts", response_model=PostListOut)
def list_posts(
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)
) -> PostListOut:
    posts = board_service.list_posts(limit=limit, offset=offset)
    return PostListOut(posts=[_to_post_out(p) for p in posts], total=board_service.count_posts())


@router.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int) -> PostOut:
    try:
        post = board_service.get_post(post_id)
    except board_service.PostNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND"})
    return _to_post_out(post)


@router.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    payload: PostUpdate,
    x_client_token: Optional[str] = Header(default=None),
) -> PostOut:
    token = _require_client_token(x_client_token)
    try:
        post = board_service.update_post(post_id, payload.content, token)
    except board_service.PostNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND"})
    except board_service.NotPostOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_POST_OWNER"})
    return _to_post_out(post)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, x_client_token: Optional[str] = Header(default=None)) -> None:
    token = _require_client_token(x_client_token)
    try:
        board_service.delete_post(post_id, token)
    except board_service.PostNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND"})
    except board_service.NotPostOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_POST_OWNER"})
