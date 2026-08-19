"""커뮤니티 게시판 요청/응답 스키마.

원래 backend.md §3에서 "완전히 제외"였다가 2026-08-19 저녁 팀 결정으로 다시 포함됨
(§12 참고). 로그인이 없는 서비스라 작성자 식별은 닉네임(표시용) + X-Client-Token
(권한 확인용, 응답엔 노출 안 함)으로 처리한다.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=20)
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
