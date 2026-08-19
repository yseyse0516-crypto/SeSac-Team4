"""커뮤니티 게시판 CRUD 라우터 (backend.md §11/§12).

목록/상세 조회는 비회원도 가능(공개 게시판). 작성/수정/삭제는 로그인 필요 —
`auth_service.get_current_user`가 401 LOGIN_REQUIRED를 던지면 프론트가 "로그인이
필요한 서비스입니다" + 회원가입 화면 안내로 처리한다.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.board import PostCreate, PostListOut, PostOut, PostUpdate
from app.services import auth_service, board_service

router = APIRouter(prefix="/api/v1/board", tags=["board"])


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
    payload: PostCreate,
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> PostOut:
    post = board_service.create_post(current_user.nickname, payload.content, current_user.id)
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
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> PostOut:
    try:
        post = board_service.update_post(post_id, payload.content, current_user.id)
    except board_service.PostNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND"})
    except board_service.NotPostOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_POST_OWNER"})
    return _to_post_out(post)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> None:
    try:
        board_service.delete_post(post_id, current_user.id)
    except board_service.PostNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND"})
    except board_service.NotPostOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_POST_OWNER"})
