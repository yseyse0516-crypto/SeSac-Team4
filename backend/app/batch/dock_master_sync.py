"""전국 공영자전거 대여소 마스터 동기화.

행안부 한국지역정보개발원 "전국 공영자전거 실시간 정보" API 중 대여소 정보
엔드포인트(inf_101_00010001_v2)를 호출해 rental_dock 마스터를 채운다.

배경 (B팀 확인, 2026-08-20):
서울시 대여소 마스터 파일(...대여소현황.csv)의 "대여소번호"는 이 API의 rntstnId와
전혀 다른 체계라 매칭이 안 된다(실제 API 응답으로 재현 확인). 반면 이 엔드포인트는
rntstnId + 이름 + 위경도를 그 자체로 제공하므로, 좌표 기반 fuzzy matching 없이
이 API 응답을 그대로 마스터로 삼으면 된다 — 실시간 재고 조회(bike_stock.py)가
쓰는 rntstnId와 동일한 값이라 조인이 저절로 맞는다.

⚠️ 2026-08-20 수정 사항 (원본 초안 대비):
원본 초안은 `location(type='DOCK', ext_code, ...)` 통합 테이블에 쓰도록 되어
있었는데, 이는 재우(DB담당)의 예전 개인용 확장판 스키마(이제 팀 공식 범위 아님)
기준이었다. 팀 실제 공식 스키마(backend/sql/01_schema.sql, B 작성분)에는 그런
통합 location 테이블이 없고, 대신 rental_dock(dock_id, dock_std_id, dock_name,
lat, lng) 전용 테이블이 있다 — 원본 그대로 실행했으면 "relation location does
not exist" 로 배치가 즉시 실패했을 것. 아래는 실제 rental_dock 테이블 기준으로
INSERT 대상만 고쳤고, API 연동 로직(페이지네이션, 인증키 unquote, lot 필드명
등)은 원본과 동일하다.

주의:
- 이 엔드포인트는 거치대 수(capacity)를 제공하지 않는다. 팀 실제 스키마의
  rental_dock 테이블에는 애초에 capacity 컬럼 자체가 없으므로(용량 정보는 이번
  범위에서 제외하기로 확정됨), 이 동기화는 용량 관련 컬럼을 아예 다루지 않는다.
  용량 정보가 나중에 필요해지면 컬럼 추가 + 별도 매칭이 필요하다(이번 범위 밖).
- 인증키는 공공데이터포털 URL-인코딩 원본을 .env에 그대로 넣고, 코드에서
  unquote()로 디코딩해서 사용해야 한다(이중 인코딩 시 인증 실패 — B팀이 실제로
  재현 확인함).
- lat/lng 필드명 주의: 이 API는 경도 필드명이 'lng'가 아니라 'lot'이다(표준과
  다름, 실제 응답으로 확인).
- rental_dock.dock_std_id는 NULL을 허용하는 UNIQUE 컬럼이다(배치가 아직 채우지
  않은 기존 행을 위한 설계) — 이 동기화가 채우는 값은 항상 non-null이므로
  ON CONFLICT (dock_std_id) 그대로 안전하게 동작한다(Postgres UNIQUE는 NULL끼리는
  서로 충돌시키지 않는다).

사용법 (배치 러너에서, 커밋은 호출부 책임):
    from app.batch.dock_master_sync import sync_dock_master
    with db.get_cursor() as cur:
        n = sync_dock_master(cur)
        cur.connection.commit()
"""
import os
from urllib.parse import unquote

import httpx

_BASE = "https://apis.data.go.kr/B551982/pbdo_v2/inf_101_00010001_v2"
_SEOUL_CODE = "1100000000"

# 팀 실제 스키마(backend/sql/01_schema.sql)의 rental_dock 컬럼명 기준.
# dock_std_id UNIQUE 제약에 ON CONFLICT로 UPSERT한다(부분 인덱스 아님 — rental_dock은
# 도크 전용 테이블이라 location처럼 type 구분이 필요 없음).
_UPSERT_SQL = """
    INSERT INTO rental_dock (dock_std_id, dock_name, lat, lng)
    VALUES (%(dock_std_id)s, %(dock_name)s, %(lat)s, %(lng)s)
    ON CONFLICT (dock_std_id)
    DO UPDATE SET dock_name = EXCLUDED.dock_name, lat = EXCLUDED.lat, lng = EXCLUDED.lng
"""


def _fetch_seoul_docks() -> list[dict]:
    """서울(lcgvmnInstCd=1100000000) 대여소 마스터 전체를 페이지네이션으로 가져온다."""
    raw_key = os.getenv("BIKE_STOCK_API_KEY")
    if not raw_key:
        return []
    key = unquote(raw_key)  # 이중 인코딩 방지 — bike_stock.py의 재고 조회와 동일한 이유

    docks: list[dict] = []
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
                docks.append(
                    {
                        "dock_std_id": item["rntstnId"],
                        "dock_name": item["rntstnNm"],
                        "lat": float(item["lat"]),
                        "lng": float(item["lot"]),  # 이 API는 경도 필드명이 lot임에 주의
                    }
                )
            total = body.get("totalCount", 0)
            if not items or page * 1000 >= total:
                break
            page += 1
    return docks


def sync_dock_master(cur) -> int:
    """대여소 마스터를 rental_dock에 UPSERT한다. 반영된 행 수를 반환한다.

    cur: psycopg cursor. 배치 러너가 관리하는 트랜잭션을 그대로 쓰고, 커밋/롤백은
    호출부(배치 러너) 책임으로 둔다.
    """
    docks = _fetch_seoul_docks()
    for dock in docks:
        cur.execute(_UPSERT_SQL, dock)
    return len(docks)
