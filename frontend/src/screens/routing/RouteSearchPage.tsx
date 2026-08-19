import { useState } from "react";
import { RouteSearchForm, type RouteSearchValues } from "../../components/routing/RouteSearchForm";
import { fetchRoutes } from "../../api/routes";
import type { RouteCandidate, TransportMode } from "../../types/routing";

// 좌표 변환(geocoding)이 아직 없어서, 검색 시 임시로 목업 origin/destination 좌표를 그대로 사용한다.
// 실제 geocoding이 붙으면 originText/destinationText -> LatLng 변환 로직만 이 자리에 추가하면 된다.
const PLACEHOLDER_ORIGIN = { lat: 37.4671, lng: 126.897 };
const PLACEHOLDER_DESTINATION = { lat: 37.4459, lng: 126.8917 };

// ui-ux-guide.md §3 — 지하철 %혼잡도/버스 재차인원처럼 단위가 다른 지표를 4단계로 정규화해서
// 화면에는 항상 이 라벨/색만 노출하고, 원본 숫자(congestionPct)는 보조 정보로만 보여준다.
function getCongestionLevel(congestionPct: number) {
  if (congestionPct < 40) return { label: "여유", color: "var(--level-calm)" };
  if (congestionPct < 60) return { label: "보통", color: "var(--level-normal)" };
  if (congestionPct < 80) return { label: "혼잡", color: "var(--level-busy)" };
  return { label: "매우 혼잡", color: "var(--level-packed)" };
}

const MODE_ICON: Record<TransportMode, string> = {
  WALK: "🚶",
  SUBWAY: "🚇",
  BUS: "🚌",
  BIKE: "🚲",
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
            const level = getCongestionLevel(route.congestionPct);
            return (
              <li
                key={route.routeId}
                style={{
                  background: "var(--surface)",
                  border: route.isRecommended ? "1px solid var(--primary)" : "1px solid var(--border)",
                  borderLeft: `4px solid ${level.color}`,
                  borderRadius: "var(--radius-card)",
                  boxShadow: "var(--shadow-card)",
                  padding: 16,
                  marginBottom: 12,
                  color: "var(--text)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: 15, fontWeight: 600 }}>{route.durationMin}분</strong>
                  <span style={{ fontSize: 12, fontWeight: 600, color: level.color }}>{level.label}</span>
                </div>

                {route.isRecommended && (
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
                  {route.modes.map((mode, i) => (
                    <span key={`${mode}-${i}`}>
                      {i > 0 && <span style={{ color: "var(--text-sub)", margin: "0 2px" }}>›</span>}
                      {MODE_ICON[mode]}
                    </span>
                  ))}
                </div>

                <div style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 8 }}>
                  {route.label} · 여유 인원 {route.netOnboardRemaining}명 · 분당개선 {route.minutePerImprovement}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
