// docs/api-contracts/routing.md 에서 합의한 형태 + 피그마 목업 화면에 실제로 쓰인 필드를 반영한 타입.
// 백엔드 응답 형태가 바뀌면 이 파일을 먼저 고치고, 그다음 화면 컴포넌트를 고친다.

export interface LatLng {
  lat: number;
  lng: number;
}

export interface RouteSearchRequest {
  origin: LatLng;
  destination: LatLng;
  departAt: string; // ISO 8601, 예: "2026-08-18T08:30:00+09:00"
}

export type TransportMode = "SUBWAY" | "BUS" | "BIKE" | "WALK";

export interface RouteStep {
  mode: TransportMode;
  label: string; // 예: "금천구청역 → 철산역"
  durationMin: number;
  lineOrRouteNo?: string; // 예: "7호선", "652" (버스 노선번호)
  congestionPct?: number; // 이 구간의 %혼잡도 (하차 전 기준)
  netOnboardCount?: number; // 이 구간의 재차인원(하차 직후 실제 남은 인원)
  stopSequence?: number; // 정차순번 (출고열차 판단용)
}

export interface RouteCandidate {
  routeId: string;
  label: string; // 카드 제목, 예: "추천 경로" / "지하철 직행" / "따릉이 + 지하철" / "버스 직행"
  isRecommended: boolean;
  modes: TransportMode[];
  durationMin: number;
  netOnboardRemaining: number; // 카드 배지에 표시되는 "여유 인원" 숫자
  minutePerImprovement: number; // 분당개선 = 재차인원 감소량 ÷ 추가 소요시간
  congestionPct: number; // 카드 막대바에 쓰는 평균 혼잡도
  path: LatLng[];
  steps: RouteStep[];
}

export interface RouteSearchResponse {
  routes: RouteCandidate[];
}
