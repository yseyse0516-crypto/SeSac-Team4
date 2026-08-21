"""지하철 역별 가중치(station_weight) 동기화.

입력: backend/app/batch/data/텅텅_지하철방향별재차인원추정-2026_08_20수정3.csv
  (호선/역번호/역명/상하구분/요일유형/시간대/혼잡도/승차_추정/하차_추정/재차인원_추정/
   판정방식/방향판정신뢰도/판정근거, 32,280행). getShtrmPath2 실측으로 확정한 방향판정
   규칙 기반 최종본이다 — 자세한 근거는 텅텅_지하철방향별재차인원추정_방법론및한계-
   2026_08_20수정3.md 참고.

이 모듈이 하는 일 5가지 (전부 원본 CSV에 없어 이 배치가 직접 계산/변환하는 부분):
  1) station_id 조회 — station 테이블을 (line_name, station_no)로 미리 로드해 매핑.
  2) 요일유형(평일/토요일/일요일) → dow(0~6) 변환.
  3) 시간대(예: '08-09시간대') → time_slot(예: '08:00-09:00') 표준 포맷 변환.
  4) stop_sequence 계산 — 원본 CSV엔 이 컬럼이 아예 없다. 실제 값(열차운행시각표
     기반 출고역 이후 정차 횟수, 명세서 4절 방식)은 아직 배치에 연결되지 않은
     별도 과제라, 이번엔 "노선의 물리적 순서상 종점으로부터 몇 번째 역인가"로
     근사한다 — 상세 근거는 아래 STOP_SEQUENCE 설명 및 방법론 md 참고.
  5) boarding_est/alighting_est 반영(2026-08-21, backend.md §7.2.1) — 원본 CSV의
     '승차_추정'/'하차_추정' 컬럼을 그대로 옮겨 담는다(변환 불필요). Q3가 순증감
     보정으로 재개정되면서 scoring.py가 이 두 컬럼이 둘 다 있을 때 stop_sequence
     감산 대신 우선 적용한다 — 비어 있으면 None으로 넣어 기존 폴백이 그대로
     동작한다.

⚠️ stop_sequence는 근사치다. 열차가 항상 종점부터 종점까지 완주한다고 가정하는데,
실제로는 단축운행(중간 기점 출발) 열차가 있어 진짜 "출고 이후 정차 횟수"보다 작게
나오는 경우가 있을 수 있다. Q3 감산 공식(K=8, 8개역 지나면 보너스 소멸)의 영향
범위가 좁아서 실사용에 큰 무리는 없다고 판단했지만, 정밀도가 중요해지면 명세서
4절의 실측 방식(열차운행시각표 기반)으로 교체할 것.

사용법 (배치 러너에서, station_sync 이후에 실행 — station_id FK 필요):
    from app.batch.station_weight_sync import sync_station_weight
    n = sync_station_weight(cur, batch_id)
"""
import csv
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "텅텅_지하철방향별재차인원추정-2026_08_20수정3.csv"

# ============================================================
# 요일유형 -> dow(0=월..6=일). '평일' 값은 월~금 5일에 동일하게 적용한다
# (원본 데이터 자체가 평일 하나로만 집계돼 있어 요일별 세분화된 값이 없다).
# ============================================================
_DOW_MAP = {"평일": [0, 1, 2, 3, 4], "토요일": [5], "일요일": [6]}

# ============================================================
# 시간대 -> time_slot 표준 포맷. 18개 정규 시간대는 그대로 'HH:00-HH:00'으로
# 바꾸고, 앞뒤 경계 2개는 실제 운행시간 특성을 반영해 매핑한다(단순히
# '06시이전'을 '00:00-06:00'으로 뭉치면 첫차/막차라는 서로 다른 성격의
# 두 구간을 하나로 오인하게 된다):
#   - '06시이전' -> '05:00-06:00' (첫차 시간대, 06시 되기 직전)
#   - '24시이후' -> '00:00-01:00' (막차 시간대, 자정 막 지난 시각)
#   즉 01:00~05:00는 실제 운행이 없는 시간대라 원본에도 버킷이 없다.
#   (정확한 첫차/막차 분 단위 경계는 원본에 없어 근사치임)
# ============================================================
_TIME_SLOT_MAP = {"06시이전": "05:00-06:00", "24시이후": "00:00-01:00"}
for h in range(6, 24):
    _TIME_SLOT_MAP[f"{h:02d}-{h+1:02d}시간대"] = f"{h:02d}:00-{h+1:02d}:00"

# ============================================================
# stop_sequence 계산용 노선별 물리적 순서.
#
# 원칙: station.station_no 오름차순 = 물리적 순서(반경형 노선 공통 규칙, 01_schema.sql
# station 테이블 주석 참고). 예외 2건은 실측 좌표(haversine 검증)로 확인된 "역번호
# 순서 ≠ 물리적 위치" 사례라 하드코딩한다:
#   - 1호선 동묘앞(159): 실제로는 동대문(155)-신설동(156) 사이에 위치.
#   - 8호선 남위례(2828): 실제로는 복정(2821)-산성(2822) 사이에 위치.
# (근거: 텅텅_지하철역좌표_OSM매칭_방법론및한계-2026_08_20수정.md)
#
# 2호선은 순환선이라 "종점(출고역)" 개념 자체가 없어 stop_sequence를 계산하지
# 않는다(전부 NULL — 방향은 통계적 추정 대상이라는 기존 02_seed.sql 방침과 동일).
#
# 5호선은 강동에서 하남검단산/마천 두 방향으로 갈라지는 Y자형 노선이다. 트렁크
# (방화~강동)는 두 지선이 공유한다.
# ============================================================
_PHYS_ORDER_1 = ["150", "151", "152", "153", "154", "155", "159", "156", "157", "158"]
_PHYS_ORDER_8 = [
    "2810", "2811", "2812", "2813", "2814", "2815", "2816", "2817", "2818",
    "2819", "2820", "2821", "2828", "2822", "2823", "2824", "2825", "2826", "2827",
]
_TRUNK_5 = [str(n) for n in range(2511, 2550)]  # 방화(2511)~강동(2549), 39개
_BRANCH_5_HANAM = ["2550", "2551", "2552", "2553", "2554", "2562", "2563", "2564", "2565", "2566"]  # 강동~하남검단산, 10개
_BRANCH_5_MACHEON = ["2555", "2556", "2557", "2558", "2559", "2560", "2561"]  # 강동~마천, 7개


def _build_simple_orders(rows: list[dict]) -> dict:
    """예외가 없는 노선(3,4,6,7호선)은 역번호 오름차순 = 물리적 순서로 그대로 쓴다."""
    orders = {}
    for line in ("3호선", "4호선", "6호선", "7호선"):
        nos = sorted({r["역번호"] for r in rows if r["호선"] == line}, key=lambda s: int(s))
        orders[line] = nos
    return orders


def _stop_sequence(line: str, direction: str, station_no: str, simple_orders: dict):
    if line == "2호선":
        return None

    if line == "1호선":
        order = _PHYS_ORDER_1
    elif line == "8호선":
        order = _PHYS_ORDER_8
    elif line in simple_orders:
        order = simple_orders[line]
    elif line == "5호선":
        if station_no in _BRANCH_5_HANAM:
            if direction == "하선":
                return 39 + _BRANCH_5_HANAM.index(station_no)
            full = list(reversed(_BRANCH_5_HANAM)) + list(reversed(_TRUNK_5))
            return full.index(station_no)
        if station_no in _BRANCH_5_MACHEON:
            if direction == "하선":
                return 39 + _BRANCH_5_MACHEON.index(station_no)
            full = list(reversed(_BRANCH_5_MACHEON)) + list(reversed(_TRUNK_5))
            return full.index(station_no)
        if station_no in _TRUNK_5:
            idx = _TRUNK_5.index(station_no)
            if direction == "하선":
                return idx
            # 상선 트렁크 구간: 어느 지선에서 왔는지 알 수 없어(트렁크 값은 두 지선
            # 공통) 더 짧은 마천지선(7개)을 기준으로 보수적으로 추정한다. 실제
            # 하남검단산발 열차라면 진짜 정차순번은 이보다 3 더 크지만, K=8 감산
            # 구간을 벗어나는 지점에서는 어차피 감산이 0이라 영향이 없다.
            return len(_BRANCH_5_MACHEON) + (len(_TRUNK_5) - 1 - idx)
        return None
    else:
        return None

    idx = order.index(station_no)
    return idx if direction == "하선" else len(order) - 1 - idx


def _load_rows() -> list[dict]:
    with open(_DATA, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sync_station_weight(cur, batch_id: int) -> int:
    """station_weight에 이번 batch_id로 행을 삽입한다. 삽입된 행 수를 반환한다.

    station 테이블이 먼저 채워져 있어야 한다(station_sync.sync_station_master를
    이 함수보다 먼저 호출할 것) — station_id FK 조회가 실패하면 해당 원본 행은
    건너뛰고 개수를 세어 로그로 남긴다(조용히 누락시키지 않는다).
    """
    cur.execute("SELECT station_id, line_name, station_no FROM station")
    station_lookup = {(r["line_name"], r["station_no"]): r["station_id"] for r in cur.fetchall()}

    raw_rows = _load_rows()
    simple_orders = _build_simple_orders(raw_rows)

    insert_rows = []
    skipped_no_station = 0
    for r in raw_rows:
        line, station_no, direction = r["호선"], r["역번호"], r["상하구분"]
        station_id = station_lookup.get((line, station_no))
        if station_id is None:
            skipped_no_station += 1
            continue

        time_slot = _TIME_SLOT_MAP[r["시간대"]]
        stop_sequence = _stop_sequence(line, direction, station_no, simple_orders)
        net_onboard = float(r["재차인원_추정"]) if r["재차인원_추정"] else None
        congestion_pct = float(r["혼잡도"]) if r["혼잡도"] else None
        boarding_est = float(r["승차_추정"]) if r["승차_추정"] else None
        alighting_est = float(r["하차_추정"]) if r["하차_추정"] else None

        for dow in _DOW_MAP[r["요일유형"]]:
            insert_rows.append(
                {
                    "station_id": station_id,
                    "batch_id": batch_id,
                    "direction": direction,
                    "time_slot": time_slot,
                    "dow": dow,
                    "net_onboard": net_onboard,
                    "congestion_pct": congestion_pct,
                    "stop_sequence": stop_sequence,
                    "boarding_est": boarding_est,
                    "alighting_est": alighting_est,
                }
            )

    if skipped_no_station:
        print(f"[station_weight_sync] 경고: station 테이블에 없어 건너뛴 원본 행 {skipped_no_station}건")

    _UPSERT_SQL = """
        INSERT INTO station_weight
            (station_id, batch_id, direction, time_slot, dow, net_onboard, congestion_pct,
             stop_sequence, boarding_est, alighting_est)
        VALUES
            (%(station_id)s, %(batch_id)s, %(direction)s, %(time_slot)s, %(dow)s,
             %(net_onboard)s, %(congestion_pct)s, %(stop_sequence)s, %(boarding_est)s, %(alighting_est)s)
        ON CONFLICT (station_id, batch_id, time_slot, dow, direction)
        DO UPDATE SET net_onboard = EXCLUDED.net_onboard,
                      congestion_pct = EXCLUDED.congestion_pct,
                      stop_sequence = EXCLUDED.stop_sequence,
                      boarding_est = EXCLUDED.boarding_est,
                      alighting_est = EXCLUDED.alighting_est
    """
    cur.executemany(_UPSERT_SQL, insert_rows)
    return len(insert_rows)
