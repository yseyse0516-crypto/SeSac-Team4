import { useEffect, useRef, useState } from "react";
import type { LatLng, RouteCandidate } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { SUBWAY_STATIONS, type SubwayStation } from "../../constants/subwayStations";
import { distanceMeters } from "../../utils/distance";
import "./SubwayLineDiagram.css";

// 실제 서울 지하철 노선도(다이어그램형) 이미지 — 서울교통공사 공식 이미지는 저작권이 있어서
// 대신 MIT 라이선스로 공개된 노선도 SVG를 그대로 배경으로 쓴다.
// 출처: https://github.com/Sinseiki/opensource-seoul-subway-map (MIT License,
// public/seoul_subway_map.LICENSE.txt 참고). 역 이름·좌표는 이 SVG의 역 라벨을 전부 추출해
// 카카오 로컬 키워드검색으로 실제 좌표를 붙인 constants/subwayStations.ts(549개 역, 2026-08-21
// 생성)를 그대로 쓴다 — 이 역들을 출발지/도착지로 고르면 실제 ODsay 검색이 그대로 되고,
// 검색 결과가 그 역 근처(±800m)를 지나가면 역 마커를 하이라이트한다.

const MAP_WIDTH = 1150.36;
const MAP_HEIGHT = 1074.59;

type NamedStation = SubwayStation;

const STATIONS: NamedStation[] = SUBWAY_STATIONS;

// 역 근접 매칭 반경 — 검색 결과 segment의 start/end가 이 반경 안이면 "이 역을 지난다"고 본다.
const STATION_MATCH_RADIUS_M = 800;
const STATION_DOT_R = 8;

const BASE_VIEW = { x: 0, y: 0, w: MAP_WIDTH, h: MAP_HEIGHT };
const ZOOM_BOUNDS = { minW: MAP_WIDTH / 6, maxW: MAP_WIDTH * 1.1 };

type View = { x: number; y: number; w: number; h: number };
type ActivePicker = "origin" | "destination" | null;

interface SubwayLineDiagramProps {
  activePicker: ActivePicker;
  onPickStation: (field: "origin" | "destination", station: { name: string; lat: number; lng: number }) => void;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
}

function matchedRouteForStation(station: NamedStation, routes: RouteCandidate[]) {
  const near = (p: LatLng) => distanceMeters(p, station) < STATION_MATCH_RADIUS_M;
  const ordered = [...routes].sort((a, b) => Number(b.is_recommended) - Number(a.is_recommended));
  for (const route of ordered) {
    const hit = route.segments.some((seg) => seg.mode === "subway" && (near(seg.start) || near(seg.end)));
    if (hit) return route;
  }
  return null;
}

// 기본 화면 진입 시 이 정도로 확대해서 보여준다(전체 노선도의 1/3.5 너비) — 현재 위치 기반
// 역이 잡히면 그 역을 중심으로, 못 잡으면 강남 근방을 기본값으로 보여준다.
const DEFAULT_ZOOM_WIDTH = MAP_WIDTH / 3.5;

function viewCenteredOn(station: NamedStation): View {
  const w = DEFAULT_ZOOM_WIDTH;
  const h = w * (BASE_VIEW.h / BASE_VIEW.w);
  return { x: station.x - w / 2, y: station.y - h / 2, w, h };
}

// 드래그(지도 이동)와 탭(역 선택)을 구분하는 최소 이동 거리(px) — 이보다 적게 움직였으면 탭으로 본다.
const DRAG_THRESHOLD_PX = 6;
// 탭 위치와 역 사이 이 거리(px) 안이면 그 역을 선택한 것으로 본다(화면 배율과 무관하게 항상 같은 크기).
const TAP_HIT_RADIUS_PX = 22;

// 위치 조회 실패/거부 시 기본으로 보여줄 역(강남) — 목록이 이름순 정렬이라 STATIONS[0]은
// 엉뚱한 역이 될 수 있어 명시적으로 찾는다.
const FALLBACK_STATION = STATIONS.find((s) => s.name === "강남") ?? STATIONS[0];

export function SubwayLineDiagram({ onPickStation, routes, onlyRecommended }: SubwayLineDiagramProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; lastX: number; lastY: number; moved: boolean } | null>(
    null
  );
  const [view, setView] = useState<View>(() => viewCenteredOn(FALLBACK_STATION));
  const [imageFailed, setImageFailed] = useState(false);
  // 방금 탭한 역 — 위에 "출발지로 설정 / 도착지로 설정" 작은 선택지를 띄운다.
  const [pending, setPending] = useState<NamedStation | null>(null);

  // 진입 시 현재 위치에서 가장 가까운 지원 역을 찾아 그 역을 기본 화면 중심으로 잡는다.
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        const nearest = STATIONS.reduce((closest, station) =>
          distanceMeters(here, station) < distanceMeters(here, closest) ? station : closest
        );
        setView(viewCenteredOn(nearest));
      },
      () => {},
      { timeout: 5000 }
    );
  }, []);

  function handleStationClick(station: NamedStation) {
    setPending((prev) => (prev?.name === station.name ? null : station));
  }

  function choose(field: "origin" | "destination") {
    if (!pending) return;
    onPickStation(field, pending);
    setPending(null);
  }

  // 역의 SVG 좌표를 현재 pan/zoom(view) 기준 화면 좌표로 바꾼다.
  function svgToClient(svgX: number, svgY: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: rect.left + ((svgX - view.x) / view.w) * rect.width,
      y: rect.top + ((svgY - view.y) / view.h) * rect.height,
    };
  }

  // 팝업 위치는 wrapper(포지션 기준 컨테이너) 상대 좌표로 — 확대/축소와 무관하게 항상 같은
  // 크기로, 역 바로 위에 띄우기 위해서다.
  function stationScreenPos(station: NamedStation) {
    const wrapperRect = wrapperRef.current?.getBoundingClientRect();
    const client = svgToClient(station.x, station.y);
    if (!wrapperRect) return { left: 0, top: 0 };
    return { left: client.x - wrapperRect.left, top: client.y - wrapperRect.top };
  }

  function zoomBy(factor: number, pivot?: { x: number; y: number }) {
    setView((prev) => {
      const nextW = Math.min(ZOOM_BOUNDS.maxW, Math.max(ZOOM_BOUNDS.minW, prev.w * factor));
      const nextH = nextW * (BASE_VIEW.h / BASE_VIEW.w);
      const px = pivot?.x ?? prev.x + prev.w / 2;
      const py = pivot?.y ?? prev.y + prev.h / 2;
      const ratioX = (px - prev.x) / prev.w;
      const ratioY = (py - prev.y) / prev.h;
      return { x: px - ratioX * nextW, y: py - ratioY * nextH, w: nextW, h: nextH };
    });
  }

  function toSvgPoint(clientX: number, clientY: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: view.x + ((clientX - rect.left) / rect.width) * view.w,
      y: view.y + ((clientY - rect.top) / rect.height) * view.h,
    };
  }

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    zoomBy(e.deltaY > 0 ? 1.15 : 1 / 1.15, toSvgPoint(e.clientX, e.clientY));
  }

  function handlePointerDown(e: React.PointerEvent<SVGSVGElement>) {
    dragRef.current = { startX: e.clientX, startY: e.clientY, lastX: e.clientX, lastY: e.clientY, moved: false };
    svgRef.current?.setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) > DRAG_THRESHOLD_PX) {
      drag.moved = true;
    }
    const dx = ((e.clientX - drag.lastX) / rect.width) * view.w;
    const dy = ((e.clientY - drag.lastY) / rect.height) * view.h;
    drag.lastX = e.clientX;
    drag.lastY = e.clientY;
    if (drag.moved) {
      setView((prev) => ({ ...prev, x: prev.x - dx, y: prev.y - dy }));
    }
  }

  // 클릭 이벤트 대신 포인터 업 시점에 직접 "이동 없었으면 탭"으로 판정한다 — SVG 개별 요소의
  // onClick은 setPointerCapture(팬 처리용)와 겹치면 브라우저별로 안 눌리는 경우가 있어서
  // (실제로 역을 눌러도 반응이 없던 버그의 원인), 여기서 화면 좌표 기준으로 가장 가까운 역을
  // 직접 찾아 선택한다.
  //
  // onPointerLeave도 이 함수로 연결돼 있는데, 실제 마우스 버튼을 누른 적이 없어도(그냥 커서만
  // 옮겨도) 팝업(HTML, z-index 위)이 SVG 위를 덮으면 "커서 밑 최상단 요소가 바뀌었다"는
  // 이유로 브라우저가 SVG에 pointerleave를 쏜다 — 이걸 "빈 곳을 탭했다"로 오판해서 팝업이
  // 뜨자마자 닫혀버리는 버그가 있었다(drag가 null인데도 탭 판정 로직을 그대로 태웠던 게 원인).
  // 그래서 실제로 SVG 위에서 눌렀다 뗀 경우(drag가 있고, 안 움직인 경우)에만 탭으로 본다.
  function handlePointerUp(e: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    dragRef.current = null;
    svgRef.current?.releasePointerCapture(e.pointerId);
    if (!drag || drag.moved) return;

    let closest: NamedStation | null = null;
    let closestDist = Infinity;
    for (const station of STATIONS) {
      const p = svgToClient(station.x, station.y);
      const d = Math.hypot(p.x - e.clientX, p.y - e.clientY);
      if (d < closestDist) {
        closestDist = d;
        closest = station;
      }
    }

    if (closest && closestDist <= TAP_HIT_RADIUS_PX) {
      handleStationClick(closest);
    } else {
      setPending(null);
    }
  }

  const displayedRoutes = onlyRecommended ? routes.filter((r) => r.is_recommended) : routes;
  const stationMatches = STATIONS.map((station) => ({
    station,
    route: matchedRouteForStation(station, displayedRoutes),
  }));
  const legendRoutes = Array.from(
    new Map(stationMatches.filter((m) => m.route).map((m) => [m.route!.id, m.route!])).values()
  );

  return (
    <div className="subway-line-diagram" ref={wrapperRef}>
      <div className="subway-line-diagram__toolbar">
        <span className="subway-line-diagram__hint">역을 탭해서 출발지/도착지로 선택 · 드래그로 이동 · 스크롤로 확대/축소</span>
        <div className="subway-line-diagram__zoom">
          <button type="button" onClick={() => zoomBy(1 / 1.3)} aria-label="확대">
            +
          </button>
          <button type="button" onClick={() => zoomBy(1.3)} aria-label="축소">
            −
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        {!imageFailed && (
          <image
            href="/seoul_subway_map.svg"
            x={0}
            y={0}
            width={MAP_WIDTH}
            height={MAP_HEIGHT}
            onError={() => setImageFailed(true)}
          />
        )}

        {/* 549개 역 전부에 항상 점을 그리면 배경 이미지 자체의 역 표시와 겹쳐 지저분해 보여서,
            평소엔 아무것도 안 그린다 — 탭 판정은 이 그림과 무관하게 좌표 거리로만 하기 때문에
            점이 없어도 클릭은 그대로 된다. 실제로 뭔가 보여줄 필요가 있는 역만(검색 결과가
            지나가는 역의 혼잡도 링, 방금 탭한 역 표시) 그린다. */}
        {stationMatches.map(({ station, route }) => {
          const level = route ? getCongestionLevel(route.congestion_score) : null;
          const isPending = pending?.name === station.name;
          if (!level && !isPending) return null;
          return (
            <g key={station.name}>
              {level && (
                <circle
                  cx={station.x}
                  cy={station.y}
                  r={STATION_DOT_R * (route?.is_recommended ? 1.8 : 1.4)}
                  fill="none"
                  stroke={level.color}
                  strokeWidth={STATION_DOT_R * 0.4}
                  opacity={route?.is_recommended ? 1 : 0.7}
                />
              )}
              {isPending && <circle cx={station.x} cy={station.y} r={STATION_DOT_R * 0.6} fill="#3d7bff" />}
            </g>
          );
        })}
      </svg>

      {imageFailed && (
        <div className="subway-line-diagram__placeholder">노선도 이미지를 불러오지 못했습니다.</div>
      )}

      {legendRoutes.length > 0 && (
        <div className="subway-line-diagram__legend">
          {legendRoutes.map((route) => {
            const level = getCongestionLevel(route.congestion_score);
            return (
              <span key={route.id} className="subway-line-diagram__legend-item">
                <span className="subway-line-diagram__dot" style={{ background: level.color }} />
                {route.total_time_min}분 · {level.label}
                {route.is_recommended && " · 추천"}
              </span>
            );
          })}
        </div>
      )}

      {pending && (
        <div
          className="subway-line-diagram__popup"
          style={{ left: stationScreenPos(pending).left, top: stationScreenPos(pending).top }}
        >
          <span className="subway-line-diagram__popup-name">{pending.name}역</span>
          <button type="button" onClick={() => choose("origin")}>
            출발지로 설정
          </button>
          <button type="button" onClick={() => choose("destination")}>
            도착지로 설정
          </button>
        </div>
      )}
    </div>
  );
}
