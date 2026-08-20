from datetime import datetime

from pydantic import BaseModel


class SystemMeta(BaseModel):
    front_version: str
    server_version: str
    server_name: str
    server_ip: str
    client_ip: str
    x_forwarded_for: str | None = None


class LatestBatch(BaseModel):
    run_month: str
    status: str
    finished_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    latest_batch: LatestBatch | None = None
