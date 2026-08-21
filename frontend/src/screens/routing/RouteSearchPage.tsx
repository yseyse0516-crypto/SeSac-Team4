import { useState } from "react";
import { RouteSearchForm, type RouteSearchValues } from "../../components/routing/RouteSearchForm";
import { ViewModeToolbar, type ViewMode } from "../../components/routing/ViewModeToolbar";
import { BikeDockFinder } from "../../components/routing/BikeDockFinder";
import { RouteComparisonTable } from "../../components/routing/RouteComparisonTable";
import { fetchRoutes, RouteSearchError } from "../../api/routes";
import type { RouteCandidate } from "../../types/routing";
import "./RouteOptionsBar.css";

// frontend-plan.md §3.3에 정의된 에러코드별 UI 처리.
type SearchErrorKind = "invalid_input" | "no_candidate" | "quota_exceeded" | "upstream_error";

interface SearchError {
  kind: SearchErrorKind;
  message: string;
}

// backend/app/routers/search.py 기준: 400 INVALID_INPUT / 404 NO_CANDIDATE /
// 503 UPSTREAM_QUOTA_EXCEEDED(ODsay 일일 쿼터 초과) / 502 UPSTREAM_ERROR.
const ERROR_BY_STATUS: Record<number, SearchError> = {
  400: { kind: "invalid_input", message: "출발지를 다시 선택해 주세요." },
  404: { kind: "no_candidate", message: "추천 경로를 찾지 못했습니다." },
  503: { kind: "quota_exceeded", message: "잠시 후 다시 시도해 주세요." },
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
  "테스트503": ERROR_BY_STATUS[503],
  "테스트502": ERROR_BY_STATUS[502],
};

export function RouteSearchPage() {
  const [routes, setRoutes] = useState<RouteCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<SearchError | null>(null);
  const [lastValues, setLastValues] = useState<RouteSearchValues | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("map");
  const [onlyRecommended, setOnlyRecommended] = useState(false);
  // "전체" 탭에서 최단시간/추천 카드 선택 상태 — 지도가 선택된 경로만 상세히 보여줘야 해서
  // RouteComparisonTable과 RouteSearchForm(지도)이 같이 참조하도록 여기서 들고 있는다.
  const [selectedComparison, setSelectedComparison] = useState<"fastest" | "recommended" | null>(null);

  async function handleSearch(values: RouteSearchValues) {
    setLoading(true);
    setError(null);
    setLastValues(values);
    setSelectedComparison(null);

    const debugError = DEBUG_ERROR_TRIGGER[values.destinationText.trim()];
    if (debugError) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      setRoutes([]);
      setError(debugError);
      setLoading(false);
      return;
    }

    // 지오코딩 실패 등으로 좌표를 못 구한 경우 — 절대 임의 좌표로 조용히 검색하지 않고
    // 명시적으로 에러를 보여준다(예전엔 여기서 목업 좌표로 폴백해 엉뚱한 위치가 검색되는 버그가 있었다).
    if (!values.originCoords || !values.destinationCoords) {
      setRoutes([]);
      setError(ERROR_BY_STATUS[400]);
      setLoading(false);
      return;
    }

    try {
      // "지금 출발"(departureTime 미지정)이면 departure_time을 안 보내고, 백엔드가 현재 시각 기준으로 조회한다.
      const response = await fetchRoutes({
        origin: values.originCoords,
        destination: values.destinationCoords,
        departure_time: values.departureTime,
      });
      if (response.candidates.length === 0) {
        setRoutes([]);
        setError(ERROR_BY_STATUS[404]);
      } else {
        setRoutes(response.candidates);
      }
    } catch (err) {
      setRoutes([]);
      setError(toSearchError(err));
    } finally {
      setLoading(false);
    }
  }

  const selectedRoute =
    selectedComparison === "fastest"
      ? routes.find((r) => r.is_fastest) ?? routes[0] ?? null
      : selectedComparison === "recommended"
        ? routes.find((r) => r.is_recommended) ?? routes[0] ?? null
        : null;

  // 자전거 탭은 출발지/도착지 검색 흐름을 아예 안 쓰는 별도 화면이라(§ 요청: "다른거랑 달리
  // 비교적 심플하게") 여기서 완전히 분기한다.
  if (viewMode === "bike") {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "12px 20px" }}>
        <ViewModeToolbar value={viewMode} onChange={setViewMode} />
        <BikeDockFinder />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "12px 20px" }}>
      <ViewModeToolbar value={viewMode} onChange={setViewMode} />
      <RouteSearchForm
        onSearch={handleSearch}
        searchCategory={viewMode}
        routes={routes}
        onlyRecommended={onlyRecommended}
        selectedRoute={selectedRoute}
      />

      <div className="route-options-bar">
        <button
          type="button"
          className={
            onlyRecommended
              ? "route-options-bar__chip route-options-bar__chip--active"
              : "route-options-bar__chip"
          }
          onClick={() => setOnlyRecommended((v) => !v)}
        >
          추천 경로만 보기
        </button>
      </div>

      {loading && <p style={{ color: "var(--text-sub)", fontSize: 13 }}>경로 탐색 중...</p>}

      {!loading && error?.kind === "invalid_input" && (
        <p style={{ color: "var(--level-packed)", fontSize: 13, marginTop: 8 }}>{error.message}</p>
      )}

      {!loading && error?.kind === "quota_exceeded" && (
        <div
          style={{
            background: "var(--surface-muted)",
            color: "var(--text)",
            borderRadius: "var(--radius-control)",
            padding: 10,
            marginTop: 8,
            fontSize: 13,
          }}
        >
          {error.message}
        </div>
      )}

      {!loading && error?.kind === "no_candidate" && (
        <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-sub)" }}>
          <p>{error.message}</p>
        </div>
      )}

      {!loading && error?.kind === "upstream_error" && (
        <div style={{ textAlign: "center", padding: "20px 0" }}>
          <p style={{ color: "var(--text-sub)", marginBottom: 10, fontSize: 13 }}>{error.message}</p>
          <button
            type="button"
            onClick={() => lastValues && handleSearch(lastValues)}
            style={{
              background: "var(--primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-control)",
              padding: "8px 18px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            재시도
          </button>
        </div>
      )}

      {!loading && !error && routes.length > 0 && lastValues?.originCoords && (
        <RouteComparisonTable
          routes={routes}
          selected={selectedComparison}
          onSelectedChange={setSelectedComparison}
        />
      )}
    </div>
  );
}
