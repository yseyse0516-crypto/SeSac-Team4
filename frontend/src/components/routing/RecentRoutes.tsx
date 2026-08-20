import { useEffect, useState } from "react";
import { clearRecentRoutes, getRecentRoutes, type RecentRouteEntry } from "../../utils/recentRoutes";
import "./RecentRoutes.css";

// 회의록: "지난번에 이용했던 경로를 남겨뒀으면 함" — 샌드박스 데모용 localStorage 기반 최근 경로.
export function RecentRoutes({ refreshKey }: { refreshKey: number }) {
  const [entries, setEntries] = useState<RecentRouteEntry[]>([]);

  useEffect(() => {
    setEntries(getRecentRoutes());
  }, [refreshKey]);

  if (entries.length === 0) return null;

  return (
    <div className="recent-routes">
      <div className="recent-routes__header">
        <h3 className="recent-routes__title">최근 이용한 경로 (이 브라우저에만 저장됨)</h3>
        <button
          type="button"
          className="recent-routes__clear"
          onClick={() => {
            clearRecentRoutes();
            setEntries([]);
          }}
        >
          전체 삭제
        </button>
      </div>
      {entries.map((entry) => (
        <div key={`${entry.route.id}-${entry.savedAt}`} className="recent-routes__item">
          <span>
            <strong>{entry.route.total_time_min}분</strong> · {entry.route.path_type}
          </span>
          <span>{new Date(entry.savedAt).toLocaleString("ko-KR")}</span>
        </div>
      ))}
    </div>
  );
}
