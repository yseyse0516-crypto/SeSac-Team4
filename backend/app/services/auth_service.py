"""회원가입/로그인/JWT 발급·검증.

⚠️ 사용자 저장은 임시로 프로세스 메모리를 쓴다(재시작하면 전부 사라지고 다시 가입해야
함) — B의 core/db.py가 붙으면 이 파일의 사용자 저장 부분만 실제 SQL로 교체하면 된다
(board_service.py와 동일한 패턴). 반면 **로그인 자체(토큰 검증)는 처음부터 저장소가
필요 없다** — JWT라 서명만 확인하면 되기 때문(아래 설명 참고).

비밀번호는 bcrypt로 해시해서만 저장한다(평문·단순해시 저장 금지).

인증 방식은 JWT(Authorization: Bearer 헤더)로 확정했다 — B(김창영)가 쿠폰 등 다른
라우터에서도 "지금 요청한 사람이 누군지"를 공용 Dependency 하나로 바로 확인하고 싶다고
요청했고(backend.md §12), 세션을 Redis 같은 공유 저장소에 두는 대신 **토큰 자체에
user_id를 서명해서 담아두면** 어느 라우터든(A 파일이든 B 파일이든) DB/Redis 조회 없이
서명 검증만으로 바로 신원을 확인할 수 있다 — 아직 core/db.py·core/redis.py가 안 붙은
지금 시점에 서로 다른 파일(A/B)이 저장소를 공유할 필요가 없어진다는 실질적 이점도 있다.

트레이드오프(알고 진행하는 것): 로그아웃해도 서버가 토큰을 강제로 무효화할 방법이 없다
(만료 전까지는 그 토큰으로 계속 인증됨) — 그래서 만료시간을 24시간으로 짧게 잡았다.
블록리스트를 두면 해결되지만 그러려면 결국 공유 저장소(Redis)가 필요해져서 JWT를 쓰는
이유 자체가 옅어진다 — 이번 스프린트 범위에서는 과한 대응이라 판단해 안 함.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=24)


def _jwt_secret() -> str:
    # 함수로 감싸서 매 호출 시 os.getenv를 읽는다 — .env가 나중에 로드돼도(로딩 순서
    # 이슈) 항상 최신 값을 쓰게 하기 위함. 모듈 임포트 시점에 상수로 고정하면 dotenv
    # 로드 전에 캡처될 위험이 있음.
    return os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-in-production")


@dataclass
class User:
    id: int
    username: str
    password_hash: bytes
    nickname: str
    role: str = "member"  # 지금은 미사용 — 관리자 권한 기능은 추후 필요 시 이 필드로 확장
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UsernameTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


_users_by_username: dict[str, User] = {}
_users_by_id: dict[int, User] = {}
_next_user_id = 1

_bearer_scheme = HTTPBearer(auto_error=False)


def register(username: str, password: str, nickname: str) -> User:
    global _next_user_id
    if username in _users_by_username:
        raise UsernameTakenError(username)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user = User(id=_next_user_id, username=username, password_hash=password_hash, nickname=nickname)
    _next_user_id += 1
    _users_by_username[username] = user
    _users_by_id[user.id] = user
    return user


def authenticate(username: str, password: str) -> User:
    user = _users_by_username.get(username)
    # 계정이 없을 때와 비밀번호가 틀렸을 때를 다른 에러로 알려주면 아이디 존재 여부가
    # 새어나간다(계정 열거 공격) — 항상 같은 예외로 처리한다.
    if user is None or not bcrypt.checkpw(password.encode("utf-8"), user.password_hash):
        raise InvalidCredentialsError()
    return user


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"user_id": user.id, "iat": now, "exp": now + ACCESS_TOKEN_TTL}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> int:
    """B가 요청한 공용 Dependency — 다른 라우터(쿠폰 등)에서도 그대로 가져다 쓰면 됨:

        from app.services.auth_service import get_current_user_id
        current_user_id: int = Depends(get_current_user_id)

    `Authorization: Bearer <token>` 헤더의 JWT를 검증해 user_id만 반환한다. DB/Redis
    조회가 전혀 없다 — 서명 검증만으로 끝남. 비회원/토큰만료/위조 토큰은 전부 401
    LOGIN_REQUIRED로 통일해서 던진다(프론트는 이 코드로 "로그인이 필요한 서비스입니다"
    + 회원가입 화면 안내를 띄우면 됨).
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
    user = _users_by_id.get(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "LOGIN_REQUIRED"})
    return user
