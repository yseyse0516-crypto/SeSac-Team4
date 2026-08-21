import { useEffect, useRef, useState } from "react";
import type { LatLng, RouteCandidate, TransportMode } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { rankRouteColors } from "../../constants/routeRanking";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import { reverseGeocode } from "../../utils/reverseGeocode";
import "./SearchMap.css";

// "전체" 탭에서 경로 하나를 선택해 상세히 보여줄 때, 구간을 이동수단별로 구분하는 색.
// 회의 요청: 도보=회색, 지하철=파란색, 버스는 파란색/회색과 안 헷갈리는 색으로.
const MODE_COLOR: Record<TransportMode, string> = {
  walk: "#9AA0A6",
  subway: "#2F6FE4",
  bus: "#F97316",
};

const MODE_LABEL: Record<TransportMode, string> = {
  walk: "도보",
  subway: "지하철",
  bus: "버스",
};

function samePoint(a: LatLng, b: LatLng): boolean {
  return Math.abs(a.lat - b.lat) < 1e-5 && Math.abs(a.lng - b.lng) < 1e-5;
}

// 선택된 경로의 구간들을 훑어서 "OO역 승차"/"OO역 하차" 라벨을 만든다. 환승 지점처럼
// 하차 지점과 다음 구간 승차 지점이 같은 좌표면 라벨 두 개를 겹쳐 찍지 않고 "환승"으로 합친다.
function buildStopLabels(route: RouteCandidate): { point: LatLng; text: string }[] {
  const labels: { point: LatLng; text: string }[] = [];
  route.segments
    .filter((segment) => segment.mode !== "walk")
    .forEach((segment) => {
      if (segment.start_name) labels.push({ point: segment.start, text: `${segment.start_name} 승차` });
      if (segment.end_name) labels.push({ point: segment.end, text: `${segment.end_name} 하차` });
    });

  const merged: { point: LatLng; text: string }[] = [];
  for (const label of labels) {
    const prev = merged[merged.length - 1];
    if (prev && samePoint(prev.point, label.point)) {
      prev.text = `${prev.text.replace(/ (승차|하차)$/, "")} 환승`;
    } else {
      merged.push({ ...label });
    }
  }
  return merged;
}

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
  // field를 매번 명시해서 넘긴다 — 역지오코딩 응답이 오는 시점엔 activePicker가 이미
  // null로 리셋돼 있거나(첫 클릭 처리 중 리셋) 다음 클릭으로 다른 필드로 바뀌어 있을 수
  // 있어서, "어느 필드였는지"를 상위가 아닌 이 클릭 시점 값으로 직접 넘겨야 한다.
  onPick: (field: "origin" | "destination", point: LatLng, label?: string) => void;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
  // "전체" 탭에서만 넘어온다 — 출발/도착 핀과, 경로 하나를 선택했을 때의 구간별 상세 표시용.
  origin?: LatLng | null;
  destination?: LatLng | null;
  selectedRoute?: RouteCandidate | null;
}

export function SearchMap({
  center,
  activePicker,
  onPick,
  routes,
  onlyRecommended,
  origin,
  destination,
  selectedRoute,
}: SearchMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const pickMarkerRef = useRef<any>(null);
  const polylinesRef = useRef<any[]>([]);
  const endpointOverlaysRef = useRef<any[]>([]);
  const stopOverlaysRef = useRef<any[]>([]);
  // 클릭 리스너는 지도 생성 시 딱 한 번만 붙이고, activePicker/onPick의 "최신 값"은 ref로
  // 읽는다 — 그래야 이 값들이 바뀔 때마다 리스너를 떼었다 다시 붙일 필요가 없다.
  const activePickerRef = useRef(activePicker);
  const onPickRef = useRef(onPick);
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
          // picker를 지역 변수로 한 번만 읽어서 이 클릭 전체(동기 호출 + 비동기 역지오코딩
          // 응답)에 그대로 쓴다 — activePicker(상태)를 다시 읽으면, 역지오코딩이 끝나기 전에
          // 사용자가 반대쪽 필드를 또 클릭했을 때 그 값으로 덮여서 주소가 엉뚱한 필드에
          // 적용되거나 원래 필드엔 영영 좌표만 남는 버그가 있었다.
          const picker = activePickerRef.current;
          if (!picker) return;
          const latlng = mouseEvent.latLng;
          if (pickMarkerRef.current) pickMarkerRef.current.setMap(null);
          pickMarkerRef.current = new kakao.maps.Marker({ map, position: latlng });
          const point = { lat: latlng.getLat(), lng: latlng.getLng() };
          onPickRef.current(picker, point);
          reverseGeocode(point).then((address) => {
            if (address) onPickRef.current(picker, point, address);
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
  // "전체" 탭에서 최단시간/추천 카드를 선택한 상태(selectedRoute)면, 후보 비교용 혼잡도색
  // 개요선 대신 그 경로 하나만 구간(도보/지하철/버스)별로 색을 다르게 그린다.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    const map = mapRef.current;

    polylinesRef.current.forEach((line) => line.setMap(null));
    polylinesRef.current = [];

    if (selectedRoute) {
      const bounds = new kakao.maps.LatLngBounds();
      selectedRoute.segments.forEach((segment) => {
        const path = (
          segment.polyline && segment.polyline.length > 0 ? segment.polyline : [segment.start, segment.end]
        ).map((point) => new kakao.maps.LatLng(point.lat, point.lng));
        path.forEach((point: any) => bounds.extend(point));

        const polyline = new kakao.maps.Polyline({
          map,
          path,
          strokeWeight: segment.mode === "walk" ? 4 : 6,
          strokeColor: MODE_COLOR[segment.mode],
          strokeOpacity: segment.mode === "walk" ? 0.8 : 1,
          strokeStyle: segment.mode === "walk" ? "shortdash" : "solid",
        });
        polylinesRef.current.push(polyline);
      });
      map.setBounds(bounds);
      return;
    }

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
  }, [status, onlyRecommended, routes.length, selectedRoute]);

  // 출발/도착 핀 — 둘 다 좌표가 있으면(전체 탭에서만 값이 온다) 항상 표시한다.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    const map = mapRef.current;

    endpointOverlaysRef.current.forEach((overlay) => overlay.setMap(null));
    endpointOverlaysRef.current = [];

    if (!origin || !destination) return;

    function addEndpoint(point: LatLng, text: string, variant: "origin" | "destination") {
      const el = document.createElement("div");
      el.className = `search-map__endpoint search-map__endpoint--${variant}`;
      el.textContent = text;
      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(point.lat, point.lng),
        content: el,
        yAnchor: 1.3,
        zIndex: 20,
      });
      overlay.setMap(map);
      endpointOverlaysRef.current.push(overlay);
    }

    addEndpoint(origin, "출발", "origin");
    addEndpoint(destination, "도착", "destination");
  }, [status, origin?.lat, origin?.lng, destination?.lat, destination?.lng]);

  // 선택된 경로의 승차/하차(환승) 지점 라벨 — 경로를 선택했을 때만 보인다.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    const map = mapRef.current;

    stopOverlaysRef.current.forEach((overlay) => overlay.setMap(null));
    stopOverlaysRef.current = [];

    if (!selectedRoute) return;

    buildStopLabels(selectedRoute).forEach(({ point, text }) => {
      const el = document.createElement("div");
      el.className = "search-map__stop-label";
      el.textContent = text;
      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(point.lat, point.lng),
        content: el,
        yAnchor: 1.6,
        zIndex: 15,
      });
      overlay.setMap(map);
      stopOverlaysRef.current.push(overlay);
    });
  }, [status, selectedRoute]);

  function renderLegend() {
    if (status === "error") return null;

    if (selectedRoute) {
      const usedModes = Array.from(new Set(selectedRoute.segments.map((s) => s.mode)));
      return (
        <div className="search-map__legend">
          {usedModes.map((mode) => (
            <span key={mode} className="search-map__legend-item">
              <span className="search-map__dot" style={{ background: MODE_COLOR[mode] }} />
              {MODE_LABEL[mode]}
            </span>
          ))}
        </div>
      );
    }

    if (displayedRoutes.length === 0) return null;
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
    onPick(activePicker, { lat: center.lat - dy * 0.02, lng: center.lng + dx * 0.02 });
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
