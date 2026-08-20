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


class RoutePoint(BaseModel):
    lat: float
    lng: float


class BikeRoute(BaseModel):
    distance_m: float
    duration_min: float
    geometry: list[RoutePoint]
