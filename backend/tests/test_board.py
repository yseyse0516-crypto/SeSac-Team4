"""POST /api/v1/board/posts 등 커뮤니티 게시판 CRUD 통합 테스트.

작성/수정/삭제는 로그인 필요(§12) — auth_service로 직접 사용자를 만들고 JWT를 발급해서
Authorization: Bearer 헤더로 보낸다(HTTP로 회원가입까지 거칠 필요 없음, auth_service의
메모리 저장소를 그대로 공유하므로).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.board import router
from app.services import auth_service, board_service

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    board_service._posts.clear()
    auth_service._users_by_username.clear()
    auth_service._users_by_id.clear()
    yield
    board_service._posts.clear()
    auth_service._users_by_username.clear()
    auth_service._users_by_id.clear()


def _make_user(username="alice", nickname="앨리스"):
    user = auth_service.register(username, "password123", nickname)
    token = auth_service.create_access_token(user)
    return user, token


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create(content="첫 글", token=None):
    headers = _auth_header(token) if token else {}
    return client.post("/api/v1/board/posts", json={"content": content}, headers=headers)


def test_create_post_uses_account_nickname_automatically():
    _, token = _make_user(nickname="앨리스")
    resp = _create(content="첫 글", token=token)
    assert resp.status_code == 201
    body = resp.json()
    assert body["nickname"] == "앨리스"
    assert body["content"] == "첫 글"


def test_create_post_without_login_returns_401():
    resp = _create(content="비회원 글")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "LOGIN_REQUIRED"


def test_list_posts_is_public_no_login_needed():
    _, token = _make_user()
    _create(content="글", token=token)
    resp = client.get("/api/v1/board/posts")  # 인증 헤더 없음
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_single_post_is_public():
    _, token = _make_user()
    post_id = _create(token=token).json()["id"]
    resp = client.get(f"/api/v1/board/posts/{post_id}")
    assert resp.status_code == 200


def test_get_missing_post_returns_404():
    resp = client.get("/api/v1/board/posts/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "POST_NOT_FOUND"


def test_owner_can_update_own_post():
    _, token = _make_user()
    post_id = _create(content="원래 내용", token=token).json()["id"]
    resp = client.put(
        f"/api/v1/board/posts/{post_id}",
        json={"content": "수정된 내용"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "수정된 내용"


def test_non_owner_cannot_update_post():
    _, token_a = _make_user(username="alice")
    _, token_b = _make_user(username="bob")
    post_id = _create(token=token_a).json()["id"]
    resp = client.put(
        f"/api/v1/board/posts/{post_id}",
        json={"content": "남의 글 수정 시도"},
        headers=_auth_header(token_b),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "NOT_POST_OWNER"


def test_owner_can_delete_own_post():
    _, token = _make_user()
    post_id = _create(token=token).json()["id"]
    resp = client.delete(f"/api/v1/board/posts/{post_id}", headers=_auth_header(token))
    assert resp.status_code == 204
    assert client.get(f"/api/v1/board/posts/{post_id}").status_code == 404


def test_non_owner_cannot_delete_post():
    _, token_a = _make_user(username="alice")
    _, token_b = _make_user(username="bob")
    post_id = _create(token=token_a).json()["id"]
    resp = client.delete(f"/api/v1/board/posts/{post_id}", headers=_auth_header(token_b))
    assert resp.status_code == 403
    assert client.get(f"/api/v1/board/posts/{post_id}").status_code == 200


def test_update_without_login_returns_401():
    _, token = _make_user()
    post_id = _create(token=token).json()["id"]
    resp = client.put(f"/api/v1/board/posts/{post_id}", json={"content": "x"})
    assert resp.status_code == 401
