"""회원가입/로그인/내 정보 조회 통합 테스트."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.auth import router
from app.services import auth_service

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    auth_service._users_by_username.clear()
    auth_service._users_by_id.clear()
    yield
    auth_service._users_by_username.clear()
    auth_service._users_by_id.clear()


def _register(username="alice", password="password123", nickname="앨리스"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "nickname": nickname},
    )


def test_register_returns_access_token_and_user():
    resp = _register()
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["username"] == "alice"
    assert body["user"]["nickname"] == "앨리스"


def test_password_is_never_returned():
    resp = _register()
    assert "password" not in resp.text
    assert "password_hash" not in resp.text


def test_duplicate_username_returns_409():
    _register(username="alice")
    resp = _register(username="alice")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


def test_too_short_password_returns_422():
    resp = _register(password="short")
    assert resp.status_code == 422


def test_login_with_correct_password_succeeds():
    _register(username="alice", password="password123")
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_with_wrong_password_returns_401():
    _register(username="alice", password="password123")
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_login_with_unknown_username_returns_same_error_as_wrong_password():
    # 계정 존재 여부가 새어나가지 않도록 같은 에러 코드/상태여야 함 (계정 열거 공격 방지)
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_valid_token():
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "LOGIN_REQUIRED"


def test_me_rejects_garbage_token():
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "LOGIN_REQUIRED"


def test_me_returns_current_user_with_valid_token():
    token = _register(username="alice", nickname="앨리스").json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
