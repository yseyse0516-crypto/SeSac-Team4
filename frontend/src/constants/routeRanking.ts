// 경로 표시 색을 "실제 혼잡도 절대값"이 아니라 "지금 보여주는 후보들 사이의 순위"로 정한다.
// 추천 경로(is_recommended)가 항상 초록, 나머지는 혼잡도가 낮은 순으로 정렬해서 앞쪽 절반은
// 노랑, 뒤쪽 절반(더 혼잡한 쪽)은 빨강 — 모든 탭(전체/지하철/자전거)에서 동일하게 적용한다.
import type { RouteCandidate } from "../types/routing";

const RANK_GREEN = "#1fb987";
const RANK_YELLOW = "#f0b429";
const RANK_RED = "#e5484d";

export function rankRouteColors(routes: RouteCandidate[]): Map<number, string> {
  const colors = new Map<number, string>();
  if (routes.length === 0) return colors;

  const recommended = routes.find((r) => r.is_recommended);
  const rest = routes.filter((r) => r !== recommended).sort((a, b) => a.congestion_score - b.congestion_score);

  if (recommended) {
    colors.set(recommended.id, RANK_GREEN);
  } else {
    // 추천 표시가 없는 예외 상황이면 혼잡도가 가장 낮은 후보를 1등으로 취급한다.
    const best = rest.shift();
    if (best) colors.set(best.id, RANK_GREEN);
  }

  const yellowCount = Math.ceil(rest.length / 2);
  rest.forEach((route, i) => {
    colors.set(route.id, i < yellowCount ? RANK_YELLOW : RANK_RED);
  });

  return colors;
}
