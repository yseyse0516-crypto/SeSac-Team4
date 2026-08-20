"""지하철 역 마스터 동기화.

입력: backend/app/batch/data/텅텅_지하철역좌표_전체_공식데이터-2026_08_20수정.csv
  (호선/역번호/역명/lat/lng/match_method, 269행, 1~8호선). 국가철도공단(KRIC) 공식
  표준데이터('전체_도시철도역사정보_20260630.xlsx')를 역명 기준으로 매칭해 만든 좌표다.
  자세한 근거: 텅텅_지하철역좌표_OSM매칭_방법론및한계-2026_08_20수정.md

⚠️ station.station_no는 KRIC 공식 역번호가 **아니다**. 이 프로젝트의 방향판정/혼잡도
계산 파이프라인(텅텅_지하철방향별재차인원추정-2026_08_20수정3.csv, getShtrmPath2 실측
기반)이 쓰는 자체 역번호 체계를 그대로 쓴다(예: 왕십리=208, 2호선). 좌표 CSV는 바로
이 역번호 체계에 맞춰 이름으로 매칭해 만들었으므로 station_no 값 자체는 이미 올바르다
— 착각하기 쉬운 지점이라 명시해둔다.

출력: station 테이블에 UPSERT(line_name + station_no 기준, 01_schema.sql의
UNIQUE (line_name, station_no) 제약을 그대로 활용).

사용법 (배치 러너에서):
    from app.batch.station_sync import sync_station_master
    n = sync_station_master(cur)
"""
import csv
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "텅텅_지하철역좌표_전체_공식데이터-2026_08_20수정.csv"

_UPSERT_SQL = """
    INSERT INTO station (station_name, line_name, station_no, lat, lng)
    VALUES (%(station_name)s, %(line_name)s, %(station_no)s, %(lat)s, %(lng)s)
    ON CONFLICT (line_name, station_no)
    DO UPDATE SET station_name = EXCLUDED.station_name,
                  lat = EXCLUDED.lat,
                  lng = EXCLUDED.lng
"""


def _load_rows() -> list[dict]:
    rows = []
    with open(_DATA, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "station_name": r["역명"],
                    "line_name": r["호선"],
                    "station_no": r["역번호"],
                    "lat": float(r["lat"]),
                    "lng": float(r["lng"]),
                }
            )
    return rows


def sync_station_master(cur) -> int:
    """station 테이블을 좌표 CSV 기준으로 UPSERT한다. 반영된 행 수를 반환한다."""
    rows = _load_rows()
    cur.executemany(_UPSERT_SQL, rows)
    return len(rows)
