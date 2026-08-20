// tokens.css의 --level-calm/--level-normal/--level-busy/--level-packed와 같은 값을 실제 hex로 들고 있는 곳.
// CSS var(--level-calm) 문자열은 인라인 style에는 통하지만, 카카오맵 Polyline strokeColor처럼
// CSS가 아닌 곳에 넘기면 그대로 안 풀려서 색이 깨진다 — 그래서 지도에 넘길 색은 항상 여기서 가져온다.

export interface CongestionLevel {
  label: string;
  color: string;
}

const LEVELS: { max: number; level: CongestionLevel }[] = [
  { max: 0.4, level: { label: "여유", color: "#1fb987" } },
  { max: 0.6, level: { label: "보통", color: "#f0b429" } },
  { max: 0.8, level: { label: "혼잡", color: "#f2793a" } },
  { max: Infinity, level: { label: "매우 혼잡", color: "#e5484d" } },
];

export function getCongestionLevel(congestionScore: number): CongestionLevel {
  return LEVELS.find((entry) => congestionScore < entry.max)!.level;
}
