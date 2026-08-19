// 지금은 진짜 서버가 없어서 가짜 데이터(mock)를 돌려주는 파일.
// 필드 형태는 backend.md(정종우, 2026-08-19 최종본)의 §4/§5 계약을 따른다 (snake_case, congestion_score 0~1).
// 나중에 백엔드가 준비되면 fetchRoutes 함수 내용만 real fetch로 바꾸면 되고, 화면 컴포넌트는 손 안 대도 된다.

import type { RouteSearchRequest, RouteSearchResponse } from "../types/routing";

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

// 실제 백엔드가 준비되면 아래 함수 내부만 real fetch(`POST /api/v1/routes/search`)로 교체한다.
export async function fetchRoutes(
  _request: RouteSearchRequest
): Promise<RouteSearchResponse> {
  return new Promise((resolve) => setTimeout(() => resolve(MOCK_RESPONSE), 300));
}
