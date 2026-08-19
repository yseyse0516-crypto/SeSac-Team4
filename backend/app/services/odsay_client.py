"""ODsay LAB 멀티모달 경로탐색 API 연동.

요청 1건당 정확히 1회만 호출한다 (CLAUDE.md §3, N-03). 재요청 캐시는 Redis가 준비되면
search.py 쪽에서 이 함수를 감싸서 처리한다 (core/redis.py는 B 담당, 2026-08-20 오전 통합 예정).

ODSAY_API_KEY가 없으면 샘플 응답(fixture)을 반환한다 — 실제 키가 없는 상태에서도
파싱/매칭/스코어링 로직을 개발·테스트할 수 있게 하기 위함.

파라미터명(SX/SY/EX/EY/OPT)과 응답 필드는 2026-08-19 실제 키로 라이브 호출해서 검증
완료 — odsay_parser.py가 기대하는 필드(trafficType/startX/startY/lane 등)와 정확히
일치함을 확인했다. 인증 실패(IP 미등록 등)는 `{"error": [...]}` 형태로 200과 함께
오는 것도 이때 확인함 — result가 아예 없는 정상 실패 응답이라 NO_CANDIDATE와 구분해서
처리해야 한다(_interpret_response 참고).
"""
import json
from pathlib import Path
from typing import Optional

import httpx

ODSAY_ENDPOINT = "https://api.odsay.com/v1/api/searchPubTransPathT"
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "odsay_sample_response.json"
)


class OdsayError(Exception):
    """ODsay 호출 실패 — 라우터에서 502 UPSTREAM_ERROR로 변환."""


class OdsayNoCandidateError(Exception):
    """ODsay가 경로 후보를 반환하지 못함 — 라우터에서 404 NO_CANDIDATE로 변환."""


def call_odsay(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: Optional[str] = None,
    timeout: float = 5.0,
) -> dict:
    """ODsay 멀티모달 경로탐색 API를 1회 호출한다.

    api_key가 없으면 로컬 샘플 응답(fixture)을 반환한다 (키 발급 전 개발용).
    """
    if not api_key:
        return _load_fixture()

    params = {
        "apiKey": api_key,
        "SX": origin_lng,
        "SY": origin_lat,
        "EX": dest_lng,
        "EY": dest_lat,
        "OPT": 0,
    }
    try:
        response = httpx.get(ODSAY_ENDPOINT, params=params, timeout=timeout)
    except httpx.RequestError as exc:
        raise OdsayError(f"ODsay 요청 실패: {exc}") from exc

    if response.status_code != 200:
        raise OdsayError(f"ODsay 응답 오류: HTTP {response.status_code}")

    return _interpret_response(response.json())


def _interpret_response(data: dict) -> dict:
    """ODsay가 실제로 내려주는 세 가지 응답 형태를 구분한다 (2026-08-19 라이브 확인).

    1) {"error": [{"code": ..., "message": ...}]} — 인증 실패 등 API 자체 오류 → 502
    2) {"result": {..., "path": []}} — 정상 응답이지만 경로 후보가 없음 → 404
    3) {"result": {..., "path": [...]}} — 정상 응답
    """
    if "error" in data:
        raise OdsayError(f"ODsay 오류 응답: {data['error']}")

    if "result" not in data:
        raise OdsayError(f"ODsay 응답 형식이 예상과 다름: {data}")

    if not data["result"].get("path"):
        raise OdsayNoCandidateError("ODsay가 경로 후보를 반환하지 않음")

    return data


def _load_fixture() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)
