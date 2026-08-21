import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.core import db
from app.schemas.bike import BikeRoute, Dock, DockList
from app.services import bike_route, bike_stock

router = APIRouter(tags=["bike"])

NEARBY_EARTH_RADIUS_M = 6371000


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * NEARBY_EARTH_RADIUS_M * math.asin(math.sqrt(a))


@router.get("/bike/docks/nearby", response_model=DockList)
def get_bike_docks_nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(800, ge=1, le=5000),
) -> DockList:
    """임의 좌표(내 위치 등) 근처 대여소 조회.

    `/bike/docks`(hub_type/hub_id 기준)는 경로 검색 결과의 역/정류장을 기준으로
    조회하는 용도로 설계됐다(backend.md §6, 2026-08-19) — 그 시점엔 "내 위치 근처"
    좌표 기반 조회는 계획에 없었다. 이후 프론트 자전거 탭이 좌표 기반으로 동작하도록
    구현되면서 계약에 없는 엔드포인트를 호출하게 됐고, 이번에 그 좌표 기반 조회 자체를
    추가해 계약을 맞춘다. `/bike/docks`는 그대로 유지 — 경로 검색 흐름은 계속 그걸 쓴다.

    weight_repository.match_subway_station과 동일한 방식(원시 SQL + Python haversine,
    PostGIS 미사용)으로 rental_dock 전체를 훑는다 — 대여소 규모가 커지면 bbox 사전
    필터를 추가할 수 있지만, 지금 규모에서는 불필요하다.
    """
    with db.get_cursor() as cur:
        cur.execute("SELECT dock_id, dock_std_id, dock_name, lat, lng FROM rental_dock")
        rows = cur.fetchall()

    candidates = []
    for row in rows:
        dist = _haversine_m(lat, lng, float(row["lat"]), float(row["lng"]))
        if dist <= radius_m:
            candidates.append((dist, row))
    candidates.sort(key=lambda item: item[0])

    docks = [
        Dock(
            dock_id=row["dock_id"],
            dock_name=row["dock_name"],
            lat=row["lat"],
            lng=row["lng"],
            distance_m=int(dist),
            stock=bike_stock.get_stock(row["dock_std_id"]),
        )
        for dist, row in candidates
    ]
    return DockList(docks=docks)


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
