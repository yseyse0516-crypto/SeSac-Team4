import { useEffect, useState } from "react";
import type { RouteCandidate } from "../../types/routing";
import { RouteDirections } from "./RouteDirections";
import "./RouteComparisonTable.css";

type ComparisonSelection = "fastest" | "recommended" | null;
type ComparisonTab = "recommended" | "compare";

interface RouteComparisonTableProps {
  routes: RouteCandidate[];
  // "전체" 탭에서 지도가 선택된 경로를 같이 보여줘야 해서, 선택 상태를 상위(RouteSearchPage)로 끌어올렸다.
  selected: ComparisonSelection;
  onSelectedChange: (value: ComparisonSelection) => void;
}

function levelLabel(score: number) {
  if (score < 0.4) return "여유";
  if (score < 0.6) return "보통";
  if (score < 0.8) return "혼잡";
  return "매우 혼잡";
}

// 회의록: 기본 화면은 "덜 혼잡한(추천)" 경로 하나만 보여주고, 최단시간과의 비교는 별도 탭으로
// 뺀다. "자세히 비교 보기" 토글은 없애고, 가는 방법(RouteDirections)은 굳이 누르지 않아도
// 항상 보이게 한다 — 추천 탭은 추천 경로 기준으로, 비교 탭은 고른 카드 기준으로.
export function RouteComparisonTable({ routes, selected, onSelectedChange }: RouteComparisonTableProps) {
  const [tab, setTab] = useState<ComparisonTab>("recommended");
  const fastest = routes.find((r) => r.is_fastest) ?? routes[0];
  const recommended = routes.find((r) => r.is_recommended) ?? routes[0];

  // "추천 경로" 탭이 메인 화면 역할을 하므로, 이 탭에 있을 때는 지도(전체 탭)도 항상 추천
  // 경로를 가리키게 동기화한다. "비교" 탭으로 넘어가면 카드를 직접 고르기 전까진 개요로 되돌린다.
  useEffect(() => {
    onSelectedChange(tab === "recommended" ? "recommended" : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, recommended?.id, fastest?.id]);

  if (!fastest || !recommended) return null;

  const compareSelectedRoute = selected === "fastest" ? fastest : selected === "recommended" ? recommended : null;

  return (
    <div className="route-comparison">
      <div className="route-comparison__tabs">
        <button
          type="button"
          className={
            tab === "recommended" ? "route-comparison__tab route-comparison__tab--active" : "route-comparison__tab"
          }
          onClick={() => setTab("recommended")}
        >
          추천 경로
        </button>
        <button
          type="button"
          className={
            tab === "compare" ? "route-comparison__tab route-comparison__tab--active" : "route-comparison__tab"
          }
          onClick={() => setTab("compare")}
        >
          최단시간과 비교
        </button>
      </div>

      {tab === "recommended" ? (
        <>
          <div className="route-comparison__summary">
            <div className="route-comparison__summary-card route-comparison__summary-card--recommended route-comparison__summary-card--static">
              <span className="route-comparison__summary-label">★ 추천(덜 혼잡)</span>
              <strong className="route-comparison__summary-time">{recommended.total_time_min}분</strong>
              <span className="route-comparison__summary-sub">혼잡도 {levelLabel(recommended.congestion_score)}</span>
            </div>
          </div>
          <p className="route-comparison__directions-label">추천 경로로 가는 방법</p>
          <RouteDirections route={recommended} />
        </>
      ) : (
        <>
          <div className="route-comparison__summary">
            <button
              type="button"
              className="route-comparison__summary-card"
              onClick={() => onSelectedChange(selected === "fastest" ? null : "fastest")}
            >
              <span className="route-comparison__summary-label">최단시간</span>
              <strong className="route-comparison__summary-time">{fastest.total_time_min}분</strong>
              <span className="route-comparison__summary-sub">혼잡도 {levelLabel(fastest.congestion_score)}</span>
            </button>
            <button
              type="button"
              className="route-comparison__summary-card route-comparison__summary-card--recommended"
              onClick={() => onSelectedChange(selected === "recommended" ? null : "recommended")}
            >
              <span className="route-comparison__summary-label">★ 추천(덜 혼잡)</span>
              <strong className="route-comparison__summary-time">{recommended.total_time_min}분</strong>
              <span className="route-comparison__summary-sub">
                혼잡도 {levelLabel(recommended.congestion_score)}
              </span>
            </button>
          </div>

          {compareSelectedRoute && (
            <>
              <p className="route-comparison__directions-label">
                {selected === "fastest" ? "최단시간 경로로 가는 방법" : "추천 경로로 가는 방법"}
              </p>
              <RouteDirections route={compareSelectedRoute} />
            </>
          )}

          <table className="route-comparison__table">
            <thead>
              <tr>
                <th></th>
                <th>최단시간</th>
                <th>추천(덜 혼잡)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>소요시간</td>
                <td>{fastest.total_time_min}분</td>
                <td>{recommended.total_time_min}분</td>
              </tr>
              <tr>
                <td>혼잡도</td>
                <td>{levelLabel(fastest.congestion_score)}</td>
                <td>{levelLabel(recommended.congestion_score)}</td>
              </tr>
              <tr>
                <td>분당개선</td>
                <td>{fastest.minute_improvement_ratio}</td>
                <td>{recommended.minute_improvement_ratio}</td>
              </tr>
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
