import { useState } from "react";
import { RouteSearchForm, type RouteSearchValues } from "../../components/routing/RouteSearchForm";
import { RouteMap } from "../../components/routing/RouteMap";
import { fetchRoutes, RouteSearchError } from "../../api/routes";
import type { RouteCandidate, TransportMode } from "../../types/routing";

// 좌표 변환(geocoding)이 아직 없어서, 검색 시 임시로 목업 origin/destination 좌표를 그대로 사용한다.
// 실제 geocoding이 붙으면 originText/destinationText -> LatLng 변환 로직만 이 자리에 추가하면 된다.
const PLACEHOLDER_ORIGIN = { lat: 37.4671, lng: 126.897 };
const PLACEHOLDER_DESTINATION = { lat: 37.4459, lng: 126.8917 };

// frontend-plan.md §3.3에 정의된 에러코드별 UI 처리.
type SearchErrorKind = "invalid_input" | "no_candidate" | "quota_exceeded" | "upstream_error";

interface SearchError {
  kind: SearchErrorKind;
  message: string;
}

const ERROR_BY_STATUS: Record<number, SearchError> = {
  400: { kind: "invalid_input", message: "출발지를 다시 선택해 주세요." },
  404: { kind: "no_candidate", message: "추천 경로를 찾지 못했습니다." },
  429: { kind: "quota_exceeded", message: "잠시 후 다시 시도해 주세요." },
  502: { kind: "upstream_error", message: "연동 시스템에 문제가 발생했습니다." },
};

function toSearchError(err: unknown): SearchError {
  if (err instanceof RouteSearchError && ERROR_BY_STATUS[err.status]) {
    return ERROR_BY_STATUS[err.status];
  }
  return { kind: "upstream_error", message: "알 수 없는 오류가 발생했습니다." };
}

// ⚠️ 지금은 mock이 항상 성공만 반환해서 위 에러 상태들을 실제로 볼 방법이 없다.
// 도착지에 이 키워드를 입력하면 해당 에러 화면을 미리 확인할 수 있는 임시 QA 트리거 —
// VITE_API_BASE_URL로 실제 백엔드에 붙이면 이 분기는 지워도 된다.
const DEBUG_ERROR_TRIGGER: Record<string, SearchError> = {
  "테스트400": ERROR_BY_STATUS[400],
  "테스트404": ERROR_BY_STATUS[404],
  "테스트429": ERROR_BY_STATUS[429],
  "테스트502": ERROR_BY_STATUS[502],
};

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
  const [selectedRouteId, setSelectedRouteId] = useState<number | null>(null);
  const [error, setError] = useState<SearchError | null>(null);
  const [lastValues, setLastValues] = useState<RouteSearchValues | null>(null);

  async function handleSearch(values: RouteSearchValues) {
    setLoading(true);
    setError(null);
    setSelectedRouteId(null);
    setLastValues(values);

    const debugError = DEBUG_ERROR_TRIGGER[values.destinationText.trim()];
    if (debugError) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      setRoutes([]);
      setError(debugError);
      setLoading(false);
      return;
    }

    try {
      const today = new Date().toISOString().slice(0, 10);
      const response = await fetchRoutes({
        origin: PLACEHOLDER_ORIGIN,
        destination: PLACEHOLDER_DESTINATION,
        departAt: `${today}T${values.departAt}:00+09:00`,
      });
      if (response.routes.length === 0) {
        setRoutes([]);
        setError(ERROR_BY_STATUS[404]);
      } else {
        setRoutes(response.routes);
      }
    } catch (err) {
      setRoutes([]);
      setError(toSearchError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 20 }}>
      <RouteSearchForm onSearch={handleSearch} />

      {loading && <p style={{ color: "var(--text-sub)" }}>경로 탐색 중...</p>}

      {!loading && error?.kind === "invalid_input" && (
        <p style={{ color: "var(--level-packed)", fontSize: 13, marginTop: 12 }}>{error.message}</p>
      )}

      {!loading && error?.kind === "quota_exceeded" && (
        <div
          style={{
            background: "var(--surface-muted)",
            color: "var(--text)",
            borderRadius: "var(--radius-control)",
            padding: 12,
            marginTop: 12,
            fontSize: 13,
          }}
        >
          {error.message}
        </div>
      )}

      {!loading && error?.kind === "no_candidate" && (
        <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-sub)" }}>
          <p>{error.message}</p>
        </div>
      )}

      {!loading && error?.kind === "upstream_error" && (
        <div style={{ textAlign: "center", padding: "32px 0" }}>
          <p style={{ color: "var(--text-sub)", marginBottom: 12 }}>{error.message}</p>
          <button
            type="button"
            onClick={() => lastValues && handleSearch(lastValues)}
            style={{
              background: "var(--primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-control)",
              padding: "10px 20px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            재시도
          </button>
        </div>
      )}

      {!loading && !error && routes.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 20 }}>
          {routes.map((route) => {
            const level = getCongestionLevel(route.congestion_score);
            const modes = route.segments.map((segment) => segment.mode);
            const isSelected = selectedRouteId === route.id;
            return (
              <li
                key={route.id}
                onClick={() => setSelectedRouteId(isSelected ? null : route.id)}
                style={{
                  background: "var(--surface)",
                  border: route.is_recommended ? "1px solid var(--primary)" : "1px solid var(--border)",
                  borderLeft: `4px solid ${level.color}`,
                  borderRadius: "var(--radius-card)",
                  boxShadow: "var(--shadow-card)",
                  padding: 16,
                  marginBottom: 12,
                  color: "var(--text)",
                  cursor: "pointer",
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

                {isSelected && (
                  <div style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
                    <RouteMap segments={route.segments} lineColor={level.color} />
                    <ol style={{ listStyle: "none", padding: 0, marginTop: 8, fontSize: 12 }}>
                      {route.segments.map((segment, i) => (
                        <li
                          key={i}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            padding: "6px 0",
                            borderTop: i > 0 ? "1px solid var(--border)" : "none",
                            color: "var(--text)",
                          }}
                        >
                          <span>
                            {MODE_ICON[segment.mode]} {segment.mode}
                          </span>
                          <span style={{ color: "var(--text-sub)" }}>{segment.duration_min}분</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
