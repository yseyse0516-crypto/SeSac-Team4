// ⚠️ 샌드박스 데모 전용 목업. backend.md에서 쿠폰(Redis 선착순)은 "조건부"(B가 시간 남으면 진행) 기능이라
// 실제 선착순 동시성 처리는 이 코드가 아니라 백엔드 Redis에서 해야 한다 — 여기선 브라우저 하나 안에서의
// 흐름(받기 → 소진 확인)만 흉내낸다.

const REMAINING_KEY = "bium_sandbox_coupon_remaining";
const CLAIMED_KEY = "bium_sandbox_coupon_claimed";
const INITIAL_REMAINING = 37;

export function getRemaining(): number {
  const raw = localStorage.getItem(REMAINING_KEY);
  return raw ? Number(raw) : INITIAL_REMAINING;
}

export function isClaimed(): boolean {
  return localStorage.getItem(CLAIMED_KEY) === "true";
}

export function claimCoupon(): { success: boolean; remaining: number } {
  if (isClaimed()) return { success: false, remaining: getRemaining() };
  const remaining = getRemaining();
  if (remaining <= 0) return { success: false, remaining: 0 };
  const next = remaining - 1;
  localStorage.setItem(REMAINING_KEY, String(next));
  localStorage.setItem(CLAIMED_KEY, "true");
  return { success: true, remaining: next };
}
