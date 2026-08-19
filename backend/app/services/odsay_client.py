"""ODsay LAB 멀티모달 경로탐색 API 연동.

요청 1건당 정확히 1회만 호출한다 (CLAUDE.md §3, N-03). 재요청 캐시는 Redis가 준비되면
search.py 쪽에서 이 함수를 감싸서 처리한다 (core/redis.py는 B 담당, 2026-08-20 오전 통합 예정).

ODSAY_API_KEY가 없으면 샘플 응답(fixture)을 반환한다 — 실제 키가 없는 상태에서도
파싱/매칭/스코어링 로직을 개발·테스트할 수 있게 하기 위함.

⚠️ 아래 실제 호출 부분(파라미터명 SX/SY/EX/EY/OPT)은 ODsay Lab 공개 문서 기준 추정치다.
실제 키를 받으면 반드시 응답을 확인해서 파라미터명·필드명이 맞는지 검증해야 한다
(backend.md §9 "오늘 A 작업" 참고).
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

    data = response.json()
    if "result" not in data:
        # ODsay는 에러도 200으로 내려주고 본문에 error 필드를 담는 경우가 있음 — 실제 키로 확인 필요
        raise OdsayNoCandidateError(f"ODsay 응답에 result 없음: {data}")

    return data


def _load_fixture() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)
