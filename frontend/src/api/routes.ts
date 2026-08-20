// VITE_API_BASE_URL이 설정되어 있으면 실제 백엔드(POST /api/v1/routes/search)를 호출하고,
// 없으면 가짜 데이터(mock)를 돌려준다. 필드 형태는 backend/app/schemas/route.py(2026-08-20,
// zer0 브랜치 실제 구현) 기준.

import type { RouteSearchRequest, RouteSearchResponse } from "../types/routing";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// backend/app/routers/search.py의 에러 매핑(400/404/502) + odsay_client.py의 503(쿼터 초과).
// 화면 쪽 매핑은 RouteSearchPage.tsx 참고.
export class RouteSearchError extends Error {
  status: number;
  constructor(status: number) {
    super(`routes search failed: ${status}`);
    this.status = status;
  }
}

const MOCK_RESPONSE: RouteSearchResponse = {
  request_id: 1,
  is_same: false,
  candidates: [
    {
      id: 1,
      path_type: "subway+bus",
      is_recommended: true,
      is_fastest: false,
      total_time_min: 42,
      congestion_score: 0.26,
      minute_improvement_ratio: 4.7,
      segments: [
        {
          mode: "walk",
          duration_min: 4,
          distance_m: 300,
          matched: true,
          start: { lat: 37.4671, lng: 126.897 }, // 레미안위브아파트 (예시 좌표)
          end: { lat: 37.4553, lng: 126.8895 }, // 금천구청역
        },
        {
          mode: "subway",
          station_id: 1021,
          duration_min: 6,
          distance_m: 1800,
          matched: true,
          start: { lat: 37.4553, lng: 126.8895 }, // 금천구청역
          end: { lat: 37.4425, lng: 126.8938 }, // 철산역
        },
        {
          mode: "bus",
          stop_id: 2045,
          duration_min: 14,
          distance_m: 3200,
          matched: true,
          start: { lat: 37.4425, lng: 126.8938 }, // 철산역
          end: { lat: 37.4483, lng: 126.8836 }, // 독산역
        },
        {
          mode: "walk",
          duration_min: 5,
          distance_m: 380,
          matched: true,
          start: { lat: 37.4483, lng: 126.8836 }, // 독산역
          end: { lat: 37.4459, lng: 126.8917 }, // 독산사거리
        },
      ],
    },
    {
      id: 2,
      path_type: "subway",
      is_recommended: false,
      is_fastest: true,
      total_time_min: 54,
      congestion_score: 0.58,
      minute_improvement_ratio: 1.2,
      segments: [
        {
          mode: "subway",
          station_id: 1021,
          duration_min: 54,
          distance_m: 6100,
          matched: true,
          start: { lat: 37.4671, lng: 126.897 },
          end: { lat: 37.4459, lng: 126.8917 },
        },
      ],
    },
    {
      id: 3,
      path_type: "bus",
      is_recommended: false,
      is_fastest: false,
      total_time_min: 38,
      congestion_score: 0.71,
      minute_improvement_ratio: 0.8,
      segments: [
        {
          mode: "bus",
          stop_id: 2045,
          duration_min: 38,
          distance_m: 5900,
          matched: true,
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
