import type { RouteCandidate, RouteSegment } from "../../types/routing";
import "./RouteDirections.css";

interface RouteDirectionsProps {
  route: RouteCandidate;
}

const MODE_ICON: Record<RouteSegment["mode"], string> = {
  walk: "🚶",
  subway: "🚇",
  bus: "🚌",
};

// 세그먼트 하나를 "OO역에서 탑승 후 OO역 하차" 같은 한 줄 안내문으로 바꾼다.
// 도보 구간은 ODsay가 역/정류장 이름을 안 줘서, 다음 구간의 탑승 지점 이름을 목적지로 빌려 쓴다.
function stepText(segment: RouteSegment, index: number, segments: RouteSegment[]): string {
  if (segment.mode === "walk") {
    const isLast = index === segments.length - 1;
    if (isLast) return `도보 ${segment.duration_min}분 이동 → 목적지 도착`;
    const nextName = segments[index + 1]?.start_name;
    return nextName ? `${nextName}까지 도보 ${segment.duration_min}분` : `도보 ${segment.duration_min}분 이동`;
  }
  if (segment.mode === "subway") {
    const line = segment.line_name ? `${segment.line_name} ` : "";
    return `${line}지하철 탑승: ${segment.start_name ?? "승차역"} → ${segment.end_name ?? "하차역"} (${segment.duration_min}분)`;
  }
  const busNo = segment.route_id ? `${segment.route_id}번 ` : "";
  return `${busNo}버스 탑승: ${segment.start_name ?? "승차 정류장"} → ${segment.end_name ?? "하차 정류장"} (${segment.duration_min}분)`;
}

// 요약 비교카드(최단시간/추천)를 눌렀을 때 실제로 "어떻게 가야 하는지" 보여주는 단계별 안내.
export function RouteDirections({ route }: RouteDirectionsProps) {
  return (
    <ol className="route-directions">
      {route.segments.map((segment, index) => (
        <li key={index} className="route-directions__step">
          <span className="route-directions__icon">{MODE_ICON[segment.mode]}</span>
          <span className="route-directions__text">{stepText(segment, index, route.segments)}</span>
        </li>
      ))}
    </ol>
  );
}
