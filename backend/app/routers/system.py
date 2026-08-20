import os
import socket

from fastapi import APIRouter, HTTPException, Request

from app.core import db
from app.core import redis as redis_core
from app.schemas.system import HealthResponse, LatestBatch, SystemMeta

router = APIRouter(tags=["system"])


def _latest_batch() -> LatestBatch | None:
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT run_month, status, finished_at FROM batch_run "
            "ORDER BY started_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    return LatestBatch(**row) if row else None


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _local_ip() -> str:
    """이 인스턴스 자신의 IP를 알아낸다 (실제로 패킷을 보내지 않는 UDP 소켓 트릭).

    ASG로 API 서버가 여러 대 뜰 수 있어서(같은 AMI/.env 공유), SERVER_IP를 고정
    문자열로 두면 전부 같은 값이 찍혀 '어느 인스턴스가 응답했는지' 확인이라는
    배너의 목적이 무의미해진다 — 환경변수 미설정 시엔 인스턴스 자신의 실제 IP로 대체한다.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@router.get("/system/meta", response_model=SystemMeta)
def get_system_meta(request: Request) -> SystemMeta:
    return SystemMeta(
        front_version=os.getenv("FRONT_VERSION", "0.0.0"),
        server_version=os.getenv("SERVER_VERSION", "0.0.0"),
        server_name=os.getenv("SERVER_NAME") or socket.gethostname(),
        server_ip=os.getenv("SERVER_IP") or _local_ip(),
        client_ip=_client_ip(request),
        x_forwarded_for=request.headers.get("x-forwarded-for"),
    )


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    try:
        db_ok = db.ping()
    except Exception:
        db_ok = False
    try:
        redis_ok = redis_core.ping()
    except Exception:
        redis_ok = False
    try:
        latest_batch = _latest_batch() if db_ok else None
    except Exception:
        latest_batch = None
    return HealthResponse(
        status="ok" if db_ok and redis_ok else "degraded",
        db="ok" if db_ok else "error",
        redis="ok" if redis_ok else "error",
        latest_batch=latest_batch,
    )


@router.get("/admin/batch/latest", response_model=LatestBatch)
def get_admin_batch_latest() -> LatestBatch:
    batch = _latest_batch()
    if batch is None:
        raise HTTPException(status_code=404, detail="NO_BATCH_RUN")
    return batch
