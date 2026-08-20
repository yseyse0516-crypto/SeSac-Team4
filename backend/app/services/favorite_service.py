"""즐겨찾기(자주 쓰는 출발-도착 경로) CRUD.

⚠️ 임시 구현 — 프로세스 메모리 저장(board_service.py와 동일한 패턴). B의 core/db.py가
붙으면 이 파일 내부만 실제 SQL로 교체하면 된다.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count

from app.schemas.route import Coordinate


@dataclass
class Favorite:
    id: int
    user_id: int
    label: str
    origin: Coordinate
    destination: Coordinate
    created_at: datetime


class FavoriteNotFoundError(Exception):
    pass


class NotFavoriteOwnerError(Exception):
    pass


_favorites: dict[int, Favorite] = {}
_next_id = count(1)


def create_favorite(user_id: int, label: str, origin: Coordinate, destination: Coordinate) -> Favorite:
    fav = Favorite(
        id=next(_next_id),
        user_id=user_id,
        label=label,
        origin=origin,
        destination=destination,
        created_at=datetime.now(timezone.utc),
    )
    _favorites[fav.id] = fav
    return fav


def list_favorites(user_id: int) -> list[Favorite]:
    mine = [f for f in _favorites.values() if f.user_id == user_id]
    return sorted(mine, key=lambda f: f.created_at, reverse=True)


def delete_favorite(favorite_id: int, user_id: int) -> None:
    fav = _favorites.get(favorite_id)
    if fav is None:
        raise FavoriteNotFoundError(favorite_id)
    if fav.user_id != user_id:
        raise NotFavoriteOwnerError(favorite_id)
    del _favorites[favorite_id]
