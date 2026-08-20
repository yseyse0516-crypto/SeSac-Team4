import { BIKE_DOCKS } from "../../constants/bikeDocks";
import { distanceMeters } from "../../utils/distance";
import type { LatLng } from "../../types/routing";
import "./NearbyBikeDocks.css";

interface NearbyBikeDocksProps {
  from: LatLng;
}

// 회의록: "지금 있는 위치에서 근처 따릉이 대여소 거리까지" 보여주는 패널.
export function NearbyBikeDocks({ from }: NearbyBikeDocksProps) {
  const sorted = [...BIKE_DOCKS]
    .map((dock) => ({ dock, distance: distanceMeters(from, dock) }))
    .sort((a, b) => a.distance - b.distance);

  return (
    <div className="nearby-bike-docks">
      <h3 className="nearby-bike-docks__title">내 위치 근처 따릉이 대여소</h3>
      {sorted.map(({ dock, distance }) => (
        <div key={dock.id} className="nearby-bike-docks__item">
          <span className="nearby-bike-docks__name">{dock.name}</span>
          <span
            className={
              dock.availableCount === 0
                ? "nearby-bike-docks__meta nearby-bike-docks__meta--empty"
                : "nearby-bike-docks__meta"
            }
          >
            {Math.round(distance)}m · {dock.availableCount === 0 ? "재고 없음" : `${dock.availableCount}대`}
          </span>
        </div>
      ))}
    </div>
  );
}
