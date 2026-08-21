"""커뮤니티 게시판 요청/응답 스키마.

작성/수정/삭제는 회원 전용(§12). 닉네임은 글마다 입력받지 않고 로그인한 계정의 닉네임을
자동으로 쓴다 — `PostCreate`에 nickname 필드가 없는 이유(응답에는 표시용으로 여전히 있음).
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
