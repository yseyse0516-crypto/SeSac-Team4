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
            # 2026-08-20 실제 통합 테스트로 발견: 기본값(RESP3 협상을 위해 HELLO를
            # 먼저 보냄)이 docker-compose의 redis:7과 연결 시
            # "unknown command 'HELLO'"로 실패했다. protocol=2(RESP2)로 고정하면
            # 정상 연결됨 — redis-py/서버 버전 조합에 따른 RESP3 협상 이슈로 보임.
            protocol=2,
        )
    return _client


def ping() -> bool:
    return bool(get_client().ping())
