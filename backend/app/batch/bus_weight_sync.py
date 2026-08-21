"""버스 정류장×노선별 가중치(bus_weight) 동기화.

입력: backend/app/batch/data/텅텅_버스구간별재차인원추정-2026_08_20생성.csv
  (노선번호/정류장ID/정류소명/순번 + 승차_00시~23시/하차_00시~23시/재차인원_00시~23시,
  38,599개 노선×정류장 조합). 방법론: 텅텅_버스구간별재차인원추정_방법론및한계-
  2026_08_20생성.md. bus_weight의 Q1 스코어링은 net_onboard(재차인원)만 쓴다 —
  %혼잡도(텅텅_버스구간별혼잡도추정-2026_08_20수정.csv)는 Q1 공식이 쓰지 않는
  보조 지표라 이 배치 대상이 아니다(CLAUDE.md 확정 스코어링: bus_score =
  min(net_onboard/50, 1.0), %혼잡도가 아니라 재차인원 그대로 사용). 승차/하차
  추정치는 Q1이 아니라 Q3 순증감 보정(backend.md §7.2.1)에 쓰인다 — 아래 4) 참고.

이 모듈이 원본 CSV로부터 직접 계산/변환하는 것 4가지:
  1) stop_id 조회 — bus_stop 테이블을 stop_std_id(=정류장ID)로 미리 로드해 매핑.
  2) 시간대(00시~23시 컬럼) → time_slot(예: '08:00-09:00') 와이드→롱 변환.
     station_weight와 동일한 'HH:00-(HH+1):00' 포맷을 써서, 나중에 지하철/버스
     조회 로직이 같은 방식으로 현재 시각→time_slot 문자열을 만들 수 있게 한다.
  3) stop_sequence — 원본 CSV의 '순번' 컬럼을 그대로 쓴다. 지하철과 달리 이건
     근사치가 아니라 실측값이다(서울시버스노선별정류소정보의 노선 내 정차순번을
     그대로 이어받은 것 — 기점부터 몇 번째 정류장인지가 정확히 나온다).
  4) boarding_est/alighting_est(2026-08-21, backend.md §7.2.1) — 원본의
     '승차_HH시'/'하차_HH시' 컬럼도 재차인원과 동일한 방식으로 와이드→롱 변환한다.
     Q3가 순증감 보정으로 재개정되면서 scoring.py가 이 두 값이 둘 다 있을 때
     stop_sequence 감산 대신 우선 적용한다.

⚠️ 순환버스 중복 정류장 처리 — 로컬 검증 중 발견한 문제. 일부 노선(예: 0017,
01A, 01B 등 순환/셔틀형 노선)은 같은 정류장을 한 바퀴 안에 두 번 이상 지난다
(순번이 다른 여러 행으로 원본에 이미 존재 — 예: 0017번의 "신용산지하차도"는
순번 2와 21에 각각 등장하고, 재차인원 값도 서로 다르다: 08시 기준 0명 vs 57명).
그런데 bus_weight의 UNIQUE 제약(stop_id, route_id, batch_id, time_slot, dow)엔
순번이 없어서 같은 정류장을 두 번 지나는 걸 구분해 저장할 방법이 없다(스키마가
애초에 "노선 하나가 정류장 하나를 한 번만 지난다"고 가정하고 있음). 실제 노선×
정류장 조합 38,599건 중 1,095건(2.8%)이 이렇게 중복된다.
해결: 이런 중복은 net_onboard=최댓값, stop_sequence=최댓값으로 병합한다(둘 다
"더 혼잡했다고, 더 출고에서 멀다고 보수적으로 가정"하는 방향 — 혼잡 회피가
목적인 서비스에서 실제보다 덜 혼잡하다고 알려주는 쪽보다는 안전하다). 순환
노선의 두 번째 통과가 첫 번째보다 보통 더 혼잡한 경향(위 예시가 그렇듯)과도
방향이 맞는다. boarding_est/alighting_est도 같은 이유로 최댓값 병합한다 —
이 값들도 결국 net_onboard와 같은 "더 혼잡한 쪽으로 보수적으로 가정" 정책을
따라야 정합성이 깨지지 않는다.

⚠️ dow(요일) 정책 — 원본 재차인원 자체가 "2026년 6월 한 달 합계 ÷ 30"으로 만든
평일/주말 구분 없는 근사치다(방법론 md 4절 한계). 이 배치는 그 근사치를 **평일만**
(dow=0~4, 월~금)에 동일하게 채우고, 토요일(5)·일요일(6)은 **아예 행을 넣지 않는다**.
주말 값을 평일과 똑같이 채우면 "주말 데이터도 있다"는 착각을 주지만, 실제로는
평일/주말을 구분할 수 없는 게 사실이라 없는 채로 두는 쪽이 더 정직하다고 판단했다
(station_weight는 반대로 평일/토요일/일요일 값이 원본에 실제로 따로 있어 그대로
셋 다 넣는다 — 이 차이는 데이터 유무 차이일 뿐 정책 비일관이 아니다). 나중에 요일별
버스 승하차 데이터를 구하면 이 정책부터 다시 검토할 것.

성능: 38,599(정류장) × 24(시간대) × 5(평일 dow) ≈ 463만 행이 된다. 이 정도 규모를
psycopg의 executemany(행 단위 파라미터 바인딩)로 넣으면 왕복 오버헤드 때문에
현실적인 시간 안에 끝나지 않는다(로컬 테스트에서 2분 넘게 걸려도 안 끝남). COPY로
임시 테이블에 통째로 적재하는 것까지는 빨랐다(8~10초). 그런데 그 다음
INSERT...SELECT...GROUP BY 단계가 여전히 느렸다(2분 넘게 안 끝남) — 원인을
추적해보니 bus_weight의 외래키(stop_id→bus_stop, batch_id→batch_run) 검증이
456만 건 각각에 대해 개별적으로 실행되는 게 병목이었다(로컬 2코어 환경 기준
실측: FK 검증 있으면 2분+, 없으면 68초). 이 배치가 넣는 stop_id는 바로 위에서
bus_stop을 조회해 얻은 값이고 batch_id는 이 함수 호출 직전에 만든 batch_run
행이라 **둘 다 이미 유효함이 보장**돼 있으므로, 병합하는 동안만 안전하게
트리거를 꺼서(ALTER TABLE ... DISABLE/ENABLE TRIGGER ALL) 중복 검증을 생략한다
— try/finally로 감싸 어떤 경우에도(에러가 나도) 트리거가 다시 켜지는 걸 보장한다.

사용법 (배치 러너에서, bus_stop_sync 이후에 실행 — stop_id FK 필요):
    from app.batch.bus_weight_sync import sync_bus_weight
    n = sync_bus_weight(cur, batch_id)
"""
import csv
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "텅텅_버스구간별재차인원추정-2026_08_20생성.csv"

_WEEKDAY_DOWS = [0, 1, 2, 3, 4]  # 월~금만. 토/일은 넣지 않음(위 docstring 참고).

_CREATE_TEMP_SQL = """
    CREATE TEMP TABLE _bus_weight_staging (
        stop_id INT, route_id VARCHAR(20), batch_id INT,
        time_slot VARCHAR(20), dow SMALLINT,
        net_onboard NUMERIC(10,2), stop_sequence SMALLINT,
        boarding_est NUMERIC(10,2), alighting_est NUMERIC(10,2)
    ) ON COMMIT DROP
"""

_MERGE_SQL = """
    INSERT INTO bus_weight (stop_id, route_id, batch_id, time_slot, dow, net_onboard, stop_sequence,
                             boarding_est, alighting_est)
    SELECT stop_id, route_id, batch_id, time_slot, dow,
           MAX(net_onboard) AS net_onboard, MAX(stop_sequence) AS stop_sequence,
           MAX(boarding_est) AS boarding_est, MAX(alighting_est) AS alighting_est
    FROM _bus_weight_staging
    GROUP BY stop_id, route_id, batch_id, time_slot, dow
    ON CONFLICT (stop_id, route_id, batch_id, time_slot, dow)
    DO UPDATE SET net_onboard = EXCLUDED.net_onboard, stop_sequence = EXCLUDED.stop_sequence,
                  boarding_est = EXCLUDED.boarding_est, alighting_est = EXCLUDED.alighting_est
"""


def _load_rows() -> list[dict]:
    with open(_DATA, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _iter_staging_tuples(raw_rows: list[dict], stop_lookup: dict, batch_id: int):
    for r in raw_rows:
        stop_id = stop_lookup.get(r["정류장ID"])
        if stop_id is None:
            continue

        route_id = r["노선번호"]
        stop_sequence = int(r["순번"]) if r["순번"] else None

        for h in range(24):
            net_onboard_raw = r.get(f"재차인원_{h:02d}시")
            net_onboard = float(net_onboard_raw) if net_onboard_raw not in (None, "") else None
            boarding_raw = r.get(f"승차_{h:02d}시")
            boarding_est = float(boarding_raw) if boarding_raw not in (None, "") else None
            alighting_raw = r.get(f"하차_{h:02d}시")
            alighting_est = float(alighting_raw) if alighting_raw not in (None, "") else None
            time_slot = f"{h:02d}:00-{h + 1:02d}:00"

            for dow in _WEEKDAY_DOWS:
                yield (
                    stop_id, route_id, batch_id, time_slot, dow,
                    net_onboard, stop_sequence, boarding_est, alighting_est,
                )


def sync_bus_weight(cur, batch_id: int) -> int:
    """bus_weight에 이번 batch_id로 행을 삽입한다(평일 dow=0~4만). 삽입된 행 수를 반환한다.

    bus_stop 테이블이 먼저 채워져 있어야 한다(bus_stop_sync.sync_bus_stop_master를
    이 함수보다 먼저 호출할 것) — stop_id FK 조회가 실패하면 해당 원본 행은
    건너뛰고 개수를 세어 로그로 남긴다.
    """
    cur.execute("SELECT stop_id, stop_std_id FROM bus_stop")
    stop_lookup = {r["stop_std_id"]: r["stop_id"] for r in cur.fetchall()}

    raw_rows = _load_rows()
    skipped_no_stop = sum(1 for r in raw_rows if stop_lookup.get(r["정류장ID"]) is None)
    if skipped_no_stop:
        print(f"[bus_weight_sync] 경고: bus_stop 테이블에 없어 건너뛴 원본 행 {skipped_no_stop}건")

    cur.execute(_CREATE_TEMP_SQL)
    with cur.copy("COPY _bus_weight_staging FROM STDIN") as copy:
        for row in _iter_staging_tuples(raw_rows, stop_lookup, batch_id):
            copy.write_row(row)

    # 대량 병합 동안만 FK 검증을 꺼서 성능을 확보한다(위 docstring 참고) —
    # stop_id/batch_id 둘 다 이 함수 안에서 이미 유효성이 보장된 값이라 안전하다.
    # 원래 ALTER TABLE ... DISABLE TRIGGER ALL 로 구현했었으나, 이게 끄는 트리거에는
    # FK RI 시스템 트리거도 포함돼서 "permission denied: ... is a system trigger" 로
    # 실패한다(테이블 소유자라도 superuser가 아니면 시스템 트리거는 못 끔 — 로컬
    # 테스트뿐 아니라 운영에서도 superuser 계정을 쓰지 않는 한 항상 이렇게 실패했을
    # 것). 대신 FK 제약을 DROP했다가 병합 후 다시 ADD하는 방식으로 대체한다 — 이건
    # 테이블 소유자 권한만으로 가능하고, 재추가 시 한 번의 검증 스캔만 도는 것도
    # 트리거를 켠 채 456만 건을 개별 검증하는 것보다 여전히 훨씬 빠르다.
    # work_mem도 이 트랜잭션 안에서만 늘린다(GROUP BY 456만 행을 기본 4MB로 하면
    # 해시 집계가 디스크로 스필되어 느려진다 — SET LOCAL이라 트랜잭션 끝나면 자동 원복).
    cur.execute("SET LOCAL work_mem = '256MB'")
    cur.execute("ALTER TABLE bus_weight DROP CONSTRAINT bus_weight_stop_id_fkey")
    cur.execute("ALTER TABLE bus_weight DROP CONSTRAINT bus_weight_batch_id_fkey")
    try:
        cur.execute(_MERGE_SQL)
        n = cur.rowcount
    finally:
        cur.execute(
            "ALTER TABLE bus_weight ADD CONSTRAINT bus_weight_stop_id_fkey "
            "FOREIGN KEY (stop_id) REFERENCES bus_stop(stop_id)"
        )
        cur.execute(
            "ALTER TABLE bus_weight ADD CONSTRAINT bus_weight_batch_id_fkey "
            "FOREIGN KEY (batch_id) REFERENCES batch_run(batch_id)"
        )
    return n
