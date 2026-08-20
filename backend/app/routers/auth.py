"""회원가입/로그인/내 정보 조회 (backend.md §12).

기본 서비스(경로 검색)는 로그인 없이 그대로 쓸 수 있고, 게시판 작성·수정과 즐겨찾기만
로그인을 요구한다 — 이 라우터는 그 로그인 자체(JWT 발급/검증)를 처리한다.

로그아웃 API는 일부러 안 만들었다 — JWT는 서버가 들고 있는 상태가 없어서(그게 장점이자
트레이드오프, auth_service.py 상단 설명 참고) "로그아웃"은 순수하게 프론트가 저장해둔
토큰을 지우는 것으로 끝난다. 백엔드가 할 일이 없는 동작을 API로 만들면 오히려 "뭔가
서버에서 처리해준다"는 오해를 살 수 있어 빼는 쪽을 택함.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_user_out(user: auth_service.User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, nickname=user.nickname, created_at=user.created_at
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest) -> TokenResponse:
    try:
        user = auth_service.register(payload.username, payload.password, payload.nickname)
    except auth_service.UsernameTakenError:
        raise HTTPException(status_code=409, detail={"code": "USERNAME_TAKEN"})
    token = auth_service.create_access_token(user)
    return TokenResponse(access_token=token, user=_to_user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    try:
        user = auth_service.authenticate(payload.username, payload.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS"})
    token = auth_service.create_access_token(user)
    return TokenResponse(access_token=token, user=_to_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current_user: auth_service.User = Depends(auth_service.get_current_user)) -> UserOut:
    return _to_user_out(current_user)
