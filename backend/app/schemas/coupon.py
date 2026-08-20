from enum import Enum

from pydantic import BaseModel


class CouponClaimStatus(str, Enum):
    CLAIMED = "CLAIMED"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    SOLD_OUT = "SOLD_OUT"


class CouponClaimResponse(BaseModel):
    status: CouponClaimStatus
    sequence: int | None = None
    remaining_stock: int


class CouponInfo(BaseModel):
    coupon_id: int
    title: str
    total_stock: int
    remaining_stock: int
    claimed_by_me: bool = False
    my_sequence: int | None = None
