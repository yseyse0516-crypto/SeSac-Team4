from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.redis import get_client
from app.schemas.coupon import CouponClaimResponse, CouponClaimStatus, CouponInfo
from app.services.auth_service import get_current_user_id, get_optional_user_id

router = APIRouter(tags=["coupon"])

_PENDING = "-1"


def _get_coupon(coupon_id: int) -> dict | None:
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT coupon_id, title, total_stock FROM coupon WHERE coupon_id = %s",
            (coupon_id,),
        )
        return cur.fetchone()


def _ensure_stock_key(coupon_id: int, total_stock: int) -> str:
    """coupon:{id}:stock을 최초 1회만 total_stock으로 초기화하고 키 이름을 반환한다."""
    stock_key = f"coupon:{coupon_id}:stock"
    get_client().setnx(stock_key, total_stock)
    return stock_key


@router.get("/coupons/{coupon_id}", response_model=CouponInfo)
def get_coupon_info(
    coupon_id: int,
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> CouponInfo:
    """쿠폰 정보 조회. 로그인 상태면 내가 이미 발급받았는지도 같이 알려준다."""
    coupon = _get_coupon(coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail={"code": "COUPON_NOT_FOUND"})

    r = get_client()
    stock_key = _ensure_stock_key(coupon_id, coupon["total_stock"])
    remaining = max(int(r.get(stock_key) or 0), 0)

    claimed_by_me = False
    my_sequence = None
    if user_id is not None:
        existing = r.hget(f"coupon:{coupon_id}:users", str(user_id))
        if existing is not None and existing != _PENDING:
            claimed_by_me = True
            my_sequence = int(existing)

    return CouponInfo(
        coupon_id=coupon["coupon_id"],
        title=coupon["title"],
        total_stock=coupon["total_stock"],
        remaining_stock=remaining,
        claimed_by_me=claimed_by_me,
        my_sequence=my_sequence,
    )


@router.post("/coupons/{coupon_id}/claim", response_model=CouponClaimResponse)
def claim_coupon(
    coupon_id: int, current_user_id: int = Depends(get_current_user_id)
) -> CouponClaimResponse:
    """선착순 쿠폰 발급 — 로그인 필수(비로그인 시 auth_service가 401 LOGIN_REQUIRED로 처리).

    Redis 키 구조:
      coupon:{id}:stock    남은 재고 (DECR로 원자적 차감, 0 미만이면 매진)
      coupon:{id}:claimed  발급 성공 순번 카운터 (INCR)
      coupon:{id}:users    user_id → 순번 해시 (HSETNX로 계정당 1회만 통과시켜 중복 발급 차단)
    """
    user_key = str(current_user_id)

    coupon = _get_coupon(coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail={"code": "COUPON_NOT_FOUND"})

    r = get_client()
    stock_key = _ensure_stock_key(coupon_id, coupon["total_stock"])
    claimed_key = f"coupon:{coupon_id}:claimed"
    users_key = f"coupon:{coupon_id}:users"

    # 계정당 한 번만 재고 차감을 시도하도록 하는 원자적 게이트.
    is_new = r.hsetnx(users_key, user_key, _PENDING)
    if not is_new:
        existing = r.hget(users_key, user_key)
        if existing == _PENDING:
            # 같은 계정의 첫 요청이 아직 순번을 기록하기 전에 들어온 재시도.
            raise HTTPException(status_code=409, detail={"code": "CLAIM_IN_PROGRESS"})
        remaining = max(int(r.get(stock_key) or 0), 0)
        return CouponClaimResponse(
            status=CouponClaimStatus.ALREADY_CLAIMED,
            sequence=int(existing),
            remaining_stock=remaining,
        )

    remaining = r.decr(stock_key)
    if remaining < 0:
        r.incr(stock_key)  # 재고를 0 밑으로 드리프트시키지 않도록 원복
        r.hdel(users_key, user_key)  # 예약 해제 — 매진이라 이 계정은 발급받지 못했으므로
        return CouponClaimResponse(
            status=CouponClaimStatus.SOLD_OUT, sequence=None, remaining_stock=0
        )

    sequence = r.incr(claimed_key)
    r.hset(users_key, user_key, sequence)
    return CouponClaimResponse(
        status=CouponClaimStatus.CLAIMED, sequence=sequence, remaining_stock=remaining
    )
