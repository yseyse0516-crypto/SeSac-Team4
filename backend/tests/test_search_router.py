"""POST /api/v1/routes/search 통합 테스트.

main.py는 B 담당이라 여기선 테스트 전용으로 라우터만 얹은 앱을 즉석에서 만든다.
ODSAY_API_KEY가 없는 상태이므로 odsay_client가 자동으로 fixture(샘플 응답)를 사용한다 —
실제 키가 들어오면 이 테스트는 그대로 두고 call_odsay()의 실호출 경로만 별도 검증하면 된다.

2026-08-20 수정(김재우, 초안 — A 리뷰 전): search.py가 이제 hardcoded_weights.py 대신
실제 station/bus_stop/station_weight/bus_weight를 조회한다(weight_repository.py).
02_seed.sql의 더미 데이터만으로는 odsay_sample_response.json이 참조하는 실제
역/정류장(답십리·여의도, 118000070)이 없어 매칭이 안 되므로, 이 파일 전용으로
그 역/정류장에 맞는 최소한의 실제 데이터를 직접 심어둔다(_real_weight_fixture).
전체 배치(app/batch/run_batch.py)를 매 테스트 실행마다 돌리기엔 느려서, 이 두
테스트가 필요로 하는 딱 그만큼만 넣고 끝나면 지운다.

⚠️ 답십리/여의도/118000070은 odsay_sample_response.json에 맞춰 일부러 고른
"실제" 값이라, 누군가 이미 진짜 배치(python -m app.batch.run_batch)를 돌려둔
DB에서는 이 station/bus_stop 행이 이미 존재한다 — 그대로 INSERT하면
UniqueViolation이 난다. 그래서 먼저 존재 여부를 확인하고, 이미 있으면 그 행을
재사용(테어다운에서 지우지 않음)하고, 없으면 새로 만든다(테어다운에서 지움).
station_weight/bus_weight/batch_run은 이 fixture가 매번 새로 발급받는 batch_id에
묶여 있어 실제 배치 데이터와 절대 충돌하지 않는다.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import db
from app.routers.search import router
from app.services import line_geometry, weight_repository

app = FastAPI()
app.include_router(router)
client = TestClient(app)

REQUEST_BODY = {
    "origin": {"lat": 37.5012, "lng": 127.0396},
    "destination": {"lat": 37.4784, "lng": 126.8874},
}

# odsay_sample_response.json에서 실제로 쓰이는 값 (subPath 실측 확인, 2026-08-20).
_DAPSIMNI = {"name": "답십리", "line_name": "5호선", "station_no": "2543", "lat": 37.56709, "lng": 127.052361}
_YEOUIDO = {"name": "여의도", "line_name": "5호선", "station_no": "2527", "lat": 37.521624, "lng": 126.924082}
_BUS_STOP_STD_ID = "118000070"  # 여의도역6번출구
_BUS_ROUTE_ID = "5623"


@pytest.fixture(autouse=True)
def _stub_bus_curve_lookup(monkeypatch):
    """get_bus_curve()가 실제 Overpass를 호출하지 않게 막는다 — 이 파일은 라우터 동작을
    검증하는 것이라 외부망 호출까지 태울 필요가 없다(느리고 인터넷 상태에 좌우됨).
    line_geometry 자체의 캐싱/폴백 동작은 test_line_geometry.py에서 모킹으로 검증함."""
    line_geometry._bus_curve_cache.clear()
    monkeypatch.setattr(line_geometry, "_fetch_bus_line", lambda route_ref: [])
    yield
    line_geometry._bus_curve_cache.clear()


def _get_or_create_station(cur, spec):
    """(line_name, station_no) 행이 이미 있으면 재사용, 없으면 새로 만든다.
    반환값: (station_id, 이 fixture가 새로 만들었는가)."""
    cur.execute(
        "SELECT station_id FROM station WHERE line_name = %s AND station_no = %s",
        (spec["line_name"], spec["station_no"]),
    )
    row = cur.fetchone()
    if row is not None:
        return row["station_id"], False

    cur.execute(
        "INSERT INTO station (station_name, line_name, station_no, lat, lng) "
        "VALUES (%(name)s, %(line_name)s, %(station_no)s, %(lat)s, %(lng)s)",
        spec,
    )
    cur.execute("SELECT lastval() AS id")
    return cur.fetchone()["id"], True


def _get_or_create_bus_stop(cur, stop_std_id, name, lat, lng):
    """stop_std_id 행이 이미 있으면 재사용, 없으면 새로 만든다.
    반환값: (stop_id, 이 fixture가 새로 만들었는가)."""
    cur.execute("SELECT stop_id FROM bus_stop WHERE stop_std_id = %s", (stop_std_id,))
    row = cur.fetchone()
    if row is not None:
        return row["stop_id"], False

    cur.execute(
        "INSERT INTO bus_stop (stop_std_id, stop_name, lat, lng) VALUES (%s, %s, %s, %s)",
        (stop_std_id, name, lat, lng),
    )
    cur.execute("SELECT lastval() AS id")
    return cur.fetchone()["id"], True


@pytest.fixture(autouse=True)
def _real_weight_fixture():
    """search.py가 실제 DB를 조회하므로, 이 파일이 검증하려는 역/정류장에 맞는
    최소한의 station/bus_stop/station_weight/bus_weight 행을 확보하고, 이 fixture가
    직접 만든 행만 테스트 후 지운다(이미 실제 배치가 만들어둔 행은 그대로 둔다).
    time_slot/dow는 지금(now()) 기준으로 계산해 search.py가 요청 시점에 실제로
    조회할 값과 맞춘다(departure_time 미지정 시 now() 사용 — search.py 참고)."""
    dt = datetime.now()
    time_slot = weight_repository.time_slot_for(dt)
    dow = dt.weekday()

    with db.get_cursor() as cur:
        dapsimni_id, dapsimni_created = _get_or_create_station(cur, _DAPSIMNI)
        _yeouido_id, yeouido_created = _get_or_create_station(cur, _YEOUIDO)
        bus_stop_id, bus_stop_created = _get_or_create_bus_stop(
            cur, _BUS_STOP_STD_ID, "여의도역6번출구", 37.520631, 126.924843
        )

        cur.execute(
            "INSERT INTO batch_run (run_month, status, started_at, finished_at, note) "
            "VALUES ('2026-08', 'success', now(), now(), 'test_search_router.py 전용 fixture')"
        )
        cur.execute("SELECT lastval() AS id")
        batch_id = cur.fetchone()["id"]

        # station_no 2543(답십리) -> 2527(여의도)로 감소 = 상선 (direction.py 규칙과 동일)
        cur.execute(
            "INSERT INTO station_weight "
            "(station_id, batch_id, direction, time_slot, dow, net_onboard, congestion_pct, stop_sequence) "
            "VALUES (%s, %s, '상선', %s, %s, 100.0, 120.0, 5)",
            (dapsimni_id, batch_id, time_slot, dow),
        )
        cur.execute(
            "INSERT INTO bus_weight (stop_id, route_id, batch_id, time_slot, dow, net_onboard, stop_sequence) "
            "VALUES (%s, %s, %s, %s, %s, 30.0, 4)",
            (bus_stop_id, _BUS_ROUTE_ID, batch_id, time_slot, dow),
        )

    yield

    with db.get_cursor() as cur:
        # station_weight/bus_weight/batch_run은 이 fixture가 새로 발급받은 batch_id에만
        # 묶여 있으니 실제 배치 데이터와 무관하게 항상 안전하게 지운다.
        cur.execute(
            "DELETE FROM station_weight WHERE station_id = %s AND batch_id = %s",
            (dapsimni_id, batch_id),
        )
        cur.execute(
            "DELETE FROM bus_weight WHERE stop_id = %s AND batch_id = %s",
            (bus_stop_id, batch_id),
        )
        cur.execute("DELETE FROM batch_run WHERE batch_id = %s", (batch_id,))

        # station/bus_stop은 이 fixture가 직접 만든 경우에만 지운다 — 이미 실제
        # 배치가 만들어둔 행이면 그대로 둔다(다른 테스트/실제 데이터를 건드리지 않음).
        if bus_stop_created:
            cur.execute("DELETE FROM bus_stop WHERE stop_std_id = %s", (_BUS_STOP_STD_ID,))
        if dapsimni_created:
            cur.execute(
                "DELETE FROM station WHERE line_name = %s AND station_no = %s",
                (_DAPSIMNI["line_name"], _DAPSIMNI["station_no"]),
            )
        if yeouido_created:
            cur.execute(
                "DELETE FROM station WHERE line_name = %s AND station_no = %s",
                (_YEOUIDO["line_name"], _YEOUIDO["station_no"]),
            )


def test_search_returns_200_with_candidates():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidates"], "샘플 응답 기준 17개 후보가 나와야 함"
    assert len(body["candidates"]) == 17


def test_exactly_one_candidate_is_recommended():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    recommended = [c for c in body["candidates"] if c["is_recommended"]]
    assert len(recommended) == 1


def test_every_segment_has_coordinates():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    for candidate in body["candidates"]:
        for seg in candidate["segments"]:
            assert seg["start"]["lat"] is not None
            assert seg["end"]["lat"] is not None


def test_bus_segment_has_matched_stop_id_when_known():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    bus_segments = [
        seg
        for c in body["candidates"]
        for seg in c["segments"]
        if seg["mode"] == "bus"
    ]
    assert bus_segments
    # 118000070(여의도역6번출구)는 _real_weight_fixture가 심어둔 실제 bus_stop 행이라 매칭돼야 함
    matched_known = [s for s in bus_segments if s["stop_std_id"] == _BUS_STOP_STD_ID]
    assert matched_known and matched_known[0]["matched"] is True
    assert matched_known[0]["stop_id"] is not None


def test_matched_subway_segment_has_stop_sequence():
    resp = client.post("/api/v1/routes/search", json=REQUEST_BODY)
    body = resp.json()
    subway_segments = [
        seg
        for c in body["candidates"]
        for seg in c["segments"]
        if seg["mode"] == "subway" and seg["matched"]
    ]
    assert subway_segments
    assert any(seg["stop_sequence"] is not None for seg in subway_segments)


def test_out_of_range_coordinates_return_400_invalid_input():
    bad_body = {
        "origin": {"lat": 999.0, "lng": 127.0},
        "destination": {"lat": 37.4, "lng": 126.8},
    }
    resp = client.post("/api/v1/routes/search", json=bad_body)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_INPUT"


def test_wrong_type_coordinates_return_422():
    bad_body = {
        "origin": {"lat": "not-a-number", "lng": 127.0},
        "destination": {"lat": 37.4, "lng": 126.8},
    }
    resp = client.post("/api/v1/routes/search", json=bad_body)
    assert resp.status_code == 422  # FastAPI/Pydantic 자체 타입 검증 실패 (스키마 단계)
