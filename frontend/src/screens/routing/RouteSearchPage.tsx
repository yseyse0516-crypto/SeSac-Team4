import { useState } from "react";
import { RouteSearchForm, type RouteSearchValues } from "../../components/routing/RouteSearchForm";
import { fetchRoutes } from "../../api/routes";
import type { RouteCandidate, TransportMode } from "../../types/routing";

// 좌표 변환(geocoding)이 아직 없어서, 검색 시 임시로 목업 origin/destination 좌표를 그대로 사용한다.
// 실제 geocoding이 붙으면 originText/destinationText -> LatLng 변환 로직만 이 자리에 추가하면 된다.
const PLACEHOLDER_ORIGIN = { lat: 37.4671, lng: 126.897 };
const PLACEHOLDER_DESTINATION = { lat: 37.4459, lng: 126.8917 };

// ui-ux-guide.md §3 — congestion_score(0~1, backend.md §7.1 Q1)를 4단계로 정규화해서
// 화면에는 항상 이 라벨/색만 노출하고, 원본 점수는 보조 정보로만 보여준다.
function getCongestionLevel(congestionScore: number) {
  if (congestionScore < 0.4) return { label: "여유", color: "var(--level-calm)" };
  if (congestionScore < 0.6) return { label: "보통", color: "var(--level-normal)" };
  if (congestionScore < 0.8) return { label: "혼잡", color: "var(--level-busy)" };
  return { label: "매우 혼잡", color: "var(--level-packed)" };
}

// path_type의 정확한 enum이 backend.md에 명시돼 있지 않아, 알려진 값만 사람이 읽는 문구로 매핑하고
// 나머지는 원본 문자열을 그대로 보여준다 (백엔드 확정되면 이 매핑만 갱신하면 됨).
const PATH_TYPE_LABEL: Record<string, string> = {
  recommended: "추천 경로",
  fastest: "최단시간 경로",
  bike_transfer: "따릉이 + 지하철",
  bus_direct: "버스 직행",
};

const MODE_ICON: Record<TransportMode, string> = {
  walk: "🚶",
  subway: "🚇",
  bus: "🚌",
  bike: "🚲",
};

export function RouteSearchPage() {
  const [routes, setRoutes] = useState<RouteCandidate[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch(values: RouteSearchValues) {
    setLoading(true);
    const today = new Date().toISOString().slice(0, 10);
    const response = await fetchRoutes({
      origin: PLACEHOLDER_ORIGIN,
      destination: PLACEHOLDER_DESTINATION,
      departAt: `${today}T${values.departAt}:00+09:00`,
    });
    setRoutes(response.routes);
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 20 }}>
      <RouteSearchForm onSearch={handleSearch} />

      {loading && <p style={{ color: "var(--text-sub)" }}>경로 탐색 중...</p>}

      {!loading && routes.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 20 }}>
          {routes.map((route) => {
            const level = getCongestionLevel(route.congestion_score);
            const modes = route.segments.map((segment) => segment.mode);
            return (
              <li
                key={route.id}
                style={{
                  background: "var(--surface)",
                  border: route.is_recommended ? "1px solid var(--primary)" : "1px solid var(--border)",
                  borderLeft: `4px solid ${level.color}`,
                  borderRadius: "var(--radius-card)",
                  boxShadow: "var(--shadow-card)",
                  padding: 16,
                  marginBottom: 12,
                  color: "var(--text)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: 15, fontWeight: 600 }}>{route.total_time_min}분</strong>
                  <span style={{ fontSize: 12, fontWeight: 600, color: level.color }}>{level.label}</span>
                </div>

                {route.is_recommended && (
                  <span
                    style={{
                      display: "inline-block",
                      background: "var(--primary)",
                      color: "white",
                      fontSize: 11,
                      fontWeight: 600,
                      borderRadius: "var(--radius-chip)",
                      padding: "2px 8px",
                      marginTop: 6,
                    }}
                  >
                    가장 여유로운 경로
                  </span>
                )}

                <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 8, fontSize: 13 }}>
                  {modes.map((mode, i) => (
                    <span key={`${mode}-${i}`}>
                      {i > 0 && <span style={{ color: "var(--text-sub)", margin: "0 2px" }}>›</span>}
                      {MODE_ICON[mode]}
                    </span>
                  ))}
                </div>

                <div style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 8 }}>
                  {PATH_TYPE_LABEL[route.path_type] ?? route.path_type} · 분당개선 {route.minute_improvement_ratio}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
