"""즐겨찾기(자주 쓰는 출발-도착 경로) CRUD — 회원 전용 (backend.md §12)."""
from fastapi import APIRouter, Depends, HTTPException

from app.schemas.favorite import FavoriteCreate, FavoriteListOut, FavoriteOut
from app.services import auth_service, favorite_service

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


def _to_favorite_out(fav: favorite_service.Favorite) -> FavoriteOut:
    return FavoriteOut(
        id=fav.id,
        label=fav.label,
        origin=fav.origin,
        destination=fav.destination,
        created_at=fav.created_at,
    )


@router.post("", response_model=FavoriteOut, status_code=201)
def create_favorite(
    payload: FavoriteCreate,
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> FavoriteOut:
    fav = favorite_service.create_favorite(
        current_user.id, payload.label, payload.origin, payload.destination
    )
    return _to_favorite_out(fav)


@router.get("", response_model=FavoriteListOut)
def list_favorites(
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> FavoriteListOut:
    favs = favorite_service.list_favorites(current_user.id)
    return FavoriteListOut(favorites=[_to_favorite_out(f) for f in favs])


@router.delete("/{favorite_id}", status_code=204)
def delete_favorite(
    favorite_id: int,
    current_user: auth_service.User = Depends(auth_service.get_current_user),
) -> None:
    try:
        favorite_service.delete_favorite(favorite_id, current_user.id)
    except favorite_service.FavoriteNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "FAVORITE_NOT_FOUND"})
    except favorite_service.NotFavoriteOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_FAVORITE_OWNER"})
