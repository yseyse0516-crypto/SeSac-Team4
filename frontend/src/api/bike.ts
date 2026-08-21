// VITE_API_BASE_URL이 설정되어 있으면 실제 백엔드(GET /api/v1/bike/docks/nearby)를 호출하고,
// 없으면 가짜 데이터(mock)를 돌려준다. backend/app/schemas/bike.py의 NearbyDock 기준.

export interface NearbyDock {
  dock_std_id: string;
  name: string;
  lat: number;
  lng: number;
  distance_m: number;
  stock: number | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const MOCK_DOCKS: NearbyDock[] = [
  { dock_std_id: "mock-1", name: "금천구청역 3번출구", lat: 37.4558, lng: 126.8899, distance_m: 120, stock: 6 },
  { dock_std_id: "mock-2", name: "철산역 1번출구", lat: 37.4429, lng: 126.8933, distance_m: 340, stock: 2 },
];

export async function fetchNearbyDocks(
  center: { lat: number; lng: number },
  radiusM = 800
): Promise<NearbyDock[]> {
  if (!API_BASE_URL) {
    return new Promise((resolve) => setTimeout(() => resolve(MOCK_DOCKS), 200));
  }

  const params = new URLSearchParams({
    lat: String(center.lat),
    lng: String(center.lng),
    radius_m: String(radiusM),
  });
  const res = await fetch(`${API_BASE_URL}/api/v1/bike/docks/nearby?${params}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.docks ?? [];
}
