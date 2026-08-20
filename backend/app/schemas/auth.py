"""회원가입/로그인 요청·응답 스키마.

로그인 세션 도입 결정: 2026-08-19 저녁, 팀 요청으로 진행(backend.md §12). CLAUDE.md
§4/§13은 "1차 MVP엔 회원가입/로그인 없음"으로 명시했던 항목이라(CLAUDE.md 기준 번호 —
backend.md 쪽 상세 기록은 §12) 이번 번복 사유를 backend.md에 기록해뒀다. 이메일은 받지
않는다 — N-04(개인정보 최소화) 취지와 일관되게, 이번 스프린트에 실제로 안 쓰는 개인정보
(이메일, 비밀번호 재설정 플로우 등)는 처음부터 요구하지 않는다.

인증 방식은 JWT(Authorization: Bearer 헤더) — B(김창영)가 쿠폰 등 다른 라우터에서 로그인
결과를 DB/세션 조회 없이 바로 쓸 수 있게 요청한 방식(backend.md §12).
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
