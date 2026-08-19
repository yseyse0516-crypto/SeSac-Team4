"""_interpret_response()는 2026-08-19 실제 ODsay 키로 라이브 호출해서 확인한
세 가지 응답 형태(오류/후보없음/정상)를 그대로 재현한 테스트다."""
import pytest

from app.services.odsay_client import OdsayError, OdsayNoCandidateError, _interpret_response


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
