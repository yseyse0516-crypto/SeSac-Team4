"""전국 공영자전거 실시간 정보 API(행정안전부 한국지역정보개발원) 연동.

국토교통부 API와 같은 공공데이터포털 서비스키를 재사용한다. 서울만 쓰므로
lcgvmnInstCd=1100000000으로 고정.

⚠️ 이 API의 rntstnId(예: "ST-10")는 서울시 대여소 마스터의 "대여소 번호"(예: "102")와
다른 체계라 매칭 안 됨 — dock_std_id는 rntstnId 기준으로 통일해서 저장해야 한다.

이 API 응답엔 재고(bcyclTpkctNocs)뿐 아니라 대여소 이름(rntstnNm)·좌표(lat/lot)도 그대로
들어있다 — rental_dock 테이블(배치가 아직 이 지도 화면용 조회 경로까지는 안 붙어있어서)에
기대지 않고, 지도에 대여소 핀을 찍거나 근처 대여소를 찾는 기능은 전부 이 실시간 API
하나로 처리한다.

매 요청마다 부르면 낭비라 Redis에 전체 서울 대여소 정보를 짧게 캐싱해두고 읽는다.
"""
import json
import math
import os
from typing import Optional
from urllib.parse import unquote

import httpx

from app.core.redis import get_client

_BASE = "https://apis.data.go.kr/B551982/pbdo_v2/inf_101_00010002_v2"
_SEOUL_CODE = "1100000000"
_DOCKS_CACHE_KEY = "bike:seoul:docks"
_CACHE_TTL = 90  # 초 — 실시간이지만 매 요청마다 부르지 않도록 짧게 캐싱


def _fetch_seoul_docks() -> list[dict]:
    """서울 전체 대여소의 실시간 정보(대여소ID/이름/좌표/재고)를 전부 가져온다."""
    raw_key = os.getenv("BIKE_STOCK_API_KEY")
    if not raw_key:
        return []
    # httpx params가 값을 다시 인코딩하므로, 이미 인코딩된 키를 그대로 넘기면 이중 인코딩됨.
    key = unquote(raw_key)

    result: list[dict] = []
    page = 1
    with httpx.Client(timeout=10.0) as client:
        while True:
            resp = client.get(
                _BASE,
                params={
                    "serviceKey": key,
                    "pageNo": page,
                    "numOfRows": 1000,
                    "type": "json",
                    "lcgvmnInstCd": _SEOUL_CODE,
                },
            )
            resp.raise_for_status()
            body = resp.json().get("body", {})
            items = body.get("item") or []
            for item in items:
                result.append(
                    {
                        "dock_std_id": item["rntstnId"],
                        # rntstnNm은 "{대여소번호}. {이름}" 형식이라 번호 접두어는 잘라낸다.
                        "name": item["rntstnNm"].split(". ", 1)[-1],
                        "lat": float(item["lat"]),
                        "lng": float(item["lot"]),
                        "stock": int(item["bcyclTpkctNocs"]),
                    }
                )
            total = body.get("totalCount", 0)
            if not items or page * 1000 >= total:
                break
            page += 1
    return result


def _get_cached_docks() -> list[dict]:
    r = get_client()
    cached = r.get(_DOCKS_CACHE_KEY)
    if cached is not None:
        return json.loads(cached)

    fresh = _fetch_seoul_docks()
    if fresh:
        r.set(_DOCKS_CACHE_KEY, json.dumps(fresh), ex=_CACHE_TTL)
    return fresh


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_m = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def get_stock(dock_std_id: Optional[str]) -> Optional[int]:
    """dock_std_id(=rntstnId, 예: 'ST-10')의 실시간 대여 가능 대수. 못 찾으면 None."""
    if not dock_std_id:
        return None
    docks = _get_cached_docks()
    return next((d["stock"] for d in docks if d["dock_std_id"] == dock_std_id), None)


def get_nearby_docks(lat: float, lng: float, radius_m: int = 800, limit: int = 30) -> list[dict]:
    """주어진 좌표 반경(radius_m) 안의 실시간 대여소를 거리순으로 반환한다.

    지도에 핀을 찍는 용도라 dock_hub_distance(배치) 대신 실시간 API 좌표를 그대로 쓴다.
    """
    docks = _get_cached_docks()
    nearby = []
    for d in docks:
        dist = round(_haversine_m(lat, lng, d["lat"], d["lng"]))
        if dist <= radius_m:
            nearby.append({**d, "distance_m": dist})
    nearby.sort(key=lambda d: d["distance_m"])
    return nearby[:limit]
