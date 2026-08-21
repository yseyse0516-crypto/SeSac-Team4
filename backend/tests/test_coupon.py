"""GET /coupons/{id}, POST /coupons/{id}/claim 통합 테스트.

02_seed.sql 기준 coupon_id=1(총 재고 100)을 그대로 쓴다. Redis는 conftest.py의
전역 fakeredis 픽스처가 테스트마다 초기화해주므로 재고는 매 테스트 100부터 시작한다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import db
from app.routers.coupon import router
from app.services import auth_service

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_users():
    with db.get_cursor() as cur:
        cur.execute("TRUNCATE users, board_post, favorite RESTART IDENTITY CASCADE")
    yield


def _make_token(username="alice"):
    user = auth_service.register(username, "password123", "닉네임")
    return auth_service.create_access_token(user)


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_coupon_info_without_login():
    resp = client.get("/coupons/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["coupon_id"] == 1
    assert body["remaining_stock"] == 100
    assert body["claimed_by_me"] is False


def test_get_missing_coupon_returns_404():
    resp = client.get("/coupons/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "COUPON_NOT_FOUND"


def test_claim_without_login_returns_401():
    resp = client.post("/coupons/1/claim")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "LOGIN_REQUIRED"


def test_claim_with_login_succeeds_and_decrements_stock():
    token = _make_token()
    resp = client.post("/coupons/1/claim", headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "CLAIMED"
    assert body["sequence"] == 1
    assert body["remaining_stock"] == 99


def test_claiming_twice_returns_already_claimed_with_same_sequence():
    token = _make_token()
    first = client.post("/coupons/1/claim", headers=_auth_header(token))
    second = client.post("/coupons/1/claim", headers=_auth_header(token))
    assert second.status_code == 200
    assert second.json()["status"] == "ALREADY_CLAIMED"
    assert second.json()["sequence"] == first.json()["sequence"]


def test_get_coupon_info_after_claim_shows_claimed_by_me():
    token = _make_token()
    client.post("/coupons/1/claim", headers=_auth_header(token))
    resp = client.get("/coupons/1", headers=_auth_header(token))
    body = resp.json()
    assert body["claimed_by_me"] is True
    assert body["my_sequence"] == 1


def test_different_users_get_independent_sequences():
    token_a = _make_token("alice")
    token_b = _make_token("bob")
    resp_a = client.post("/coupons/1/claim", headers=_auth_header(token_a))
    resp_b = client.post("/coupons/1/claim", headers=_auth_header(token_b))
    assert resp_a.json()["sequence"] == 1
    assert resp_b.json()["sequence"] == 2
