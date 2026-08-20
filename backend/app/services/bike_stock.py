"""전국 공영자전거 실시간 정보 API(행정안전부 한국지역정보개발원) 연동.

국토교통부 API와 같은 공공데이터포털 서비스키를 재사용한다. 서울만 쓰므로
lcgvmnInstCd=1100000000으로 고정.

⚠️ 이 API의 rntstnId(예: "ST-10")는 서울시 대여소 마스터의 "대여소 번호"(예: "102")와
다른 체계라 매칭 안 됨 — dock_std_id는 rntstnId 기준으로 통일해서 저장해야 한다.

매 요청마다 부르면 낭비라 Redis에 전체 서울 대여소 재고를 짧게 캐싱해두고 읽는다.
"""
import os
from typing import Optional
from urllib.parse import unquote

import httpx

from app.core.redis import get_client

_BASE = "https://apis.data.go.kr/B551982/pbdo_v2/inf_101_00010002_v2"
_SEOUL_CODE = "1100000000"
_CACHE_KEY = "bike:seoul:stock"
_CACHE_TTL = 90  # 초 — 실시간이지만 매 요청마다 부르지 않도록 짧게 캐싱


def _fetch_seoul_stock() -> dict[str, int]:
    """서울 전체 대여소의 실시간 대여 가능 대수를 rntstnId 기준으로 가져온다."""
    raw_key = os.getenv("BIKE_STOCK_API_KEY")
    if not raw_key:
        return {}
    # httpx params가 값을 다시 인코딩하므로, 이미 인코딩된 키를 그대로 넘기면 이중 인코딩됨.
    key = unquote(raw_key)

    result: dict[str, int] = {}
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
                result[item["rntstnId"]] = int(item["bcyclTpkctNocs"])
            total = body.get("totalCount", 0)
            if not items or page * 1000 >= total:
                break
            page += 1
    return result


def get_stock(dock_std_id: Optional[str]) -> Optional[int]:
    """dock_std_id(=rntstnId, 예: 'ST-10')의 실시간 대여 가능 대수. 못 찾으면 None."""
    if not dock_std_id:
        return None

    r = get_client()
    cached = r.hget(_CACHE_KEY, dock_std_id)
    if cached is not None:
        return int(cached)

    if not r.exists(_CACHE_KEY):
        fresh = _fetch_seoul_stock()
        if fresh:
            r.hset(_CACHE_KEY, mapping=fresh)
            r.expire(_CACHE_KEY, _CACHE_TTL)
        return fresh.get(dock_std_id)

    return None
