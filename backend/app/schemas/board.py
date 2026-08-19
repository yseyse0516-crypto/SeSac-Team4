"""커뮤니티 게시판 요청/응답 스키마.

원래 backend.md §3에서 "완전히 제외"였다가 2026-08-19 저녁 팀 결정으로 다시 포함됨
(§11 참고). 처음엔 로그인이 없어 X-Client-Token(익명 기기 토큰)으로 작성자를 식별했으나,
같은 날 저녁 로그인 기능이 추가되면서 **작성/수정/삭제는 회원 전용으로 전환**했다(§12).
닉네임은 더 이상 글마다 입력받지 않고 로그인한 계정의 닉네임을 자동으로 쓴다 — 그래서
`PostCreate`에 nickname 필드가 없다(응답에는 여전히 있음, 표시용).
"""
from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class PostUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class PostOut(BaseModel):
    id: int
    nickname: str
    content: str
    created_at: datetime
    updated_at: datetime


class PostListOut(BaseModel):
    posts: list[PostOut]
    total: int
