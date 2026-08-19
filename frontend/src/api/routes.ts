// VITE_API_BASE_URL이 설정되어 있으면 실제 백엔드(POST /api/v1/routes/search)를 호출하고,
// 없으면 가짜 데이터(mock)를 돌려준다. 필드 형태는 backend.md(정종우, 2026-08-19 최종본)의
// §4/§5 계약을 따른다 (snake_case, congestion_score 0~1). 내일 백엔드가 준비되면
// frontend/.env의 VITE_API_BASE_URL만 채우면 되고, 코드는 그대로 둬도 된다.

import type { RouteSearchRequest, RouteSearchResponse } from "../types/routing";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// backend.md/frontend-plan.md §3.3에 정의된 에러코드(400/404/429/502)를 화면에서 구분해서
// 처리할 수 있도록 status를 들고 있는 에러. 화면 쪽 매핑은 RouteSearchPage.tsx 참고.
export class RouteSearchError extends Error {
  status: number;
  constructor(status: number) {
    super(`routes search failed: ${status}`);
    this.status = status;
  }
}

const MOCK_RESPONSE: RouteSearchResponse = {
  routes: [
    {
      id: 1,
      path_type: "recommended",
      is_recommended: true,
      total_time_min: 42,
      congestion_score: 0.26,
      minute_improvement_ratio: 4.7,
      segments: [
        {
          mode: "walk",
          duration_min: 4,
          start: { lat: 37.4671, lng: 126.897 }, // 레미안위브아파트 (예시 좌표)
          end: { lat: 37.4553, lng: 126.8895 }, // 금천구청역
        },
        {
          mode: "subway",
          station_id: 1021,
          duration_min: 6,
          start: { lat: 37.4553, lng: 126.8895 }, // 금천구청역
          end: { lat: 37.4425, lng: 126.8938 }, // 철산역
        },
        {
          mode: "bus",
          stop_id: 2045,
          duration_min: 14,
          start: { lat: 37.4425, lng: 126.8938 }, // 철산역
          end: { lat: 37.4483, lng: 126.8836 }, // 독산역
        },
        {
          mode: "walk",
          duration_min: 5,
          start: { lat: 37.4483, lng: 126.8836 }, // 독산역
          end: { lat: 37.4459, lng: 126.8917 }, // 독산사거리
        },
      ],
    },
    {
      id: 2,
      path_type: "fastest",
      is_recommended: false,
      total_time_min: 54,
      congestion_score: 0.58,
      minute_improvement_ratio: 1.2,
      segments: [
        {
          mode: "subway",
          station_id: 1021,
          duration_min: 54,
          start: { lat: 37.4671, lng: 126.897 },
          end: { lat: 37.4459, lng: 126.8917 },
        },
      ],
    },
    {
      id: 3,
      path_type: "bike_transfer",
      is_recommended: false,
      total_time_min: 49,
      congestion_score: 0.33,
      minute_improvement_ratio: 6.3,
      segments: [
        {
          mode: "bike",
          duration_min: 9,
          start: { lat: 37.4671, lng: 126.897 },
          end: { lat: 37.4553, lng: 126.8895 },
        },
        {
          mode: "subway",
          station_id: 1021,
          duration_min: 40,
          start: { lat: 37.4553, lng: 126.8895 },
          end: { lat: 37.4459, lng: 126.8917 },
        },
      ],
    },
    {
      id: 4,
      path_type: "bus_direct",
      is_recommended: false,
      total_time_min: 38,
      congestion_score: 0.71,
      minute_improvement_ratio: 0.8,
      segments: [
        {
          mode: "bus",
          stop_id: 2045,
          duration_min: 38,
          start: { lat: 37.4671, lng: 126.897 },
          end: { lat: 37.4459, lng: 126.8917 },
        },
      ],
    },
  ],
};

export async function fetchRoutes(
  request: RouteSearchRequest
): Promise<RouteSearchResponse> {
  if (!API_BASE_URL) {
    return new Promise((resolve) => setTimeout(() => resolve(MOCK_RESPONSE), 300));
  }

  const res = await fetch(`${API_BASE_URL}/api/v1/routes/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new RouteSearchError(res.status);
  }
  return res.json();
}
