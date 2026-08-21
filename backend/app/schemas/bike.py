from pydantic import BaseModel


class Dock(BaseModel):
    dock_id: int
    dock_name: str
    lat: float
    lng: float
    distance_m: int
    stock: int | None = None


class DockList(BaseModel):
    docks: list[Dock]


class NearbyDock(BaseModel):
    """실시간 공영자전거 API 기준 대여소 — dock_id(내부 DB 번호) 대신 dock_std_id를 쓴다."""

    dock_std_id: str
    name: str
    lat: float
    lng: float
    distance_m: int
    stock: int | None = None


class NearbyDockList(BaseModel):
    docks: list[NearbyDock]


class RoutePoint(BaseModel):
    lat: float
    lng: float


class BikeRoute(BaseModel):
    distance_m: float
    duration_min: float
    geometry: list[RoutePoint]
