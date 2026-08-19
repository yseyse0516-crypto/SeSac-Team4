// backend.md(정종우, 2026-08-19 최종본)의 §4 데이터 계약 + §5 API 명세 기준 snake_case 필드.
// docs/api-contracts/routing.md에 확정/미확정 항목을 정리해뒀다 — 백엔드 응답 형태가 바뀌면
// 그 문서와 이 파일을 먼저 고치고, 그다음 화면 컴포넌트를 고친다.

export interface LatLng {
  lat: number;
  lng: number;
}

// ⚠️ request body의 정확한 필드명은 backend.md에 명시되어 있지 않음(A/B 확인 전까지 프론트 제안값).
export interface RouteSearchRequest {
  origin: LatLng;
  destination: LatLng;
  departAt: string; // ISO 8601, 예: "2026-08-18T08:30:00+09:00"
}

// backend.md §5 예시(segment.mode: "subway")는 소문자 — ODsay/DB 표기와 맞춘 것으로 보임.
export type TransportMode = "walk" | "subway" | "bus" | "bike";

export interface RouteSegment {
  mode: TransportMode;
  station_id?: number; // 지하철 구간
  stop_id?: number; // 버스 구간
  duration_min: number;
  start: LatLng;
  end: LatLng;
}

export interface RouteCandidate {
  id: number;
  path_type: string; // 값 종류(예: "fastest"/"recommended") backend.md에 enum이 명시돼 있지 않음 — 확인 필요
  is_recommended: boolean;
  total_time_min: number;
  congestion_score: number; // 0~1 정규화, 0에 가까울수록 쾌적 (backend.md §7.1 Q1)
  minute_improvement_ratio: number; // 분당개선 = 재차인원 감소량 ÷ 추가 소요시간
  segments: RouteSegment[];
}

// ⚠️ 최상위 응답 래핑 키("routes")는 backend.md에 명시된 적이 없음 — A/B 확인 필요, 확정 전까지 프론트 제안값.
export interface RouteSearchResponse {
  routes: RouteCandidate[];
}
