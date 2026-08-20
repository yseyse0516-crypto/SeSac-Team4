import type { RouteCandidate } from "../types/routing";

// ⚠️ 샌드박스 데모 전용 — 브라우저 localStorage에만 저장, 서버로 전송하지 않는다.
// 실제 서비스로 가져가려면 CLAUDE.md §4(N-04, 위치 이력 미저장 원칙)와 반드시 재검토해야 한다.
const STORAGE_KEY = "bium_sandbox_recent_routes";
const MAX_ITEMS = 10;

export interface RecentRouteEntry {
  route: RouteCandidate;
  savedAt: number;
}

export function getRecentRoutes(): RecentRouteEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveRecentRoute(route: RouteCandidate): RecentRouteEntry[] {
  const existing = getRecentRoutes().filter((entry) => entry.route.id !== route.id);
  const next = [{ route, savedAt: Date.now() }, ...existing].slice(0, MAX_ITEMS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function clearRecentRoutes(): void {
  localStorage.removeItem(STORAGE_KEY);
}
