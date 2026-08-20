import { useEffect, useRef, useState } from "react";
import type { RouteSegment } from "../../types/routing";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import "./RouteMap.css";

function renderMap(container: HTMLDivElement, segments: RouteSegment[], lineColor: string) {
  const kakao = window.kakao;
  const map = new kakao.maps.Map(container, {
    center: new kakao.maps.LatLng(segments[0].start.lat, segments[0].start.lng),
    level: 6,
  });

  const bounds = new kakao.maps.LatLngBounds();

  segments.forEach((segment) => {
    const path = [
      new kakao.maps.LatLng(segment.start.lat, segment.start.lng),
      new kakao.maps.LatLng(segment.end.lat, segment.end.lng),
    ];
    path.forEach((point: any) => bounds.extend(point));

    // ui-ux-guide.md §4 — 지하철/버스/따릉이 구간은 경로 색으로, 도보는 뉴트럴 점선으로.
    // ⚠️ segment 단위 혼잡도 값이 아직 API 계약(docs/api-contracts/routing.md)에 없어서
    // 지금은 route 전체 congestion_score 색(lineColor)을 그대로 쓴다 — 백엔드에 세그먼트별
    // 값이 추가되면 segment마다 다른 색을 쓰도록 이 부분만 바꾸면 된다.
    const isWalk = segment.mode === "walk";
    new kakao.maps.Polyline({
      map,
      path,
      strokeWeight: 5,
      strokeColor: isWalk ? "#8b93a7" : lineColor,
      strokeOpacity: 0.9,
      strokeStyle: isWalk ? "shortdash" : "solid",
    });

    new kakao.maps.Marker({ map, position: path[0] });
  });

  new kakao.maps.Marker({
    map,
    position: new kakao.maps.LatLng(
      segments[segments.length - 1].end.lat,
      segments[segments.length - 1].end.lng
    ),
  });

  map.setBounds(bounds);
}

interface RouteMapProps {
  segments: RouteSegment[];
  lineColor: string;
}

export function RouteMap({ segments, lineColor }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"no-key" | "loading" | "ready" | "error">(
    KAKAO_MAP_KEY ? "loading" : "no-key"
  );

  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current || segments.length === 0) return;

    let cancelled = false;
    setStatus("loading");
    loadKakaoMaps(KAKAO_MAP_KEY)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        renderMap(containerRef.current, segments, lineColor);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [segments, lineColor]);

  if (status === "no-key") {
    return (
      <div className="route-map route-map--placeholder">
        <span>지도 미리보기는 카카오맵 키 설정 후 표시됩니다 (VITE_KAKAO_MAP_KEY).</span>
        <ol className="route-map__segment-fallback">
          {segments.map((segment, i) => (
            <li key={i}>
              {segment.mode} · {segment.duration_min}분
            </li>
          ))}
        </ol>
      </div>
    );
  }

  if (status === "error") {
    return <div className="route-map route-map--placeholder">지도를 불러오지 못했습니다.</div>;
  }

  return <div ref={containerRef} className="route-map" />;
}
