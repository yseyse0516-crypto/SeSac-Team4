import os

import redis

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
            protocol=2,  # RESP3 HELLO 협상을 시도하다 실패하는 환경이 있어 RESP2로 고정
        )
    return _client


def ping() -> bool:
    return bool(get_client().ping())
