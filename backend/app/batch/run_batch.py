"""텅텅(TangTang) 월간 배치 진입점 (2026-08-20, 통합판).

기존 run_dock_batch.py는 대여소 동기화 하나만 처리했다("배치에 이 두 줄만
추가해달라"는 요청에 대응해 만든 최초 러너). 이번에 station/station_weight/
bus_stop/bus_weight까지 배치 범위가 넓어져서, batch_run 한 행에 이번 달 배치
전체(마스터 갱신 + 가중치 재계산)를 묶는 통합 러너로 확장했다. run_dock_batch.py는
그대로 남겨두되(대여소만 단독으로 재동기화하고 싶을 때 참고용), 정기 배치는
이 파일을 쓸 것을 권장한다.

처리 순서 (마스터 3개 먼저, 그다음 그 마스터들의 FK를 참조하는 파생 테이블 3개):
    1. station_sync.sync_station_master        — station 마스터 UPSERT
    2. bus_stop_sync.sync_bus_stop_master       — bus_stop 마스터 UPSERT
    3. dock_master_sync.sync_dock_master        — 따릉이 대여소 마스터 UPSERT(행안부 API)
    4. station_weight_sync.sync_station_weight  — 이번 batch_id로 지하철 가중치 INSERT
    5. bus_weight_sync.sync_bus_weight          — 이번 batch_id로 버스 가중치 INSERT
    6. dock_hub_distance_sync.sync_dock_hub_distance — 이번 batch_id로 대여소-거점 거리 INSERT
       (station/bus_stop/rental_dock 세 마스터 전부 끝난 뒤에만 실행 가능 — 순서 3개 다 필요)

각 단계는 독립적으로 실패할 수 있어 개별 try/except로 감싸고, 실패한 단계가
있어도 나머지는 계속 진행한다(예: 행안부 API가 일시적으로 안 되더라도 지하철/버스
가중치 갱신은 막지 않는다) — 대신 batch_run.note에 실패한 단계를 전부 기록하고,
하나라도 실패하면 최종 status는 'failed'로 남긴다(부분 성공을 'success'로
위장하지 않는다).

사용법: `python -m app.batch.run_batch`
"""
from dotenv import load_dotenv

# main.py의 lifespan(pool.open()/.close())과 .env 로딩을 거치지 않고 독립
# 프로세스로 실행되므로, 여기서 직접 .env를 읽고 커넥션 풀을 열고 닫아야 한다.
# (안 하면 psycopg_pool.PoolClosed: the pool is not open yet 로 즉시 실패한다.)
load_dotenv()

from app.batch.bus_stop_sync import sync_bus_stop_master
from app.batch.bus_weight_sync import sync_bus_weight
from app.batch.dock_hub_distance_sync import sync_dock_hub_distance
from app.batch.dock_master_sync import sync_dock_master
from app.batch.station_sync import sync_station_master
from app.batch.station_weight_sync import sync_station_weight
from app.core import db
from app.core.db import pool


def _current_run_month(cur) -> str:
    cur.execute("SELECT to_char(now(), 'YYYY-MM')")
    return cur.fetchone()["to_char"]


def run() -> None:
    with db.get_cursor() as cur:
        run_month = _current_run_month(cur)
        cur.execute(
            "INSERT INTO batch_run (run_month, status, started_at) VALUES (%s, 'running', now())",
            (run_month,),
        )
        # RETURNING은 CLAUDE.md §2가 피하라는 PG 전용 문법이라, 같은 커넥션/트랜잭션
        # 안에서 안전한 lastval()로 방금 넣은 batch_id를 가져온다(run_dock_batch.py와 동일 패턴).
        cur.execute("SELECT lastval() AS batch_id")
        batch_id = cur.fetchone()["batch_id"]
        cur.connection.commit()

        notes: list[str] = []
        failed = False

        steps = [
            ("station", lambda: sync_station_master(cur)),
            ("bus_stop", lambda: sync_bus_stop_master(cur)),
            ("rental_dock", lambda: sync_dock_master(cur)),
            ("station_weight", lambda: sync_station_weight(cur, batch_id)),
            ("bus_weight", lambda: sync_bus_weight(cur, batch_id)),
            ("dock_hub_distance", lambda: sync_dock_hub_distance(cur, batch_id)),
        ]

        for name, step in steps:
            try:
                n = step()
                cur.connection.commit()
                notes.append(f"{name}={n}건")
            except Exception as exc:
                cur.connection.rollback()
                notes.append(f"{name} 실패: {exc}")
                failed = True

        cur.execute(
            "UPDATE batch_run SET status = %s, finished_at = now(), note = %s WHERE batch_id = %s",
            ("failed" if failed else "success", " / ".join(notes)[:255], batch_id),
        )
        cur.connection.commit()

        if failed:
            raise RuntimeError(f"배치 일부 실패 (batch_id={batch_id}): {notes}")


if __name__ == "__main__":
    pool.open()
    try:
        run()
    finally:
        pool.close()
