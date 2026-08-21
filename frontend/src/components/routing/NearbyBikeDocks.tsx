import { useEffect, useState } from "react";
import { fetchNearbyDocks, type NearbyDock } from "../../api/bike";
import type { LatLng } from "../../types/routing";
import "./NearbyBikeDocks.css";

interface NearbyBikeDocksProps {
  from: LatLng;
}

// 회의록: "지금 있는 위치에서 근처 따릉이 대여소 거리까지" 보여주는 패널 — 실시간 공영자전거
// API에서 이름/좌표/재고를 바로 받아온다(오프라인 배치 결과물인 rental_dock엔 아직 4행뿐이라
// 못 씀, backend/app/services/bike_stock.py의 get_nearby_docks 참고).
export function NearbyBikeDocks({ from }: NearbyBikeDocksProps) {
  const [docks, setDocks] = useState<NearbyDock[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchNearbyDocks(from).then((result) => {
      if (!cancelled) setDocks(result);
    });
    return () => {
      cancelled = true;
    };
  }, [from.lat, from.lng]);

  return (
    <div className="nearby-bike-docks">
      <h3 className="nearby-bike-docks__title">내 위치 근처 따릉이 대여소</h3>
      {docks.length === 0 && <p className="nearby-bike-docks__empty">근처 대여소를 찾을 수 없어요.</p>}
      {docks.map((dock) => (
        <div key={dock.dock_std_id} className="nearby-bike-docks__item">
          <span className="nearby-bike-docks__name">{dock.name}</span>
          <span
            className={
              !dock.stock
                ? "nearby-bike-docks__meta nearby-bike-docks__meta--empty"
                : "nearby-bike-docks__meta"
            }
          >
            {dock.distance_m}m · {!dock.stock ? "재고 없음" : `${dock.stock}대`}
          </span>
        </div>
      ))}
    </div>
  );
}
