"""테스트 전역 설정.

search.py가 실제 candidate_log.py(Redis 필요)를 쓰게 되면서, Redis를 직접 모킹하지 않던
기존 라우터 테스트들이 로컬/CI에 진짜 Redis가 없으면 깨진다. 모든 테스트에서 core.redis의
클라이언트를 fakeredis로 바꿔치기해서, 어떤 라우터가 Redis를 쓰든 실제 서버 없이 동작하게 한다.
"""
import fakeredis
import pytest

import app.core.redis as redis_module
from app.core.db import pool


@pytest.fixture(autouse=True)
def _fake_redis():
    original = redis_module._client
    redis_module._client = fakeredis.FakeRedis(decode_responses=True)
    yield
    redis_module._client = original


@pytest.fixture(scope="session", autouse=True)
def _db_pool():
    # 개별 테스트 파일이 라우터만 얹은 즉석 앱을 쓰다 보니 main.py의 lifespan(pool.open())을
    # 안 거친다 — 실제 DB를 쓰는 auth/board/favorites 테스트를 위해 세션 전체에서 한 번만 연다.
    pool.open()
    yield
    pool.close()
