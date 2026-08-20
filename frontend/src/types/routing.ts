// backend/app/schemas/route.py(2026-08-20, 실제 zer0 브랜치 구현) 기준 snake_case 필드.
// 이 파일을 실제 백엔드 응답 형태와 맞춰 고치고, 그다음 화면 컴포넌트를 고친다.

export interface LatLng {
  lat: number;
  lng: number;
}

export interface RouteSearchRequest {
  origin: LatLng;
  destination: LatLng;
  departure_time?: string; // optional, ISO 8601. 비우면 백엔드가 현재 시각을 기준으로 조회.
}

// route.py Segment.mode — 후보 경로 구간엔 따릉이가 없다("따릉이" 탭은 별도의
// GET /api/v1/bike/docks·/bike/route 기능이지, route.search 후보의 이동수단이 아님).
export type TransportMode = "walk" | "subway" | "bus";

export interface RouteSegment {
  mode: TransportMode;
  duration_min: number;
  distance_m: number;
  start: LatLng;
  end: LatLng;
  station_id?: number | null; // 지하철 구간
  stop_id?: number | null; // 버스 구간
  stop_std_id?: string | null;
  route_id?: string | null;
  stop_sequence?: number | null;
  matched: boolean; // 매칭 실패 시 false (station_id/stop_id는 null)
  polyline?: { lat: number; lng: number }[] | null; // null이면 start-end를 직선으로 표시
}

export interface RouteCandidate {
  id: number;
  path_type: string; // 실제 이동수단 조합 문자열(예: "subway", "bus", "subway+bus") — 추천/최단 분류가 아님
  is_recommended: boolean;
  is_fastest: boolean; // 추천/최단 구분은 이 두 불리언으로 하고, path_type으로 하지 않는다
  total_time_min: number;
  congestion_score: number; // 0~1 정규화, 0에 가까울수록 쾌적
  minute_improvement_ratio: number; // 분당개선 = 재차인원 감소량 ÷ 추가 소요시간
  segments: RouteSegment[];
}

export interface RouteSearchResponse {
  request_id: number;
  candidates: RouteCandidate[];
  is_same: boolean; // 최단시간 후보와 추천 후보가 동일한 경로인지
}
