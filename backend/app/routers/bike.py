from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.core import db
from app.schemas.bike import BikeRoute, Dock, DockList, NearbyDock, NearbyDockList
from app.services import bike_route, bike_stock

router = APIRouter(tags=["bike"])


@router.get("/bike/docks/nearby", response_model=NearbyDockList)
def get_nearby_bike_docks(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(800, ge=1, le=5000),
) -> NearbyDockList:
    """지도 위 대여소 핀 표시용 — dock_hub_distance(배치) 대신 실시간 공영자전거 API 좌표를
    그대로 써서, 임의의 지도 중심 좌표 주변 대여소를 바로 찾는다."""
    docks = bike_stock.get_nearby_docks(lat, lng, radius_m)
    return NearbyDockList(docks=[NearbyDock(**d) for d in docks])


@router.get("/bike/docks", response_model=DockList)
def get_bike_docks(
    hub_type: Literal["STATION", "BUS_STOP"] = Query(...),
    hub_id: int = Query(...),
    max_distance: int = Query(500, ge=1, le=5000),
) -> DockList:
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT rd.dock_id, rd.dock_std_id, rd.dock_name, rd.lat, rd.lng, dhd.distance_m "
            "FROM dock_hub_distance dhd "
            "JOIN rental_dock rd ON rd.dock_id = dhd.dock_id "
            "WHERE dhd.hub_type = %s AND dhd.hub_id = %s AND dhd.distance_m <= %s "
            "AND dhd.batch_id = ("
            "  SELECT batch_id FROM batch_run WHERE status = 'success' "
            "  ORDER BY started_at DESC LIMIT 1"
            ") "
            "ORDER BY dhd.distance_m",
            (hub_type, hub_id, max_distance),
        )
        rows = cur.fetchall()

    docks = []
    for row in rows:
        dock_std_id = row.pop("dock_std_id", None)
        docks.append(Dock(**row, stock=bike_stock.get_stock(dock_std_id)))

    return DockList(docks=docks)


@router.get("/bike/route", response_model=BikeRoute)
def get_bike_route(
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    dest_lat: float = Query(...),
    dest_lng: float = Query(...),
) -> BikeRoute:
    """출발지→대여소(혹은 임의 두 지점) 간 자전거 도로 기반 실제 경로.

    Openrouteservice 호출 실패/쿼터 초과 시 502로 응답한다 — 이 경로가 없어도 대여소
    목록·거리 표시(GET /bike/docks) 자체는 별개로 계속 동작해야 하므로, 프론트는 이 호출
    실패를 전체 화면 에러로 처리하지 않는 게 좋다.
    """
    route = bike_route.get_bike_route(origin_lat, origin_lng, dest_lat, dest_lng)
    if route is None:
        raise HTTPException(status_code=502, detail={"code": "ROUTE_UNAVAILABLE"})
    return BikeRoute(**route)
