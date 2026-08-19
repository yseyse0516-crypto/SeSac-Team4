// 지금은 진짜 서버가 없어서 가짜 데이터(mock)를 돌려주는 파일.
// 값은 피그마 목업 화면에 실제로 표시된 숫자와 똑같이 맞춰서, 화면을 만들 때 목업이랑 바로 비교할 수 있게 했다.
// 나중에 백엔드가 준비되면 fetchRoutes 함수 내용만 real fetch로 바꾸면 되고, 화면 컴포넌트는 손 안 대도 된다.

import type { RouteSearchRequest, RouteSearchResponse } from "../types/routing";

const MOCK_RESPONSE: RouteSearchResponse = {
  routes: [
    {
      routeId: "r1",
      label: "추천 경로",
      isRecommended: true,
      modes: ["SUBWAY", "BUS", "WALK"],
      durationMin: 42,
      netOnboardRemaining: 18,
      minutePerImprovement: 4.7,
      congestionPct: 26,
      path: [
        { lat: 37.4671, lng: 126.897 }, // 레미안위브아파트 (예시 좌표)
        { lat: 37.4553, lng: 126.8895 }, // 금천구청역
        { lat: 37.4425, lng: 126.8938 }, // 철산역
        { lat: 37.4483, lng: 126.8836 }, // 독산역
        { lat: 37.4459, lng: 126.8917 }, // 독산사거리
      ],
      steps: [
        { mode: "WALK", label: "레미안위브아파트 → 금천구청역", durationMin: 4 },
        {
          mode: "SUBWAY",
          label: "금천구청역 → 철산역",
          durationMin: 6,
          lineOrRouteNo: "7호선",
          congestionPct: 22,
          netOnboardCount: 84,
          stopSequence: 3,
        },
        {
          mode: "BUS",
          label: "철산역 → 독산역",
          durationMin: 14,
          lineOrRouteNo: "652",
          congestionPct: 31,
          netOnboardCount: 102,
          stopSequence: 5,
        },
        { mode: "WALK", label: "독산역 → 독산사거리", durationMin: 5 },
      ],
    },
    {
      routeId: "r2",
      label: "지하철 직행",
      isRecommended: false,
      modes: ["SUBWAY"],
      durationMin: 54,
      netOnboardRemaining: 44,
      minutePerImprovement: 1.2,
      congestionPct: 58,
      path: [
        { lat: 37.4671, lng: 126.897 },
        { lat: 37.4459, lng: 126.8917 },
      ],
      steps: [{ mode: "SUBWAY", label: "레미안위브아파트 → 독산사거리 (직행)", durationMin: 54, lineOrRouteNo: "7호선" }],
    },
    {
      routeId: "r3",
      label: "따릉이 + 지하철",
      isRecommended: false,
      modes: ["BIKE", "SUBWAY"],
      durationMin: 49,
      netOnboardRemaining: 11,
      minutePerImprovement: 6.3,
      congestionPct: 33,
      path: [
        { lat: 37.4671, lng: 126.897 },
        { lat: 37.4459, lng: 126.8917 },
      ],
      steps: [
        { mode: "BIKE", label: "레미안위브아파트 → 금천구청역 (따릉이)", durationMin: 9 },
        { mode: "SUBWAY", label: "금천구청역 → 독산사거리", durationMin: 40, lineOrRouteNo: "7호선" },
      ],
    },
    {
      routeId: "r4",
      label: "버스 직행",
      isRecommended: false,
      modes: ["BUS"],
      durationMin: 38,
      netOnboardRemaining: 52,
      minutePerImprovement: 0.8,
      congestionPct: 71,
      path: [
        { lat: 37.4671, lng: 126.897 },
        { lat: 37.4459, lng: 126.8917 },
      ],
      steps: [{ mode: "BUS", label: "레미안위브아파트 → 독산사거리 (직행)", durationMin: 38, lineOrRouteNo: "5623" }],
    },
  ],
};

// 실제 백엔드가 준비되면 아래 함수 내부만 real fetch(`POST /api/routes/search`)로 교체한다.
export async function fetchRoutes(
  _request: RouteSearchRequest
): Promise<RouteSearchResponse> {
  return new Promise((resolve) => setTimeout(() => resolve(MOCK_RESPONSE), 300));
}
