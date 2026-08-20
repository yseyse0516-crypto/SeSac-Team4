// 샌드박스에서 만든 localStorage 데이터를 전부 정리하는 헬퍼 (회원탈퇴 시뮬레이션용).
// 실제 서비스에는 회원가입/로그인 자체가 없다(CLAUDE.md 1차 MVP 범위 밖) — 이건 전부 프론트 mock이다.
const SANDBOX_PREFIX = "bium_sandbox_";

export function clearAllSandboxData(): void {
  const keys = Object.keys(localStorage).filter((key) => key.startsWith(SANDBOX_PREFIX));
  keys.forEach((key) => localStorage.removeItem(key));
}
