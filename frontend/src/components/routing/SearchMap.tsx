import { useEffect, useRef, useState } from "react";
import type { LatLng, RouteCandidate } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { BIKE_DOCKS } from "../../constants/bikeDocks";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import "./SearchMap.css";

// 지도는 화면에 하나만 둔다 — 검색폼 위에 상시로 떠 있고, 출발지/도착지를 지도에서 찍는 것과
// 검색 결과 경로(폴리라인/범례)를 보여주는 것 둘 다 이 지도 하나에서 처리한다.
// (이전엔 위치찍기용 LocationPickerMap과 결과표시용 RouteOverviewMap이 따로 있었는데, 이 컴포넌트로 통합했다.)

// 혼잡도 레벨(여유/보통/혼잡/매우혼잡)당 최대 2개까지만 그리고 범례에 띄운다 — 후보가
// 많을 때 지도/범례가 색이 겹치는 선·항목으로 뒤덮여 복잡해지는 걸 막는다.
const MAX_PER_LEVEL = 2;

function capRoutesPerLevel(routes: RouteCandidate[]): RouteCandidate[] {
  const counts = new Map<string, number>();
  const result: RouteCandidate[] = [];
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

type ActivePicker = "origin" | "destination" | null;

interface SearchMapProps {
  center: LatLng;
  activePicker: ActivePicker;
  onPick: (point: LatLng) => void;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
  showBikeToggle?: boolean;
}

export function SearchMap({
  center,
  activePicker,
  onPick,
  routes,
  onlyRecommended,
  showBikeToggle,
}: SearchMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const pickMarkerRef = useRef<any>(null);
  const dockMarkersRef = useRef<any[]>([]);
  const [showDocks, setShowDocks] = useState(false);
  const [pin, setPin] = useState<{ x: number; y: number } | null>(null);
  const [status, setStatus] = useState<"no-key" | "loading" | "ready" | "error">(
    KAKAO_MAP_KEY ? "loading" : "no-key"
  );

  const displayedRoutes = capRoutesPerLevel(onlyRecommended ? routes.filter((r) => r.is_recommended) : routes);

  // 지도 생성 + 경로 폴리라인 그리기.
  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current) return;

    let cancelled = false;
    setStatus((s) => (s === "ready" ? s : "loading"));
    loadKakaoMaps(KAKAO_MAP_KEY)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        const kakao = window.kakao;
        const firstPoint = displayedRoutes[0]?.segments[0]?.start ?? center;
        const map = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(firstPoint.lat, firstPoint.lng),
          level: displayedRoutes.length > 0 ? 7 : 5,
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
              .flatMap((segment) =>
                segment.polyline && segment.polyline.length > 0 ? segment.polyline : [segment.start, segment.end]
              )
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

  // 출발지/도착지 찍기 — activePicker가 켜져 있을 때만 지도 클릭이 좌표를 넘긴다.
  useEffect(() => {
    const kakao = window.kakao;
    if (status !== "ready" || !mapRef.current || !kakao) return;

    const map = mapRef.current;
    function handleClick(mouseEvent: any) {
      if (!activePicker) return;
      const latlng = mouseEvent.latLng;
      if (pickMarkerRef.current) pickMarkerRef.current.setMap(null);
      pickMarkerRef.current = new kakao.maps.Marker({ map, position: latlng });
      onPick({ lat: latlng.getLat(), lng: latlng.getLng() });
    }

    kakao.maps.event.addListener(map, "click", handleClick);
    return () => kakao.maps.event.removeListener(map, "click", handleClick);
  }, [status, activePicker, onPick]);

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

  function renderLegend() {
    if (status === "error" || displayedRoutes.length === 0) return null;
    return (
      <div className="search-map__legend">
        {displayedRoutes.map((route) => {
          const level = getCongestionLevel(route.congestion_score);
          return (
            <span key={route.id} className="search-map__legend-item">
              <span className="search-map__dot" style={{ background: level.color }} />
              {route.total_time_min}분 · {level.label}
              {route.is_recommended && " · 추천"}
            </span>
          );
        })}
      </div>
    );
  }

  if (KAKAO_MAP_KEY && status !== "error") {
    return (
      <div className="search-map">
        <div ref={containerRef} className="search-map__canvas" />
        {activePicker && <span className="search-map__hint">지도를 탭해서 위치를 지정하세요</span>}
        {showBikeToggle && status === "ready" && (
          <button
            type="button"
            className="search-map__bike-toggle"
            onClick={() => setShowDocks((v) => !v)}
            aria-label="근처 따릉이 대여소 표시"
            title="근처 따릉이 대여소 표시"
          >
            🚲
          </button>
        )}
        {renderLegend()}
      </div>
    );
  }

  function handleFallbackClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!activePicker) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setPin({ x, y });

    // 박스 중앙을 center 좌표로 보고, 클릭 위치의 상대 오프셋을 위경도 근사값으로 변환.
    const dx = (x - rect.width / 2) / rect.width;
    const dy = (y - rect.height / 2) / rect.height;
    onPick({ lat: center.lat - dy * 0.02, lng: center.lng + dx * 0.02 });
  }

  return (
    <div className="search-map">
      <div className="search-map__fallback" onClick={handleFallbackClick}>
        <span className="search-map__message">
          {status === "error"
            ? "지도를 불러오지 못했습니다."
            : activePicker
              ? "카카오맵 키 설정 전 임시 시뮬레이션 — 클릭해서 위치 지정"
              : "지도 미리보기는 카카오맵 키 설정 후 표시됩니다 (VITE_KAKAO_MAP_KEY)."}
        </span>
        {pin && (
          <span className="search-map__pin" style={{ left: pin.x, top: pin.y }}>
            📍
          </span>
        )}
      </div>
      {renderLegend()}
    </div>
  );
}
