from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.core import db
from app.core.redis import get_client
from app.schemas.coupon import CouponClaimResponse, CouponClaimStatus, CouponInfo

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


def _get_identity(x_client_token: Optional[str]) -> str:
    """사용자 식별값을 정규화한다.

    지금은 브라우저가 만든 익명 토큰(X-Client-Token)이 유일한 식별 수단이다. 로그인이
    붙으면 이 함수만 인증된 user_id를 반환하도록 바꾸면 되고, 호출부(라우터 핸들러)는
    손댈 필요가 없도록 식별 로직을 여기 한 곳에 모아둔다.
    """
    return (x_client_token or "").strip()


@router.get("/coupons/{coupon_id}", response_model=CouponInfo)
def get_coupon_info(
    coupon_id: int,
    x_client_token: Optional[str] = Header(None, alias="X-Client-Token"),
) -> CouponInfo:
    """쿠폰 정보 조회. X-Client-Token을 같이 보내면 이 토큰이 이미 발급받았는지도 알려준다.

    커뮤니티 배너처럼 페이지를 열자마자(클릭 전에) '받음'/'받기' 상태를 그려야 하는
    화면에서, POST .../claim을 미리 호출해보지 않고도 상태를 알 수 있게 하기 위함이다.
    """
    coupon = _get_coupon(coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="COUPON_NOT_FOUND")

    r = get_client()
    stock_key = _ensure_stock_key(coupon_id, coupon["total_stock"])
    remaining = max(int(r.get(stock_key) or 0), 0)

    claimed_by_me = False
    my_sequence = None
    token = _get_identity(x_client_token)
    if token:
        existing = r.hget(f"coupon:{coupon_id}:users", token)
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
    coupon_id: int, x_client_token: str = Header(..., alias="X-Client-Token")
) -> CouponClaimResponse:
    """선착순 쿠폰 발급.

    Redis 키 구조:
      coupon:{id}:stock    남은 재고 (DECR로 원자적 차감, 0 미만이면 매진)
      coupon:{id}:claimed  발급 성공 순번 카운터 (INCR)
      coupon:{id}:users    토큰 → 순번 해시 (HSETNX로 토큰당 1회만 통과시켜 중복 발급 차단)
    """
    token = _get_identity(x_client_token)
    if not token:
        raise HTTPException(status_code=400, detail="INVALID_INPUT")

    coupon = _get_coupon(coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="COUPON_NOT_FOUND")

    r = get_client()
    stock_key = _ensure_stock_key(coupon_id, coupon["total_stock"])
    claimed_key = f"coupon:{coupon_id}:claimed"
    users_key = f"coupon:{coupon_id}:users"

    # 토큰당 한 번만 재고 차감을 시도하도록 하는 원자적 게이트.
    is_new = r.hsetnx(users_key, token, _PENDING)
    if not is_new:
        existing = r.hget(users_key, token)
        if existing == _PENDING:
            # 같은 토큰의 첫 요청이 아직 순번을 기록하기 전에 들어온 재시도.
            raise HTTPException(status_code=409, detail="CLAIM_IN_PROGRESS")
        remaining = max(int(r.get(stock_key) or 0), 0)
        return CouponClaimResponse(
            status=CouponClaimStatus.ALREADY_CLAIMED,
            sequence=int(existing),
            remaining_stock=remaining,
        )

    remaining = r.decr(stock_key)
    if remaining < 0:
        r.incr(stock_key)  # 재고를 0 밑으로 드리프트시키지 않도록 원복
        r.hdel(users_key, token)  # 예약 해제 — 매진이라 이 토큰은 발급받지 못했으므로
        return CouponClaimResponse(
            status=CouponClaimStatus.SOLD_OUT, sequence=None, remaining_stock=0
        )

    sequence = r.incr(claimed_key)
    r.hset(users_key, token, sequence)
    return CouponClaimResponse(
        status=CouponClaimStatus.CLAIMED, sequence=sequence, remaining_stock=remaining
    )
