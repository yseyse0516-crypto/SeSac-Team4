import { useEffect, useRef, useState } from "react";
import type { LatLng, RouteCandidate } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { BIKE_DOCKS } from "../../constants/bikeDocks";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import "./RouteOverviewMap.css";

// 회의록: 지도/따릉이 탭은 검색 전에도 지도가 상시로 떠 있어야 한다 — routes가 비어있어도
// center 기준으로 기본 지도를 그린다. 검색 결과가 있으면 그 위에 경로 선을 얹는다.
// 추천 경로는 초록 굵은 선, 나머지는 얇고 반투명하게. "추천 경로만 보기" 토글은 옵션 바
// (RouteSearchPage)로 이동했고, 여기서는 그 값을 prop으로만 받는다.
// 따릉이 탭에서는 지도 위 🚲 토글로 대여소 마커를 켜고 끌 수 있다(따릉이 앱처럼).

interface RouteOverviewMapProps {
  routes: RouteCandidate[];
  center: LatLng;
  showBikeToggle?: boolean;
  onlyRecommended: boolean;
}

// 혼잡도 레벨(여유/보통/혼잡/매우혼잡)당 최대 2개까지만 그리고 범례에 띄운다 — 후보가
// 많을 때 지도/범례가 색이 겹치는 선·항목으로 뒤덮여 복잡해지는 걸 막는다.
const MAX_PER_LEVEL = 2;

function capRoutesPerLevel(routes: RouteCandidate[]): RouteCandidate[] {
  const counts = new Map<string, number>();
  const result: RouteCandidate[] = [];
  // 추천 경로가 잘려나가지 않도록 먼저 배치한 뒤 나머지를 원래 순서대로 채운다.
  const prioritized = [...routes].sort((a, b) => Number(b.is_recommended) - Number(a.is_recommended));
  for (const route of prioritized) {
    const label = getCongestionLevel(route.congestion_score).label;
    const count = counts.get(label) ?? 0;
    if (count >= MAX_PER_LEVEL) continue;
    counts.set(label, count + 1);
    result.push(route);
  }
  return result;
}

export function RouteOverviewMap({ routes, center, showBikeToggle, onlyRecommended }: RouteOverviewMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const dockMarkersRef = useRef<any[]>([]);
  const [showDocks, setShowDocks] = useState(false);
  const [status, setStatus] = useState<"no-key" | "loading" | "ready" | "error">(
    KAKAO_MAP_KEY ? "loading" : "no-key"
  );

  const displayedRoutes = capRoutesPerLevel(onlyRecommended ? routes.filter((r) => r.is_recommended) : routes);

  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current) return;

    let cancelled = false;
    setStatus("loading");
    loadKakaoMaps(KAKAO_MAP_KEY)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        const kakao = window.kakao;
        const firstPoint = displayedRoutes[0]?.segments[0]?.start ?? center;
        const map = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(firstPoint.lat, firstPoint.lng),
          level: displayedRoutes.length > 0 ? 7 : 6,
        });
        mapRef.current = map;

        if (displayedRoutes.length > 0) {
          const bounds = new kakao.maps.LatLngBounds();
          // 추천 경로를 나중에(위에) 그려서 다른 경로 선에 덮이지 않게 한다.
          const ordered = [...displayedRoutes].sort(
            (a, b) => Number(a.is_recommended) - Number(b.is_recommended)
          );
          ordered.forEach((route) => {
            const level = getCongestionLevel(route.congestion_score);
            // polyline이 있으면(지하철/버스/도보 구간의 실제 선로·도로 곡선) 그대로 쓰고,
            // 없으면(매칭 실패/키 미설정) start-end 직선으로 폴백한다.
            const path = route.segments
              .flatMap((segment) => segment.polyline && segment.polyline.length > 0
                ? segment.polyline
                : [segment.start, segment.end])
              .map((point) => new kakao.maps.LatLng(point.lat, point.lng));
            path.forEach((point: any) => bounds.extend(point));

            new kakao.maps.Polyline({
              map,
              path,
              strokeWeight: route.is_recommended ? 6 : 3,
              strokeColor: level.color,
              strokeOpacity: route.is_recommended ? 1 : 0.5,
              strokeStyle: "solid",
            });
          });
          map.setBounds(bounds);
        }

        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyRecommended, routes.length, center.lat, center.lng]);

  // 따릉이 대여소 마커는 지도를 다시 그리지 않고 토글만으로 추가/제거한다.
  useEffect(() => {
    const kakao = window.kakao;
    if (!mapRef.current || !kakao || status !== "ready") return;

    dockMarkersRef.current.forEach((marker) => marker.setMap(null));
    dockMarkersRef.current = [];

    if (showDocks) {
      dockMarkersRef.current = BIKE_DOCKS.map(
        (dock) =>
          new kakao.maps.Marker({
            map: mapRef.current,
            position: new kakao.maps.LatLng(dock.lat, dock.lng),
            title: `${dock.name} (${dock.availableCount}대)`,
          })
      );
    }
  }, [showDocks, status]);

  return (
    <div className="route-overview-map-wrap">
      <div className="route-overview-map__container">
        {KAKAO_MAP_KEY && status !== "error" && <div ref={containerRef} className="route-overview-map" />}

        {(status === "no-key" || status === "error") && (
          <div className="route-overview-map route-overview-map--placeholder">
            {status === "error" ? (
              <span>지도를 불러오지 못했습니다.</span>
            ) : (
              <span>
                지도 미리보기는 카카오맵 키 설정 후 표시됩니다 (VITE_KAKAO_MAP_KEY).
                {displayedRoutes.length === 0 && " 검색하면 여기에 지도가 뜹니다."}
              </span>
            )}
          </div>
        )}

        {showBikeToggle && status === "ready" && (
          <button
            type="button"
            className="route-overview-map__bike-toggle"
            onClick={() => setShowDocks((v) => !v)}
            aria-label="근처 따릉이 대여소 표시"
            title="근처 따릉이 대여소 표시"
          >
            🚲
          </button>
        )}

        {status !== "error" && displayedRoutes.length > 0 && (
          <div className="route-overview-map__legend">
            {displayedRoutes.map((route) => {
              const level = getCongestionLevel(route.congestion_score);
              return (
                <span key={route.id} className="route-overview-map__legend-item">
                  <span className="route-overview-map__dot" style={{ background: level.color }} />
                  {route.total_time_min}분 · {level.label}
                  {route.is_recommended && " · 추천"}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
