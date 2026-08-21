"""즐겨찾기(자주 쓰는 출발-도착 경로) CRUD 통합 테스트 — 전 구간 로그인 필요."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import db
from app.routers.favorites import router
from app.services import auth_service

app = FastAPI()
app.include_router(router)
client = TestClient(app)

FAVORITE_BODY = {
    "label": "집",
    "origin": {"lat": 37.5012, "lng": 127.0396},
    "destination": {"lat": 37.4784, "lng": 126.8874},
}


@pytest.fixture(autouse=True)
def _reset_state():
    with db.get_cursor() as cur:
        cur.execute("TRUNCATE users, board_post, favorite RESTART IDENTITY CASCADE")
    yield


def _make_token(username="alice"):
    user = auth_service.register(username, "password123", "닉네임")
    return auth_service.create_access_token(user)


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_favorite_requires_login():
    resp = client.post("/api/v1/favorites", json=FAVORITE_BODY)
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "LOGIN_REQUIRED"


def test_create_and_list_favorite():
    token = _make_token()
    create_resp = client.post("/api/v1/favorites", json=FAVORITE_BODY, headers=_auth_header(token))
    assert create_resp.status_code == 201
    assert create_resp.json()["label"] == "집"

    list_resp = client.get("/api/v1/favorites", headers=_auth_header(token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()["favorites"]) == 1


def test_list_favorites_requires_login():
    resp = client.get("/api/v1/favorites")
    assert resp.status_code == 401


def test_favorites_are_scoped_per_user():
    token_a = _make_token(username="alice")
    token_b = _make_token(username="bob")
    client.post("/api/v1/favorites", json=FAVORITE_BODY, headers=_auth_header(token_a))

    resp_b = client.get("/api/v1/favorites", headers=_auth_header(token_b))
    assert resp_b.json()["favorites"] == []


def test_owner_can_delete_own_favorite():
    token = _make_token()
    fav_id = client.post(
        "/api/v1/favorites", json=FAVORITE_BODY, headers=_auth_header(token)
    ).json()["id"]
    resp = client.delete(f"/api/v1/favorites/{fav_id}", headers=_auth_header(token))
    assert resp.status_code == 204


def test_non_owner_cannot_delete_favorite():
    token_a = _make_token(username="alice")
    token_b = _make_token(username="bob")
    fav_id = client.post(
        "/api/v1/favorites", json=FAVORITE_BODY, headers=_auth_header(token_a)
    ).json()["id"]
    resp = client.delete(f"/api/v1/favorites/{fav_id}", headers=_auth_header(token_b))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "NOT_FAVORITE_OWNER"


def test_delete_missing_favorite_returns_404():
    token = _make_token()
    resp = client.delete("/api/v1/favorites/999999", headers=_auth_header(token))
    assert resp.status_code == 404
