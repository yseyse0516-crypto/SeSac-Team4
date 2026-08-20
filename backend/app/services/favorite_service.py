"""즐겨찾기(자주 쓰는 출발-도착 경로) CRUD."""
from dataclasses import dataclass
from datetime import datetime

from app.core import db
from app.schemas.route import Coordinate

_FAVORITE_COLUMNS = (
    "favorite_id AS id, user_id, label, "
    "origin_lat, origin_lng, dest_lat, dest_lng, created_at"
)


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


def _row_to_favorite(row: dict) -> Favorite:
    return Favorite(
        id=row["id"],
        user_id=row["user_id"],
        label=row["label"],
        origin=Coordinate(lat=row["origin_lat"], lng=row["origin_lng"]),
        destination=Coordinate(lat=row["dest_lat"], lng=row["dest_lng"]),
        created_at=row["created_at"],
    )


def create_favorite(user_id: int, label: str, origin: Coordinate, destination: Coordinate) -> Favorite:
    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO favorite (user_id, label, origin_lat, origin_lng, dest_lat, dest_lng) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, label, origin.lat, origin.lng, destination.lat, destination.lng),
        )
        cur.execute(f"SELECT {_FAVORITE_COLUMNS} FROM favorite WHERE favorite_id = lastval()")
        return _row_to_favorite(cur.fetchone())


def list_favorites(user_id: int) -> list[Favorite]:
    with db.get_cursor() as cur:
        cur.execute(
            f"SELECT {_FAVORITE_COLUMNS} FROM favorite WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        return [_row_to_favorite(row) for row in cur.fetchall()]


def delete_favorite(favorite_id: int, user_id: int) -> None:
    with db.get_cursor() as cur:
        cur.execute(f"SELECT {_FAVORITE_COLUMNS} FROM favorite WHERE favorite_id = %s", (favorite_id,))
        row = cur.fetchone()
        if row is None:
            raise FavoriteNotFoundError(favorite_id)
        if row["user_id"] != user_id:
            raise NotFavoriteOwnerError(favorite_id)
        cur.execute("DELETE FROM favorite WHERE favorite_id = %s", (favorite_id,))
