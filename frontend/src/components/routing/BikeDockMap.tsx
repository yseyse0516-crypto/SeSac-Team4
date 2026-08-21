import { useEffect, useRef, useState } from "react";
import type { LatLng } from "../../types/routing";
import type { NearbyDock } from "../../api/bike";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import "./BikeDockMap.css";

interface BikeDockMapProps {
  center: LatLng;
  docks: NearbyDock[];
  selectedIds: string[];
  onToggleSelected: (dockId: string) => void;
}

// 자전거 탭 전용 지도 — 다른 탭(전체 지도/지하철 노선도)처럼 핀을 눌러서 고르는 방식.
// 핀을 누르면 이름/남은 자전거 수 말풍선이 뜨고, 동시에 거리 비교 대상으로도 선택된다
// (리스트에서 고르는 것과 같은 selectedIds를 공유 — 지도에서 눌러도 리스트에서 누른 것과 동일하게 동작).
export function BikeDockMap({ center, docks, selectedIds, onToggleSelected }: BikeDockMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const meOverlayRef = useRef<any>(null);
  const dockOverlaysRef = useRef<Map<string, any>>(new Map());
  const infoOverlaysRef = useRef<any[]>([]);
  const onToggleRef = useRef(onToggleSelected);
  const [status, setStatus] = useState<"no-key" | "loading" | "ready" | "error">(
    KAKAO_MAP_KEY ? "loading" : "no-key"
  );

  useEffect(() => {
    onToggleRef.current = onToggleSelected;
  }, [onToggleSelected]);

  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current || mapRef.current) return;
    let cancelled = false;
    loadKakaoMaps(KAKAO_MAP_KEY)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        const kakao = window.kakao;
        mapRef.current = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(center.lat, center.lng),
          level: 4,
        });
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

  // 내 위치가 바뀌면 지도 중심만 이동.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    mapRef.current.setCenter(new window.kakao.maps.LatLng(center.lat, center.lng));
  }, [status, center.lat, center.lng]);

  // 내 위치 핀 — 항상 하나만.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    if (meOverlayRef.current) meOverlayRef.current.setMap(null);
    const el = document.createElement("div");
    el.className = "bike-dock-map__me-pin";
    el.textContent = "내 위치";
    meOverlayRef.current = new kakao.maps.CustomOverlay({
      map: mapRef.current,
      position: new kakao.maps.LatLng(center.lat, center.lng),
      content: el,
      yAnchor: 1.2,
      zIndex: 10,
    });
  }, [status, center.lat, center.lng]);

  // 대여소 핀 — docks가 바뀔 때마다 다시 그린다. 선택된 핀은 다른 색으로 강조.
  useEffect(() => {
    if (status !== "ready" || !mapRef.current) return;
    const kakao = window.kakao;
    const map = mapRef.current;

    dockOverlaysRef.current.forEach((overlay) => overlay.setMap(null));
    dockOverlaysRef.current = new Map();

    docks.forEach((dock) => {
      const el = document.createElement("div");
      el.className = selectedIds.includes(dock.dock_std_id)
        ? "bike-dock-map__dock-pin bike-dock-map__dock-pin--selected"
        : "bike-dock-map__dock-pin";
      el.textContent = "🚲";
      el.addEventListener("click", () => onToggleRef.current(dock.dock_std_id));
      const overlay = new kakao.maps.CustomOverlay({
        map,
        position: new kakao.maps.LatLng(dock.lat, dock.lng),
        content: el,
        yAnchor: 1,
        zIndex: 5,
      });
      dockOverlaysRef.current.set(dock.dock_std_id, overlay);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, docks, selectedIds]);

  // 핀 정보 말풍선 — 선택된(최대 2개) 대여소 위에 이름/남은 자전거 수를 띄운다.
  useEffect(() => {
    infoOverlaysRef.current.forEach((overlay) => overlay.setMap(null));
    infoOverlaysRef.current = [];
    if (status !== "ready" || !mapRef.current) return;

    const kakao = window.kakao;
    selectedIds.forEach((id) => {
      const dock = docks.find((d) => d.dock_std_id === id);
      if (!dock) return;

      const el = document.createElement("div");
      el.className = "bike-dock-map__info";
      const nameEl = document.createElement("div");
      nameEl.className = "bike-dock-map__info-name";
      nameEl.textContent = dock.name;
      const stockEl = document.createElement("div");
      stockEl.className = "bike-dock-map__info-stock";
      stockEl.textContent = dock.stock == null ? "재고 정보 없음" : `남은 자전거 ${dock.stock}대`;
      el.appendChild(nameEl);
      el.appendChild(stockEl);

      const overlay = new kakao.maps.CustomOverlay({
        map: mapRef.current,
        position: new kakao.maps.LatLng(dock.lat, dock.lng),
        content: el,
        yAnchor: 2.4,
        zIndex: 20,
      });
      infoOverlaysRef.current.push(overlay);
    });
  }, [status, selectedIds, docks]);

  if (KAKAO_MAP_KEY && status !== "error") {
    return (
      <div className="bike-dock-map">
        <div ref={containerRef} className="bike-dock-map__canvas" />
        <span className="bike-dock-map__hint">핀을 눌러 대여소 정보를 보고, 두 곳을 고르면 거리를 비교해요</span>
      </div>
    );
  }

  return (
    <div className="bike-dock-map">
      <div className="bike-dock-map__fallback">
        <span>
          {status === "error" ? "지도를 불러오지 못했습니다." : "지도 미리보기는 카카오맵 키 설정 후 표시됩니다."}
        </span>
      </div>
    </div>
  );
}
