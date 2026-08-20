"""_interpret_response()는 2026-08-19 실제 ODsay 키로 라이브 호출해서 확인한
세 가지 응답 형태(오류/후보없음/정상)를 그대로 재현한 테스트다.

2026-08-19 밤 추가: 실제로 40회 연속 호출해서 확인한 "일일 한도 30건"(문서화된
1,000건과 다름) 대응으로 추가한 캐싱/회로차단기 테스트. httpx.get을 모킹해서
실제 네트워크 호출 없이 캐싱/쿼터 로직만 검증한다.
"""
import time

import pytest

from app.services import odsay_client
from app.services.odsay_client import (
    OdsayError,
    OdsayNoCandidateError,
    OdsayQuotaExceededError,
    _interpret_response,
    call_odsay,
)


@pytest.fixture(autouse=True)
def _reset_odsay_state():
    odsay_client._response_cache.clear()
    odsay_client._quota_exhausted_at = None
    yield
    odsay_client._response_cache.clear()
    odsay_client._quota_exhausted_at = None


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


def _fake_httpx_get(calls, status_code=200, json_data=None):
    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return _FakeResponse(status_code, json_data)

    return fake_get


# --- 기존 _interpret_response 형태 테스트 ---


def test_auth_error_response_raises_odsay_error_not_no_candidate():
    # 2026-08-19 라이브 호출로 실제 확인된 형태 (IP 미등록 시 이 오류가 옴)
    live_error_response = {"error": [{"code": "500", "message": "[ApiKeyAuthFailed] ApiKey authentication failed."}]}
    with pytest.raises(OdsayError):
        _interpret_response(live_error_response)


def test_empty_path_list_raises_no_candidate():
    response = {"result": {"searchType": 0, "path": []}}
    with pytest.raises(OdsayNoCandidateError):
        _interpret_response(response)


def test_missing_result_key_raises_odsay_error():
    with pytest.raises(OdsayError):
        _interpret_response({"unexpected": "shape"})


def test_normal_response_with_paths_passes_through():
    response = {"result": {"searchType": 0, "path": [{"pathType": 1}]}}
    assert _interpret_response(response) is response


# --- 쿼터 소진 감지 (2026-08-19 밤, 실측 근거) ---


def test_quota_exceeded_response_raises_specific_exception():
    # 2026-08-19 밤 실제로 40회 연속 호출해서 30번째에 받은 것과 동일한 형태
    quota_response = {"error": [{"code": "429", "message": "Daily quota exceeded"}]}
    with pytest.raises(OdsayQuotaExceededError):
        _interpret_response(quota_response)


def test_quota_exceeded_error_is_odsay_error_subclass():
    # 라우터가 기존 OdsayError 처리 경로로도 잡을 수 있어야 함(하위 호환)
    assert issubclass(OdsayQuotaExceededError, OdsayError)


def test_auth_error_is_not_misclassified_as_quota_exceeded():
    # code="500"(인증 실패)은 quota 오류가 아니므로 일반 OdsayError여야 함
    auth_error = {"error": [{"code": "500", "message": "[ApiKeyAuthFailed] ApiKey authentication failed."}]}
    with pytest.raises(OdsayError) as exc_info:
        _interpret_response(auth_error)
    assert not isinstance(exc_info.value, OdsayQuotaExceededError)


# --- 응답 캐싱 ---


def test_call_odsay_caches_identical_coordinates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        odsay_client.httpx, "get", _fake_httpx_get(calls, 200, {"result": {"path": [{"pathType": 1}]}})
    )

    r1 = call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")
    r2 = call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")

    assert r1 == r2
    assert len(calls) == 1, "같은 좌표 재요청은 캐시에서 반환돼야 하고 실제 호출은 1번만"


def test_call_odsay_cache_miss_for_different_coordinates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        odsay_client.httpx, "get", _fake_httpx_get(calls, 200, {"result": {"path": [{"pathType": 1}]}})
    )

    call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")
    call_odsay(37.9, 127.0, 37.6, 127.1, api_key="k")

    assert len(calls) == 2


def test_call_odsay_cache_expires_after_ttl(monkeypatch):
    calls = []
    monkeypatch.setattr(
        odsay_client.httpx, "get", _fake_httpx_get(calls, 200, {"result": {"path": [{"pathType": 1}]}})
    )
    monkeypatch.setattr(odsay_client, "CACHE_TTL_SECONDS", -1)  # 즉시 만료

    call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")
    call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")

    assert len(calls) == 2, "TTL이 지나면 캐시를 안 쓰고 다시 호출해야 함"


# --- 쿼터 소진 회로차단기 ---


def test_quota_exceeded_triggers_cooldown_for_any_coordinates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        odsay_client.httpx,
        "get",
        _fake_httpx_get(calls, 200, {"error": [{"code": "429", "message": "Daily quota exceeded"}]}),
    )

    with pytest.raises(OdsayQuotaExceededError):
        call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")
    assert len(calls) == 1

    # 쿨다운 중엔 완전히 다른 좌표라도 실제 호출 없이 즉시 차단돼야 함
    with pytest.raises(OdsayQuotaExceededError):
        call_odsay(10.0, 10.0, 20.0, 20.0, api_key="k")
    assert len(calls) == 1, "쿨다운 중엔 새 좌표라도 실제 호출을 하면 안 됨"


def test_cooldown_expires_after_window(monkeypatch):
    monkeypatch.setattr(odsay_client, "QUOTA_COOLDOWN_SECONDS", -1)  # 즉시 만료
    odsay_client._quota_exhausted_at = time.monotonic()

    calls = []
    monkeypatch.setattr(
        odsay_client.httpx, "get", _fake_httpx_get(calls, 200, {"result": {"path": [{"pathType": 1}]}})
    )

    call_odsay(37.5, 127.0, 37.6, 127.1, api_key="k")
    assert len(calls) == 1, "쿨다운이 지났으면 다시 정상 호출돼야 함"
