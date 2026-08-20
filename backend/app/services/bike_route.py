"""자전거 도로를 따라가는 실제 경로 안내 — Openrouteservice(HeiGIT) Directions API 연동.

Tmap/카카오모빌리티는 일반 개발자에게 자전거 경로 API를 열어주지 않아(2026-08-19 팀 확인),
OSM 데이터 기반의 무료 공개 API인 Openrouteservice로 대체했다. 실제 서울 좌표(강남역→독산사거리)로
직접 호출해 실도로 기반 턴바이턴 경로(도로명까지 정상)가 나오는 것까지 확인했다.

무료 티어 쿼터가 하루 2,000건으로 한정돼 있어서, 동일 출발/도착 좌표 요청은 Redis에 캐싱해
쿼터를 아낀다 — 도로망은 실시간으로 안 바뀌므로 따릉이 재고 캐시(90초)와 달리 TTL을 길게(24시간)
준다.
"""
import json
import os
from typing import Optional

import httpx

from app.core.redis import get_client

_BASE = "https://api.openrouteservice.org/v2/directions/cycling-regular"
_CACHE_TTL = 60 * 60 * 24  # 24시간 — 도로망은 실시간으로 안 바뀌므로 길게 캐싱해 쿼터 절약


def _cache_key(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> str:
    # 소수점 5자리(~1m)까지만 써서, 미세하게 다른 좌표라도 같은 캐시를 재사용하게 한다.
    return f"bike:route:{origin_lat:.5f}:{origin_lng:.5f}:{dest_lat:.5f}:{dest_lng:.5f}"


def get_bike_route(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> Optional[dict]:
    """자전거 경로(거리/소요시간/좌표열)를 반환한다. 실패하거나 키가 없으면 None."""
    r = get_client()
    key = _cache_key(origin_lat, origin_lng, dest_lat, dest_lng)

    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)

    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                _BASE,
                params={
                    "api_key": api_key,
                    "start": f"{origin_lng},{origin_lat}",
                    "end": f"{dest_lng},{dest_lat}",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return None

    try:
        feature = data["features"][0]
        segment = feature["properties"]["segments"][0]
        # GeoJSON 좌표는 [lng, lat] 순서다 — 프론트에서 헷갈리지 않도록 {lat, lng} 객체로 바꿔 준다.
        geometry = [
            {"lat": lat, "lng": lng} for lng, lat in feature["geometry"]["coordinates"]
        ]
    except (KeyError, IndexError):
        return None

    result = {
        "distance_m": segment["distance"],
        "duration_min": round(segment["duration"] / 60, 1),
        "geometry": geometry,
    }
    r.set(key, json.dumps(result), ex=_CACHE_TTL)
    return result
