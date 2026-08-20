"""회원가입/로그인/JWT 발급·검증.

비밀번호는 bcrypt로 해시해서만 저장한다(평문·단순해시 저장 금지).

인증 방식은 JWT(Authorization: Bearer 헤더)로 확정했다 — 토큰 자체에 user_id를
서명해서 담아두면 어느 라우터든 DB 조회 없이 서명 검증만으로 신원을 확인할 수 있다.

트레이드오프(알고 진행하는 것): 로그아웃해도 서버가 토큰을 강제로 무효화할 방법이 없다
(만료 전까지는 그 토큰으로 계속 인증됨) — 그래서 만료시간을 24시간으로 짧게 잡았다.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
import psycopg.errors
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import db

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=24)


def _jwt_secret() -> str:
    # 함수로 감싸서 매 호출 시 os.getenv를 읽는다 — .env가 나중에 로드돼도(로딩 순서
    # 이슈) 항상 최신 값을 쓰게 하기 위함.
    return os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-in-production")


@dataclass
class User:
    id: int
    username: str
    password_hash: bytes
    nickname: str
    role: str = "member"  # 지금은 미사용 — 관리자 권한 기능은 추후 필요 시 이 필드로 확장
    created_at: datetime = None


class UsernameTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


_bearer_scheme = HTTPBearer(auto_error=False)

_USER_COLUMNS = "user_id AS id, username, password_hash, nickname, role, created_at"


def _row_to_user(row: dict) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"].encode("utf-8"),
        nickname=row["nickname"],
        role=row["role"],
        created_at=row["created_at"],
    )


def register(username: str, password: str, nickname: str) -> User:
    """username UNIQUE 제약을 그대로 신뢰한다 — 사전에 SELECT로 존재 여부를 확인하고 나서
    INSERT하면 그 사이에 동시 요청이 끼어드는 레이스가 남는다. INSERT를 먼저 시도하고
    제약 위반만 잡아서 UsernameTakenError로 변환하는 편이 경쟁 상황에서도 안전하다."""
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        with db.get_cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, nickname) VALUES (%s, %s, %s)",
                (username, password_hash.decode("utf-8"), nickname),
            )
            cur.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE user_id = lastval()")
            return _row_to_user(cur.fetchone())
    except psycopg.errors.UniqueViolation:
        raise UsernameTakenError(username)


def authenticate(username: str, password: str) -> User:
    with db.get_cursor() as cur:
        cur.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
    # 계정이 없을 때와 비밀번호가 틀렸을 때를 다른 에러로 알려주면 아이디 존재 여부가
    # 새어나간다(계정 열거 공격) — 항상 같은 예외로 처리한다.
    if row is None or not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        raise InvalidCredentialsError()
    return _row_to_user(row)


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"user_id": user.id, "iat": now, "exp": now + ACCESS_TOKEN_TTL}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> int:
    """공용 Dependency — 다른 라우터(쿠폰 등)에서도 그대로 가져다 쓴다:

        from app.services.auth_service import get_current_user_id
        current_user_id: int = Depends(get_current_user_id)

    `Authorization: Bearer <token>` 헤더의 JWT를 검증해 user_id만 반환한다. DB 조회가
    전혀 없다 — 서명 검증만으로 끝남. 비회원/토큰만료/위조 토큰은 전부 401
    LOGIN_REQUIRED로 통일해서 던진다.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail={"code": "LOGIN_REQUIRED"})
    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"code": "LOGIN_REQUIRED"})

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail={"code": "LOGIN_REQUIRED"})
    return user_id


def get_current_user(user_id: int = Depends(get_current_user_id)) -> User:
    """user_id뿐 아니라 닉네임 등 전체 프로필이 필요할 때(게시판 글쓰기 등) 사용."""
    with db.get_cursor() as cur:
        cur.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail={"code": "LOGIN_REQUIRED"})
    return _row_to_user(row)
