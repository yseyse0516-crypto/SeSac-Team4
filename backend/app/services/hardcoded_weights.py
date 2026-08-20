"""임시 하드코딩 가중치 — station_weight/bus_weight DB 연결 전까지 사용하는 placeholder.

⚠️ 아래 congestion_pct/net_onboard/stop_sequence 수치는 전부 로직 검증용 가짜 값이다.
실제 배치 데이터가 아니다. DB가 붙으면(backend.md §9, 8/20 오전) queries.py로 교체한다.
station_id/name/lat/lng, bus stop_std_id는 실제 ODsay 샘플 응답(odsay_sample_response.json)에서
가져온 진짜 좌표다 — matching.py 테스트가 실제 케이스로 맞아떨어지게 하기 위함.

time_slot/dow 구분은 아직 없음 — 실제 가중치 조회 연결 시(내일 오전) 반영 예정.

2026-08-20 수정: line_name/station_no 추가(direction.py가 방향을 계산하려면
필요). 값은 국가철도공단 공식 좌표 데이터(전체_도시철도역사정보_20260630.xlsx)
기준 실제 역번호다(답십리=2543, 왕십리=2541, 동대문역사문화공원=2537,
여의도=2527 — 전부 5호선, 트렁크 구간이라 역번호 오름차순=물리적 순서).
STATION_WEIGHT도 (station_id, direction) 조합으로 키를 바꿨다 — 이제
station_weight 테이블의 UNIQUE 키에 direction이 포함되므로, 이 placeholder도
같은 모양을 흉내내야 direction.py 연동을 이 파일만으로 검증할 수 있다.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StationMaster:
    station_id: int
    name: str
    lat: float
    lng: float
    line_name: str = ""
    station_no: str = ""


@dataclass
class StationWeightRow:
    congestion_pct: float
    stop_sequence: int


@dataclass
class BusStopMaster:
    stop_id: int
    stop_std_id: str
    name: str


@dataclass
class BusWeightRow:
    net_onboard: float
    stop_sequence: Optional[int] = None  # bus_weight엔 아직 이 컬럼이 없음 (backend.md §7.2)


# 좌표는 odsay_sample_response.json 실제 값 그대로 (답십리→여의도 5호선 구간).
# line_name/station_no는 공식 KRIC 데이터 기준 실제 값(위 docstring 참고) —
# 역번호가 답십리(2543)>왕십리(2541)>동대문역사문화공원(2537)>여의도(2527) 순으로
# 감소하므로, 이 순서로 이동하면 direction.py 규칙상 "상선"이 나와야 정상이다.
STATION_MASTER: list[StationMaster] = [
    StationMaster(1, "답십리", 37.567091, 127.052362, "5호선", "2543"),
    StationMaster(2, "왕십리", 37.561845, 127.037234, "5호선", "2541"),
    StationMaster(3, "동대문역사문화공원", 37.564654, 127.005665, "5호선", "2537"),
    StationMaster(4, "여의도", 37.521624, 126.924082, "5호선", "2527"),
]

# (station_id, direction) 조합이 실제 station_weight.UNIQUE 키와 같은 모양이다.
# "상선"은 위 4개 역을 답십리→여의도 순으로 이동할 때 실제로 조회되는 값
# (기존 하드코딩 값 그대로 유지 — 회귀 없음), "하선"은 반대 방향 값이 실제로
# 다르게 조회된다는 걸 보여주기 위해 새로 추가한 참고용 가짜 값이다.
STATION_WEIGHT: dict[tuple[int, Optional[str]], StationWeightRow] = {
    (1, "상선"): StationWeightRow(congestion_pct=40.0, stop_sequence=1),   # 출고 인접 — 정차순번 낮음
    (1, "하선"): StationWeightRow(congestion_pct=88.0, stop_sequence=9),
    (2, "상선"): StationWeightRow(congestion_pct=95.0, stop_sequence=3),
    (2, "하선"): StationWeightRow(congestion_pct=60.0, stop_sequence=7),
    (3, "상선"): StationWeightRow(congestion_pct=140.0, stop_sequence=7),  # 도심 환승역 — 혼잡 최고조
    (3, "하선"): StationWeightRow(congestion_pct=75.0, stop_sequence=3),
    (4, "상선"): StationWeightRow(congestion_pct=110.0, stop_sequence=16),
    (4, "하선"): StationWeightRow(congestion_pct=50.0, stop_sequence=2),
}

# stop_std_id(=ODsay localStationID)는 실제 정류장마스터 CSV와 대조 확인된 값.
# odsay_sample_response.json에서 실제로 버스 구간의 "시작" 정류장으로 쓰이는 ID로 골랐다
# (matching은 세그먼트의 startLocalStationID만 보므로 — odsay_parser.py 참고).
BUS_STOP_MASTER: dict[str, BusStopMaster] = {
    "118000070": BusStopMaster(stop_id=101, stop_std_id="118000070", name="여의도역6번출구"),
    "100000389": BusStopMaster(stop_id=102, stop_std_id="100000389", name="종로2가"),
    "105000117": BusStopMaster(stop_id=103, stop_std_id="105000117", name="답십리1동주민센터.래미안위브"),
}

BUS_WEIGHT: dict[int, BusWeightRow] = {
    101: BusWeightRow(net_onboard=12.0),
    102: BusWeightRow(net_onboard=38.0),
    103: BusWeightRow(net_onboard=25.0),
}
