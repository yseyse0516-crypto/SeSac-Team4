import { useState } from "react";
import { claimCoupon, getRemaining, isClaimed } from "../../utils/coupon";
import "./CouponBanner.css";

// 회의록: "쿠폰(커뮤니티쪽 상단 배너에 추가해보기)". backend.md에서 아직 조건부(§3) 기능이라
// 실제 Redis 선착순 로직은 없고, 이 브라우저 안에서의 받기/소진 흐름만 보여준다.
export function CouponBanner() {
  const [remaining, setRemaining] = useState(getRemaining());
  const [claimed, setClaimed] = useState(isClaimed());

  function handleClaim() {
    const result = claimCoupon();
    setRemaining(result.remaining);
    if (result.success) setClaimed(true);
  }

  const soldOut = remaining <= 0;

  return (
    <div className="coupon-banner">
      <div>
        <div className="coupon-banner__text">🎉 BIUM 오픈 기념 선착순 쿠폰</div>
        <div className="coupon-banner__sub">
          {claimed ? "이미 받으셨어요" : soldOut ? "쿠폰이 모두 소진됐어요" : `남은 수량 ${remaining}장`}
        </div>
      </div>
      <button
        type="button"
        className="coupon-banner__button"
        onClick={handleClaim}
        disabled={claimed || soldOut}
      >
        {claimed ? "받음" : soldOut ? "마감" : "받기"}
      </button>
    </div>
  );
}
