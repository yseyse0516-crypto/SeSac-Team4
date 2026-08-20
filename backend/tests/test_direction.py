from app.services import direction


def test_radial_line_descending_station_no_is_up():
    # 5호선 답십리(2543) -> 여의도(2527): 역번호 감소 -> 상선
    assert direction.determine_direction("5호선", "2543", "2527") == "상선"


def test_radial_line_ascending_station_no_is_down():
    assert direction.determine_direction("5호선", "2527", "2543") == "하선"


def test_5호선_branch_to_trunk_still_works_without_special_casing():
    # 하남검단산(2566, 지선) -> 강동(2549, 트렁크): 역번호 감소 -> 상선
    # (지선도 강동 기준 바깥쪽일수록 역번호가 커지도록 매겨져 있어 별도 처리 불필요)
    assert direction.determine_direction("5호선", "2566", "2549") == "상선"


def test_line2_ring_ascending_with_wraparound_is_outer():
    # 충정로(243) -> 시청(201): 순환 오름차순 방향(243->201, 1칸)이 더 가까움 -> 외선
    assert direction.determine_direction("2호선", "243", "201") == "외선"


def test_line2_ring_descending_with_wraparound_is_inner():
    # 시청(201) -> 충정로(243): 순환 내림차순 방향(201->243, 1칸)이 더 가까움 -> 내선
    assert direction.determine_direction("2호선", "201", "243") == "내선"


def test_line2_ring_plain_ascending_is_outer():
    assert direction.determine_direction("2호선", "210", "215") == "외선"


def test_line2_branch_station_returns_none():
    # 244~250(성수지선/신정지선)은 원형 규칙이 안 통하는 알려진 예외 — 판정하지 않음
    assert direction.determine_direction("2호선", "210", "244") is None
    assert direction.determine_direction("2호선", "244", "246") is None


def test_line1_dongmyo_ap_exception_uses_physical_order():
    # 1호선: 155(동대문) - 159(동묘앞) - 156(신설동) 순으로 물리적으로 위치.
    # 역번호만 보면 156->159가 증가(하선처럼 보이지만) 실제로는 동묘앞이 신설동보다
    # 서울역에 더 가까운 쪽(상선 방향)이다.
    assert direction.determine_direction("1호선", "156", "159") == "상선"
    assert direction.determine_direction("1호선", "155", "159") == "하선"
    assert direction.determine_direction("1호선", "159", "156") == "하선"


def test_line8_namwirye_exception_uses_physical_order():
    # 8호선: 2821(복정) - 2828(남위례) - 2822(산성) 순으로 물리적으로 위치.
    assert direction.determine_direction("8호선", "2821", "2828") == "하선"
    assert direction.determine_direction("8호선", "2828", "2822") == "하선"
    assert direction.determine_direction("8호선", "2822", "2828") == "상선"


def test_same_station_returns_none():
    assert direction.determine_direction("5호선", "2543", "2543") is None


def test_missing_inputs_return_none():
    assert direction.determine_direction(None, "2543", "2527") is None
    assert direction.determine_direction("5호선", None, "2527") is None
    assert direction.determine_direction("5호선", "2543", None) is None
