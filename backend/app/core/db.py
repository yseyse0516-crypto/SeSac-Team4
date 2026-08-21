import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_CONNINFO = (
    f"host={os.getenv('DB_HOST', 'localhost')} "
    f"port={os.getenv('DB_PORT', '5432')} "
    f"dbname={os.getenv('DB_NAME', 'bium')} "
    f"user={os.getenv('DB_USER', 'bium')} "
    f"password={os.getenv('DB_PASSWORD', 'bium')}"
)

pool = ConnectionPool(conninfo=_CONNINFO, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False)


@contextmanager
def get_cursor(timeout: float | None = None):
    with pool.connection(timeout=timeout) as conn:
        with conn.cursor() as cur:
            yield cur


def ping() -> bool:
    with get_cursor(timeout=3) as cur:
        cur.execute("SELECT 1")
        return cur.fetchone() is not None
