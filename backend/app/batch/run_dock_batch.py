"""대여소 마스터 동기화 배치 진입점.

⚠️ backend/app/batch/ 디렉토리 자체가 아직 저장소에 없어서(두 리포 다 확인함),
"이 두 줄만 추가해달라"고 하신 기존 배치 러너를 찾을 수 없었다. 이 파일을 그
디렉토리의 최초 러너로 만들어 요청하신 두 줄(import + 호출)을 넣어뒀다. 이미
다른 곳에 배치 러너가 따로 있다면 그쪽에 이 두 줄만 옮겨 넣고 이 파일은 무시해도
된다.

batch_run 테이블(N-05, 데이터 최신성 모니터링)에 실행 기록을 남긴다 — GET
/api/v1/health가 latest_batch로 조회하는 바로 그 테이블이라, 대여소 동기화만
돌리더라도 batch_run에 기록을 남겨야 health 체크가 "최근 배치가 있다"고 정상
응답한다.

사용법: `python -m app.batch.run_dock_batch`
"""
from dotenv import load_dotenv

# main.py의 lifespan(pool.open()/.close())과 .env 로딩을 거치지 않고 독립
# 프로세스로 실행되므로, 여기서 직접 .env를 읽고 커넥션 풀을 열고 닫아야 한다.
# (안 하면 psycopg_pool.PoolClosed: the pool is not open yet 로 즉시 실패한다.)
load_dotenv()

from app.batch.dock_master_sync import sync_dock_master
from app.core import db
from app.core.db import pool


def _current_run_month(cur) -> str:
    cur.execute("SELECT to_char(now(), 'YYYY-MM')")
    return cur.fetchone()["to_char"]


def run() -> None:
    with db.get_cursor() as cur:
        run_month = _current_run_month(cur)
        cur.execute(
            "INSERT INTO batch_run (run_month, status, started_at) "
            "VALUES (%s, 'running', now())",
            (run_month,),
        )
        # RETURNING은 CLAUDE.md §2가 피하라는 PG 전용 문법이라, 방금 넣은 SERIAL
        # 값은 세션 내 시퀀스 조회로 가져온다(lastval — 같은 커넥션/트랜잭션 안에서만
        # 안전, 이 배치는 단일 커넥션으로 순차 실행되므로 안전함).
        cur.execute("SELECT lastval() AS batch_id")
        batch_id = cur.fetchone()["batch_id"]
        cur.connection.commit()

        try:
            # ↓↓↓ 배치에 추가해달라고 요청하신 두 줄 ↓↓↓
            n = sync_dock_master(cur)
            cur.connection.commit()
            # ↑↑↑ 여기까지 ↑↑↑

            cur.execute(
                "UPDATE batch_run SET status = %s, finished_at = now(), note = %s "
                "WHERE batch_id = %s",
                ("success", f"{n}건 동기화", batch_id),
            )
            cur.connection.commit()
        except Exception as exc:
            cur.connection.rollback()
            cur.execute(
                "UPDATE batch_run SET status = %s, finished_at = now(), note = %s "
                "WHERE batch_id = %s",
                ("failed", str(exc)[:255], batch_id),
            )
            cur.connection.commit()
            raise


if __name__ == "__main__":
    pool.open()
    try:
        run()
    finally:
        pool.close()
