"""도보 구간 실제 보행자 경로 — SK Tmap 보행자경로안내 API.

`TMAP_APP_KEY`가 없으면(2026-08-19 저녁 기준, 키 발급 진행 중) 네트워크 호출 자체를
안 하고 바로 None을 반환해서 기존 직선 처리로 자연스럽게 폴백한다 — ODsay처럼 "키 없으면
fixture로 대체"하지 않는 이유는, 도보는 임의의 두 좌표 사이라 재사용 가능한 고정 fixture가
의미 없기 때문(지하철/버스는 노선이라는 재사용 단위가 있어서 fixture가 유효했음).

⚠️ 이 파일 작성 시점엔 실제 키가 없어서 라이브 호출로 응답 형태를 검증하지 못했다. 아래
파싱은 Tmap 공식 문서 기준(GeoJSON FeatureCollection — Point들은 턴바이턴 안내용, LineString
여러 개를 순서대로 이어붙이면 전체 경로)이다. 키가 발급되면 odsay_client.py를 라이브로
검증했던 것과 동일한 절차로 반드시 재검증해야 한다(backend.md §13 참고).

버스 노선(line_geometry.get_bus_curve)과 달리 캐싱을 안 한다 — 버스는 "노선번호"라는
재사용 단위가 있어 캐싱 효과가 크지만, 도보는 매번 임의의 두 좌표 사이라 캐시 적중률이
거의 없다. 그래서 TMAP_APP_KEY가 실제로 설정되면 도보 구간마다 매번 실시간 호출이 나간다
— 요청당 도보 구간이 여러 개면 그만큼 지연이 늘어날 수 있다는 점은 알고 있어야 한다.
"""
import os
from typing import Optional

import httpx

TMAP_ENDPOINT = "https://apis.openapi.sk.com/tmap/routes/pedestrian"


def _call_tmap(app_key: str, body: dict) -> dict:
    response = httpx.post(
        f"{TMAP_ENDPOINT}?version=1",
        headers={"appKey": app_key, "Content-Type": "application/json"},
        json=body,
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()


def get_walk_curve(
    start_lat: float, start_lng: float, end_lat: float, end_lng: float
) -> Optional[list]:
    """시작~끝 좌표 사이 실제 보행로 곡선을 [(lat, lng), ...]로 반환. 키 없음/실패/빈
    결과는 전부 None — 프론트는 기존처럼 start/end를 직선으로 이어서 그리면 됨."""
    app_key = os.getenv("TMAP_APP_KEY")
    if not app_key:
        return None

    body = {
        "startX": str(start_lng),
        "startY": str(start_lat),
        "endX": str(end_lng),
        "endY": str(end_lat),
        "startName": "출발",
        "endName": "도착",
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "searchOption": "0",
    }

    try:
        data = _call_tmap(app_key, body)
    except (httpx.HTTPError, ValueError):
        return None

    coords = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            continue
        for lng, lat in geometry.get("coordinates", []):
            coords.append((lat, lng))

    return coords if len(coords) > 1 else None
