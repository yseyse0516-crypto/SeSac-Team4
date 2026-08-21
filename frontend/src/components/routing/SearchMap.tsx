import { useEffect, useRef, useState } from "react";
import type { LatLng, RouteCandidate } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { rankRouteColors } from "../../constants/routeRanking";
import { fetchNearbyDocks, type NearbyDock } from "../../api/bike";
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
  onPick: (point: LatLng, label?: string) => void;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
  showBikeToggle?: boolean;
}

// 좌표를 실제 주소 문자열로 바꾼다(역지오코딩) — 도로명 주소가 있으면 그걸 우선하고,
// 없으면 지번 주소로 폴백한다. 실패하면 null(호출부가 좌표 문자열로 폴백).
function reverseGeocode(point: LatLng): Promise<string | null> {
  return new Promise((resolve) => {
    const kakao = window.kakao;
    const geocoder = new kakao.maps.services.Geocoder();
    geocoder.coord2Address(point.lng, point.lat, (result: any[], status: string) => {
      if (status !== kakao.maps.services.Status.OK || !result[0]) {
        resolve(null);
        return;
      }
      const address = result[0].road_address?.address_name ?? result[0].address?.address_name ?? null;
      resolve(address);
    });
  });
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
  const polylinesRef = useRef<any[]>([]);
  // 클릭 리스너는 지도 생성 시 딱 한 번만 붙이고, activePicker/onPick의 "최신 값"은 ref로
  // 읽는다 — 그래야 이 값들이 바뀔 때마다 리스너를 떼었다 다시 붙일 필요가 없다.
  const activePickerRef = useRef(activePicker);
  const onPickRef = useRef(onPick);
  const [showDocks, setShowDocks] = useState(false);
  const [pin, setPin] = useState<{ x: number; y: number } | null>(null);
  const [status, setStatus] = useState<"no-key" | "loading" | "ready" | "error">(
    KAKAO_MAP_KEY ? "loading" : "no-key"
  );

  useEffect(() => {
    activePickerRef.current = activePicker;
  }, [activePicker]);
  useEffect(() => {
    onPickRef.current = onPick;
  }, [onPick]);

  const displayedRoutes = capRoutesPerLevel(onlyRecommended ? routes.filter((r) => r.is_recommended) : routes);

  // 지도는 딱 한 번만 만든다 — 예전엔 center가 바뀔 때마다(출발지/도착지 선택 모드 전환 등)
  // 지도 객체를 통째로 새로 만들었는데, 클릭 리스너는 별도 useEffect가 status를 기준으로
  // 다시 붙이는 구조였다. 근데 재생성 직후 setStatus("ready")를 "ready"로 다시 불러도
  // React는 값이 안 바뀌었다고 보고 그 useEffect를 재실행하지 않아서, 새로 만들어진 지도엔
  // 클릭 리스너가 하나도 안 붙은 채로 남아 탭이 전혀 먹지 않는 버그가 있었다. 이제 지도는
  // 한 번만 만들고, 이후엔 이동/폴리라인 갱신만 한다.
  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current || mapRef.current) return;

    let cancelled = false;
    loadKakaoMaps(KAKAO_MAP_KEY)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        const kakao = window.kakao;
        const map = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(center.lat, center.lng),
          level: 5,
        });
        mapRef.current = map;

        function handleClick(mouseEvent: any) {
          const picker = activePickerRef.current;
          if (!picker) return;
          const latlng = mouseEvent.latLng;
          if (pickMarkerRef.current) pickMarkerRef.current.setMap(null);
          pickMarkerRef.current = new kakao.maps.Marker({ map, position: latlng });
          const point = { lat: latlng.getLat(), lng: latlng.getLng() };
          onPickRef.current(point);
          reverseGeocode(point).then((address) => {
            if (address) onPickRef.current(point, address);
          });
        }
        kakao.maps.event.addListener(map, "click", handleClick);

        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // center가 바뀌면(출발지/도착지 확정, 검색 결과 등) 기존 지도를 그 위치로 이동만 시킨다.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    mapRef.current.setCenter(new window.kakao.maps.LatLng(center.lat, center.lng));
  }, [status, center.lat, center.lng]);

  // 경로 폴리라인 — routes/onlyRecommended가 바뀔 때마다 기존 선을 지우고 새로 그린다.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    const map = mapRef.current;

    polylinesRef.current.forEach((line) => line.setMap(null));
    polylinesRef.current = [];

    if (displayedRoutes.length === 0) return;

    const bounds = new kakao.maps.LatLngBounds();
    // 색은 실제 혼잡도 절대값이 아니라 지금 보여주는 후보들 사이의 순위로 정한다 — 추천
    // 경로가 항상 초록, 나머지는 혼잡도가 낮은 순으로 노랑→빨강.
    const rankColors = rankRouteColors(displayedRoutes);
    // 추천 경로를 나중에(위에) 그려서 다른 경로 선에 덮이지 않게 한다.
    const ordered = [...displayedRoutes].sort((a, b) => Number(a.is_recommended) - Number(b.is_recommended));
    ordered.forEach((route) => {
      const color = rankColors.get(route.id) ?? getCongestionLevel(route.congestion_score).color;
      // polyline이 있으면(지하철/버스/도보 구간의 실제 선로·도로 곡선) 그대로 쓰고,
      // 없으면(매칭 실패/키 미설정) start-end 직선으로 폴백한다.
      const path = route.segments
        .flatMap((segment) =>
          segment.polyline && segment.polyline.length > 0 ? segment.polyline : [segment.start, segment.end]
        )
        .map((point) => new kakao.maps.LatLng(point.lat, point.lng));
      path.forEach((point: any) => bounds.extend(point));

      const polyline = new kakao.maps.Polyline({
        map,
        path,
        strokeWeight: route.is_recommended ? 6 : 3,
        strokeColor: color,
        strokeOpacity: route.is_recommended ? 1 : 0.5,
        strokeStyle: "solid",
      });
      polylinesRef.current.push(polyline);
    });
    map.setBounds(bounds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, onlyRecommended, routes.length]);

  // 따릉이 대여소 마커 — 토글을 켤 때마다 현재 지도 중심 근처 실제 대여소를 실시간 API로
  // 받아와서 찍는다(지도를 다시 그리진 않고 마커만 추가/제거).
  useEffect(() => {
    const kakao = window.kakao;
    if (!mapRef.current || !kakao || status !== "ready") return;

    dockMarkersRef.current.forEach((marker) => marker.setMap(null));
    dockMarkersRef.current = [];

    if (!showDocks) return;

    let cancelled = false;
    const mapCenter = mapRef.current.getCenter();
    fetchNearbyDocks({ lat: mapCenter.getLat(), lng: mapCenter.getLng() }).then((docks: NearbyDock[]) => {
      if (cancelled || !mapRef.current) return;
      dockMarkersRef.current = docks.map(
        (dock) =>
          new kakao.maps.Marker({
            map: mapRef.current,
            position: new kakao.maps.LatLng(dock.lat, dock.lng),
            title: `${dock.name} (${dock.stock == null ? "재고 정보 없음" : `${dock.stock}대`})`,
          })
      );
    });

    return () => {
      cancelled = true;
    };
  }, [showDocks, status]);

  function renderLegend() {
    if (status === "error" || displayedRoutes.length === 0) return null;
    const rankColors = rankRouteColors(displayedRoutes);
    return (
      <div className="search-map__legend">
        {displayedRoutes.map((route) => {
          const level = getCongestionLevel(route.congestion_score);
          const color = rankColors.get(route.id) ?? level.color;
          return (
            <span key={route.id} className="search-map__legend-item">
              <span className="search-map__dot" style={{ background: color }} />
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
