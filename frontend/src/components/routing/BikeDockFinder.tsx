import { useEffect, useState } from "react";
import { fetchNearbyDocks, type NearbyDock } from "../../api/bike";
import { distanceMeters } from "../../utils/distance";
import type { LatLng } from "../../types/routing";
import { BikeDockMap } from "./BikeDockMap";
import "./BikeDockFinder.css";

// Geolocation 실패/미허용 시 기준점으로 쓸 서울시청 좌표.
const DEFAULT_CENTER: LatLng = { lat: 37.5665, lng: 126.978 };

// 회의록: 자전거 탭은 출발지/도착지 검색이 아니라 "내 위치 근처 대여소 + 대여소 간 거리"만
// 보여주는 단순한 화면으로 — 다른 탭과 달리 검색 폼/즐겨찾기/출발시각 없음.
export function BikeDockFinder() {
  const [center, setCenter] = useState<LatLng>(DEFAULT_CENTER);
  const [locating, setLocating] = useState(true);
  const [docks, setDocks] = useState<NearbyDock[]>([]);
  const [loadingDocks, setLoadingDocks] = useState(false);
  // 대여소 간 거리 비교용 — 지도 핀이나 리스트에서 최대 2개까지 고른다(3번째를 고르면
  // 가장 오래된 걸 뺀다). 핀을 고르면 그 자리에 이름/남은 자전거 수 말풍선도 같이 뜬다.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocating(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 5000 }
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadingDocks(true);
    fetchNearbyDocks(center).then((result) => {
      if (cancelled) return;
      setDocks(result);
      setLoadingDocks(false);
    });
    return () => {
      cancelled = true;
    };
  }, [center.lat, center.lng]);

  function toggleSelected(dockId: string) {
    setSelectedIds((prev) => {
      if (prev.includes(dockId)) return prev.filter((id) => id !== dockId);
      const next = [...prev, dockId];
      return next.length > 2 ? next.slice(next.length - 2) : next;
    });
  }

  const selectedDocks = selectedIds
    .map((id) => docks.find((d) => d.dock_std_id === id))
    .filter((d): d is NearbyDock => !!d);
  const pairDistance =
    selectedDocks.length === 2 ? Math.round(distanceMeters(selectedDocks[0], selectedDocks[1])) : null;

  return (
    <div className="bike-dock-finder">
      <h2 className="bike-dock-finder__title">내 위치 근처 따릉이 대여소</h2>
      <p className="bike-dock-finder__hint">
        {locating
          ? "현재 위치 확인 중..."
          : "지도의 🚲 핀을 누르면 대여소 정보를 보고, 두 곳을 고르면 거리도 비교할 수 있어요."}
      </p>

      <BikeDockMap center={center} docks={docks} selectedIds={selectedIds} onToggleSelected={toggleSelected} />

      {pairDistance != null && (
        <div className="bike-dock-finder__pair-distance">
          <strong>{selectedDocks[0].name}</strong> ↔ <strong>{selectedDocks[1].name}</strong> 거리:{" "}
          <strong>{pairDistance}m</strong>
        </div>
      )}

      <div className="bike-dock-finder__list">
        {loadingDocks && <p className="bike-dock-finder__empty">대여소를 찾는 중...</p>}
        {!loadingDocks && docks.length === 0 && (
          <p className="bike-dock-finder__empty">근처 대여소를 찾을 수 없어요.</p>
        )}
        {!loadingDocks && docks.length > 0 && (
          <p className="bike-dock-finder__list-hint">두 곳을 선택하면 대여소 간 거리를 보여줘요.</p>
        )}
        {docks.map((dock) => {
          const selected = selectedIds.includes(dock.dock_std_id);
          return (
            <button
              key={dock.dock_std_id}
              type="button"
              className={
                selected ? "bike-dock-finder__item bike-dock-finder__item--selected" : "bike-dock-finder__item"
              }
              onClick={() => toggleSelected(dock.dock_std_id)}
            >
              <span className="bike-dock-finder__name">{dock.name}</span>
              <span
                className={
                  !dock.stock
                    ? "bike-dock-finder__meta bike-dock-finder__meta--empty"
                    : "bike-dock-finder__meta"
                }
              >
                내 위치에서 {dock.distance_m}m · {!dock.stock ? "재고 없음" : `${dock.stock}대`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
