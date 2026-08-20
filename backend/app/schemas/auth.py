"""회원가입/로그인 요청·응답 스키마 (backend.md §12).

이메일은 받지 않는다 — N-04(개인정보 최소화) 취지와 일관되게, 실제로 안 쓰는 개인정보는
처음부터 요구하지 않는다. 인증 방식은 JWT(Authorization: Bearer 헤더) — 다른 라우터에서도
DB/세션 조회 없이 로그인 결과를 바로 쓸 수 있다.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=100)
    nickname: str = Field(min_length=1, max_length=20)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    user: UserOut
