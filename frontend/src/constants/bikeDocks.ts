// 따릉이 대여소 목업 — 실제로는 backend.md의 rental_dock/dock_hub_distance를 조회해야 한다.
// 지금은 기존 mock 경로 좌표(레미안위브아파트~독산사거리 권역) 주변에 임의로 몇 개 흩어둔 것.

export interface BikeDock {
  id: string;
  name: string;
  lat: number;
  lng: number;
  availableCount: number;
}

export const BIKE_DOCKS: BikeDock[] = [
  { id: "dock-1", name: "금천구청역 3번출구", lat: 37.4558, lng: 126.8899, availableCount: 6 },
  { id: "dock-2", name: "철산역 1번출구", lat: 37.4429, lng: 126.8933, availableCount: 2 },
  { id: "dock-3", name: "독산역 앞", lat: 37.4487, lng: 126.884, availableCount: 9 },
  { id: "dock-4", name: "독산사거리", lat: 37.4462, lng: 126.892, availableCount: 0 },
  { id: "dock-5", name: "레미안위브아파트 정문", lat: 37.4674, lng: 126.8975, availableCount: 4 },
];
