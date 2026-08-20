"""테스트 전역 설정.

search.py가 실제 candidate_log.py(Redis 필요)를 쓰게 되면서, Redis를 직접 모킹하지 않던
기존 라우터 테스트들이 로컬/CI에 진짜 Redis가 없으면 깨진다. 모든 테스트에서 core.redis의
클라이언트를 fakeredis로 바꿔치기해서, 어떤 라우터가 Redis를 쓰든 실제 서버 없이 동작하게 한다.
"""
import fakeredis
import pytest

import app.core.redis as redis_module


@pytest.fixture(autouse=True)
def _fake_redis():
    original = redis_module._client
    redis_module._client = fakeredis.FakeRedis(decode_responses=True)
    yield
    redis_module._client = original
