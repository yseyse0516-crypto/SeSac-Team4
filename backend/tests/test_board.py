"""POST /api/v1/board/posts 등 커뮤니티 게시판 CRUD 통합 테스트.

board_service가 프로세스 메모리 저장소라 각 테스트 전후로 비워서 서로 영향 없게 한다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.board import router
from app.services import board_service

app = FastAPI()
app.include_router(router)
client = TestClient(app)

TOKEN_A = "11111111-1111-1111-1111-111111111111"
TOKEN_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _reset_board():
    board_service._posts.clear()
    yield
    board_service._posts.clear()


def _create(nickname="익명", content="첫 글", token=TOKEN_A):
    return client.post(
        "/api/v1/board/posts",
        json={"nickname": nickname, "content": content},
        headers={"X-Client-Token": token},
    )


def test_create_post_returns_201_with_post_body():
    resp = _create()
    assert resp.status_code == 201
    body = resp.json()
    assert body["nickname"] == "익명"
    assert body["content"] == "첫 글"
    assert "id" in body and "created_at" in body


def test_create_post_without_token_returns_400():
    resp = client.post("/api/v1/board/posts", json={"nickname": "익명", "content": "내용"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MISSING_CLIENT_TOKEN"


def test_list_posts_returns_newest_first():
    _create(content="첫 번째")
    _create(content="두 번째")
    resp = client.get("/api/v1/board/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [p["content"] for p in body["posts"]] == ["두 번째", "첫 번째"]


def test_get_single_post():
    post_id = _create().json()["id"]
    resp = client.get(f"/api/v1/board/posts/{post_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == post_id


def test_get_missing_post_returns_404():
    resp = client.get("/api/v1/board/posts/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "POST_NOT_FOUND"


def test_owner_can_update_own_post():
    post_id = _create(content="원래 내용", token=TOKEN_A).json()["id"]
    resp = client.put(
        f"/api/v1/board/posts/{post_id}",
        json={"content": "수정된 내용"},
        headers={"X-Client-Token": TOKEN_A},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "수정된 내용"


def test_non_owner_cannot_update_post():
    post_id = _create(token=TOKEN_A).json()["id"]
    resp = client.put(
        f"/api/v1/board/posts/{post_id}",
        json={"content": "남의 글 수정 시도"},
        headers={"X-Client-Token": TOKEN_B},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "NOT_POST_OWNER"


def test_owner_can_delete_own_post():
    post_id = _create(token=TOKEN_A).json()["id"]
    resp = client.delete(f"/api/v1/board/posts/{post_id}", headers={"X-Client-Token": TOKEN_A})
    assert resp.status_code == 204
    assert client.get(f"/api/v1/board/posts/{post_id}").status_code == 404


def test_non_owner_cannot_delete_post():
    post_id = _create(token=TOKEN_A).json()["id"]
    resp = client.delete(f"/api/v1/board/posts/{post_id}", headers={"X-Client-Token": TOKEN_B})
    assert resp.status_code == 403
    assert client.get(f"/api/v1/board/posts/{post_id}").status_code == 200


def test_update_without_token_returns_400():
    post_id = _create().json()["id"]
    resp = client.put(f"/api/v1/board/posts/{post_id}", json={"content": "x"})
    assert resp.status_code == 400
