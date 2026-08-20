import { useRef, useState } from "react";
import type { LatLng, RouteCandidate } from "../../types/routing";
import { getCongestionLevel } from "../../constants/congestionLevels";
import { distanceMeters } from "../../utils/distance";
import "./SubwayLineDiagram.css";

// 실제 서울 지하철 노선도(다이어그램형) 이미지 — 서울교통공사 공식 이미지는 저작권이 있어서
// 대신 MIT 라이선스로 공개된 노선도 SVG를 그대로 배경으로 쓴다.
// 출처: https://github.com/Sinseiki/opensource-seoul-subway-map (MIT License,
// public/seoul_subway_map.LICENSE.txt 참고). 이 SVG 자체엔 역 이름/좌표가 프로그램적으로
// 식별 가능한 형태로 들어있지 않아서(디자인 툴 출력이라 그냥 텍스트+원 도형), 자주 쓰는 실존
// 역 몇 개만 SVG 라벨 위치를 직접 찾아 좌표(스키매틱 xy + 실제 lat/lng)를 아래에 박아뒀다.
// 이 역들을 출발지/도착지로 고르면 실제 ODsay 검색이 그대로 되고, 검색 결과가 그 역 근처
// (±800m)를 지나가면 역 마커를 하이라이트한다.

const MAP_WIDTH = 1150.36;
const MAP_HEIGHT = 1074.59;

interface NamedStation {
  name: string;
  lat: number;
  lng: number;
  // seoul_subway_map.svg 안에서 이 역 라벨의 translate(x y) 좌표 (직접 파싱해서 확인함).
  x: number;
  y: number;
}

const STATIONS: NamedStation[] = [
  { name: "강남", lat: 37.4979, lng: 127.0276, x: 829.14, y: 612.01 },
  { name: "역삼", lat: 37.5, lng: 127.0364, x: 855.35, y: 612.3 },
  { name: "선릉", lat: 37.5044, lng: 127.0489, x: 887.35, y: 612.3 },
  { name: "삼성", lat: 37.5089, lng: 127.0632, x: 908.35, y: 611.3 },
  { name: "신도림", lat: 37.5088, lng: 126.8913, x: 604.14, y: 599.5 },
  { name: "구로", lat: 37.503, lng: 126.882, x: 605.35, y: 622.3 },
  { name: "가산디지털단지", lat: 37.4816, lng: 126.8825, x: 582.91, y: 646.27 },
  { name: "독산", lat: 37.465, lng: 126.8974, x: 583.14, y: 671.5 },
  { name: "홍대입구", lat: 37.5568, lng: 126.9237, x: 656.14, y: 495.5 },
  { name: "합정", lat: 37.5495, lng: 126.9137, x: 623.14, y: 519.5 },
  { name: "당산", lat: 37.5343, lng: 126.9027, x: 601.14, y: 544.5 },
  { name: "여의도", lat: 37.5215, lng: 126.9243, x: 653.14, y: 550.5 },
];

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

export function SubwayLineDiagram({ activePicker, onPickStation, routes, onlyRecommended }: SubwayLineDiagramProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  const [view, setView] = useState<View>(BASE_VIEW);
  const [imageFailed, setImageFailed] = useState(false);

  function handleStationClick(station: NamedStation) {
    if (!activePicker) return;
    onPickStation(activePicker, station);
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
    dragRef.current = { x: e.clientX, y: e.clientY };
    svgRef.current?.setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent<SVGSVGElement>) {
    if (!dragRef.current) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = ((e.clientX - dragRef.current.x) / rect.width) * view.w;
    const dy = ((e.clientY - dragRef.current.y) / rect.height) * view.h;
    dragRef.current = { x: e.clientX, y: e.clientY };
    setView((prev) => ({ ...prev, x: prev.x - dx, y: prev.y - dy }));
  }

  function handlePointerUp(e: React.PointerEvent<SVGSVGElement>) {
    dragRef.current = null;
    svgRef.current?.releasePointerCapture(e.pointerId);
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
    <div className="subway-line-diagram">
      <div className="subway-line-diagram__toolbar">
        <span className="subway-line-diagram__hint">
          {activePicker ? "역을 탭해서 위치를 지정하세요" : "드래그로 이동 · 스크롤로 확대/축소"}
        </span>
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

        {stationMatches.map(({ station, route }) => {
          const level = route ? getCongestionLevel(route.congestion_score) : null;
          return (
            <g
              key={station.name}
              onClick={() => handleStationClick(station)}
              style={{ cursor: activePicker ? "pointer" : "default" }}
            >
              <circle cx={station.x} cy={station.y} r={STATION_DOT_R * 2} fill="transparent" />
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
              <circle
                cx={station.x}
                cy={station.y}
                r={STATION_DOT_R * 0.5}
                fill={activePicker ? "#3d7bff" : "#1a1d29"}
              />
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

      <p className="subway-line-diagram__note">
        서울 지하철 노선도(MIT 라이선스 공개 SVG, 출처:{" "}
        <a href="https://github.com/Sinseiki/opensource-seoul-subway-map" target="_blank" rel="noreferrer">
          Sinseiki/opensource-seoul-subway-map
        </a>
        ). 표시된 파란 점은 실제 좌표라 출발지/도착지로 고르면 진짜 검색이 됩니다. 검색 결과가 지나가는 역은
        혼잡도 색 링으로 표시됩니다.
      </p>
    </div>
  );
}
