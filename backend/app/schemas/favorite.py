"""즐겨찾기 요청/응답 스키마 (backend.md §12).

"즐겨찾기"는 특정 역/정류장이 아니라 **출발지-도착지 조합**을 저장하는 것으로 정의한다
(예: "집→회사"). 서비스의 핵심 입력값(route.SearchRequest)과 좌표 모양이 동일해서,
프론트가 즐겨찾기를 그대로 재검색(SearchRequest)에 꽂아 쓸 수 있다. 회원만 사용 가능.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.route import Coordinate


class FavoriteCreate(BaseModel):
    label: str = Field(min_length=1, max_length=20)
    origin: Coordinate
    destination: Coordinate


class FavoriteOut(BaseModel):
    id: int
    label: str
    origin: Coordinate
    destination: Coordinate
    created_at: datetime


class FavoriteListOut(BaseModel):
    favorites: list[FavoriteOut]
