"""ODsay LAB 멀티모달 경로탐색 API 연동.

요청 1건당 정확히 1회만 호출한다 (CLAUDE.md §3, N-03).

ODSAY_API_KEY가 없으면 샘플 응답(fixture)을 반환한다 — 실제 키가 없는 상태에서도
파싱/매칭/스코어링 로직을 개발·테스트할 수 있게 하기 위함.

인증 실패(IP 미등록 등)는 `{"error": [...]}` 형태로 200과 함께 오는 정상 실패 응답이라,
result가 아예 없는 이 경우를 NO_CANDIDATE와 구분해서 처리해야 한다(_interpret_response 참고).

⚠️ 이 프로젝트 키의 일일 한도는 문서상 1,000건이 아니라 실제로는 **30건/일**이다
(라이브 확인, CLAUDE.md §3 실측값으로 정정). 그래서 응답 캐싱 + 쿼터 소진 회로차단기를 둔다:

- **결과 캐싱**: 동일 (출발, 도착) 좌표로 재요청하면 실제 API를 다시 안 부르고 캐시된
  결과를 그대로 반환한다. TTL 기본 30분. call_odsay()는 departure_time을 애초에 ODsay에
  전달하지 않으므로(파라미터 자체가 없음) 캐시 키도 좌표 4개만 쓴다 — 나중에 시간대별로
  실제 조회하게 바뀌면 캐시 키에 departure_time도 포함시켜야 한다.
- **회로차단기**: ODsay가 쿼터 소진 오류(코드 429 또는 메시지에 "quota" 포함)를 한 번이라도
  반환하면, 그 시점부터 일정 시간(기본 1시간) 동안은 좌표 조합이 달라도 실제 호출 자체를
  생략하고 바로 OdsayQuotaExceededError를 던진다 — 이미 소진된 걸 알면서 새로운 좌표
  조합마다 계속 두들기는 걸 막기 위함.

둘 다 프로세스 메모리 기반이라 인스턴스를 여러 개 띄우면 인스턴스마다 따로 논다 —
다중 인스턴스 배포 시 Redis 공유 저장소로 옮겨야 한다(현재는 단일 인스턴스 배포 전제).
"""
import json
import time
from pathlib import Path
from typing import Optional

import httpx

ODSAY_ENDPOINT = "https://api.odsay.com/v1/api/searchPubTransPathT"
_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "odsay_sample_response.json"

CACHE_TTL_SECONDS = 1800  # 30분 — 자리표시자, Redis 붙으면 TTL 캐시로 교체
QUOTA_COOLDOWN_SECONDS = 3600  # 1시간 — 쿼터 소진 감지 후 신규 호출 자체를 생략하는 기간


class OdsayError(Exception):
    """ODsay 호출 실패 — 라우터에서 502 UPSTREAM_ERROR로 변환."""


class OdsayQuotaExceededError(OdsayError):
    """ODsay 일일 쿼터 소진 — 라우터에서 503 UPSTREAM_QUOTA_EXCEEDED로 변환."""


class OdsayNoCandidateError(Exception):
    """ODsay가 경로 후보를 반환하지 못함 — 라우터에서 404 NO_CANDIDATE로 변환."""


# (origin_lat, origin_lng, dest_lat, dest_lng) -> (만료시각(monotonic), 응답 dict)
_response_cache: dict[tuple, tuple] = {}
# 쿼터 소진이 감지된 시각(monotonic) — None이면 아직 정상
_quota_exhausted_at: Optional[float] = None


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

    cache_key = (origin_lat, origin_lng, dest_lat, dest_lng)
    cached = _response_cache.get(cache_key)
    if cached is not None:
        expires_at, result = cached
        if time.monotonic() < expires_at:
            return result
        del _response_cache[cache_key]

    if _quota_cooldown_active():
        raise OdsayQuotaExceededError(
            "최근 ODsay 쿼터 소진이 감지되어 이번 호출은 생략함(쿨다운 중)"
        )

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

    try:
        result = _interpret_response(response.json())
    except OdsayQuotaExceededError:
        _mark_quota_exhausted()
        raise

    _response_cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, result)
    return result


def _quota_cooldown_active() -> bool:
    if _quota_exhausted_at is None:
        return False
    return (time.monotonic() - _quota_exhausted_at) < QUOTA_COOLDOWN_SECONDS


def _mark_quota_exhausted() -> None:
    global _quota_exhausted_at
    _quota_exhausted_at = time.monotonic()


def _is_quota_exceeded(errors: list) -> bool:
    for err in errors or []:
        code = str(err.get("code", ""))
        message = str(err.get("message", "")).lower()
        if code == "429" or "quota" in message:
            return True
    return False


def _interpret_response(data: dict) -> dict:
    """ODsay가 실제로 내려주는 응답 형태 네 가지를 구분한다.

    1) {"error": [{"code": "429", "message": "Daily quota exceeded"}]} — 쿼터 소진 → 503
    2) {"error": [{"code": ..., "message": ...}]} — 그 외 API 자체 오류(인증 실패 등) → 502
    3) {"result": {..., "path": []}} — 정상 응답이지만 경로 후보가 없음 → 404
    4) {"result": {..., "path": [...]}} — 정상 응답
    """
    if "error" in data:
        if _is_quota_exceeded(data["error"]):
            raise OdsayQuotaExceededError(f"ODsay 쿼터 소진: {data['error']}")
        raise OdsayError(f"ODsay 오류 응답: {data['error']}")

    if "result" not in data:
        raise OdsayError(f"ODsay 응답 형식이 예상과 다름: {data}")

    if not data["result"].get("path"):
        raise OdsayNoCandidateError("ODsay가 경로 후보를 반환하지 않음")

    return data


def _load_fixture() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)
