# 텅텅 스코어링 로직 상세 기록 (Q1~Q4)

> 2026-08-19 저녁, 전체 로직을 처음부터 다시 정독하며 재검토한 결과를 정리한 문서.
> `backend.md` §7이 "무엇으로 정했는지"를 압축해서 담은 결정 로그라면, 이 문서는 "그래서
> 실제로 코드가 어떻게 계산하는지"를 예시와 함께 자세히 풀어쓴 참고 자료다. 두 문서가
> 어긋나면 **코드가 진실이고, backend.md 쪽을 고쳐야 할 신호**로 취급한다(실제로 이번
> 재검토에서 그런 사례를 하나 찾아서 아래 "이번에 발견한 것"에 기록했다).

## 1. 로직 파일 위치

| 파일 | 역할 | 담당 |
|---|---|---|
| `backend/app/services/matching.py` | Q4 — ODsay 좌표/ID를 텅텅 DB의 station_id/stop_id로 매칭 | A |
| `backend/app/services/scoring.py` | Q1(혼잡 점수) + Q3(정차순번 감산) | A |
| `backend/app/services/filtering.py` | Q2 — baseline 선정 + 분당개선 필터링 + 추천 선정 | A |
| `backend/app/services/hardcoded_weights.py` | ⚠️ 임시 가중치 데이터(placeholder) — 실제 배치 DB 연결 전까지 사용 | A |
| `backend/app/services/odsay_parser.py` | ODsay 원본 응답을 위 로직이 쓸 수 있는 구조로 변환 | A |
| `backend/app/routers/search.py` | 위 네 파일을 순서대로 엮어서 실행하는 진입점 (`POST /routes/search`) | A |

테스트: `backend/tests/test_matching.py`, `test_scoring.py`, `test_filtering.py`, `test_search_router.py`
(엔드투엔드). 전부 `pytest backend/tests -q`로 실행.

## 2. 전체 흐름

```
ODsay 응답(원본)
  → odsay_parser.parse_odsay_result()      # subPath[] → ParsedSegment[]
  → odsay_parser.fill_walk_coordinates()   # 도보 구간 좌표 보간
  → [세그먼트 단위 반복]
      → matching.match_subway_station() / match_bus_stop()   # Q4
      → scoring.score_segment()                              # Q1 + Q3
  → scoring.score_candidate()              # 구간 점수 → 후보 하나의 congestion_score
  → filtering.select_candidates()          # Q2 — baseline·분당개선·추천 선정
  → SearchResponse
```

**정규화 방향 (전역 규칙, 절대 어기면 안 됨):** `congestion_score`는 **0에 가까울수록 쾌적**,
1에 가까울수록 혼잡. 이 방향이 어느 한 군데서라도 뒤집히면 추천이 정확히 거꾸로 나온다 —
아래 각 절에서 "방향 검증" 항목을 따로 두고 실제로 뒤집히지 않았는지 확인했다.

---

## 3. Q1 — 구간/후보 혼잡 점수

**파일**: `scoring.py` — `score_segment()`, `score_candidate()`

```python
SUBWAY_CONGESTION_DIVISOR = 150.0
BUS_NET_ONBOARD_DIVISOR = 50.0

# 지하철
base = min(congestion_pct / 150, 1.0)

# 버스
base = min(net_onboard / 50, 1.0)

# 후보 전체 점수 = 구간 소요시간 가중평균 (도보 구간은 제외 — 혼잡 개념이 없음)
score_candidate = Σ(duration_min × score) / Σ(duration_min)   # 도보 제외 합
```

**방향 검증**: `congestion_pct`/`net_onboard`가 클수록(더 혼잡할수록) `base`도 커진다 → 0=쾌적
방향과 일치. ✅

**예시 (실제 테스트 데이터, `hardcoded_weights.py`)**:
- 답십리역(station_id=1): `congestion_pct=40.0` → `base = min(40/150, 1.0) = 0.267`
- 동대문역사문화공원(station_id=3): `congestion_pct=140.0` → `base = min(140/150, 1.0) = 0.933`

**도보 구간 처리**: `score_segment("walk", ...)`는 항상 `None`을 반환하고, `search.py`가
`segment_scores`에 아예 안 넣는다 — 도보 시간은 가중평균의 분모에서도 빠진다. 즉 "도보 구간이
얼마나 긴지"는 congestion_score에 전혀 영향을 안 준다(의도된 설계 — 걷는 데는 혼잡이라는 개념
자체가 없음). 부수 효과로 **후보 전체가 도보뿐이면 `segment_scores=[]`가 되고
`score_candidate([])`는 0.0을 반환** — "혼잡한 구간이 아예 없으니 가장 쾌적하다(0점)"가 되어
의미적으로도 맞다.

**매칭 실패 시**: `NEUTRAL_CONGESTION_SCORE = 0.5`를 그대로 쓴다(할인 없이). Q4에서 매칭에
실패한 구간(반경 밖, ID 없음 등)은 "최선도 최악도 아닌" 값으로 처리해 전체 평균을 왜곡하지
않게 한다.

⚠️ **알아둘 점 (버그는 아니고, 실데이터 연결 후 재확인 권장)**: 0.5가 정말 "중간"이려면 실제
혼잡도 분포의 중앙값과 비슷해야 의미가 있다. 지금은 `hardcoded_weights.py`의 가짜 데이터 4개
역 기준으로 봐도 congestion_pct가 40~140%로 넓게 퍼져 있어(base 0.27~0.93), 배치 DB가 실제
데이터로 교체되면 이 상수가 통계적으로 여전히 "중립"인지 한 번 확인해볼 가치가 있다. 지금
단계에서 근거 없이 바꾸는 건 의미가 없어 그대로 뒀다.

---

## 4. Q3 — 정차순번 완만한 감산

**파일**: `scoring.py` — `stop_sequence_discount()`. Q1의 `base` 점수에 곱해지는 보정 계수다.

```python
STOP_SEQUENCE_DECAY_K = 8
STOP_SEQUENCE_MAX_BONUS = 0.3

ramp = max(0.0, (K - stop_sequence) / K)
factor = 1.0 - ramp * MAX_BONUS
congestion_score = base * factor
```

원안(B, 김창영)은 "정차순번 ≤ 3이면 ×0.7, 아니면 그대로"인 계단식이었는데, `scoring.py`가
A 전담 파일이라 A 단독으로 완만한 램프 방식으로 바꿨다(backend.md §7.2, B 확인 불요 사항으로
명시돼 있음). 계단식은 순번 3→4 경계에서 추천이 갑자기 뒤집힐 수 있어 부자연스럽다는 게 이유.

**방향 검증**: `stop_sequence`가 작을수록(출고역에 가까울수록) `ramp`가 커지고 → `factor`가
작아지고 → `congestion_score`가 작아진다(더 쾌적해짐). "출고 직후라 실제로는 덜 혼잡하다"는
의도와 정확히 일치. ✅ (이 함수가 뒤집히면 "정차순번이 낮을수록 오히려 혼잡하다고 나오는" 명백한
버그가 되는데, 실제로 `test_stop_sequence_discount_monotonically_increases_toward_one`이 이
방향을 단조성으로 고정해뒀다.)

**경계값 표**:

| stop_sequence | ramp | factor | 의미 |
|---|---|---|---|
| 0 | 1.0 | 0.70 | 최대 보너스(출고 직후) |
| 4 | 0.5 | 0.85 | 중간 |
| 8 이상 | 0.0 | 1.00 | 보너스 없음(원래 점수 그대로) |
| `None`(순번 정보 없음) | — | 1.00 | 보너스 없음(중립 처리) |

K/MAX_BONUS는 **근거 데이터 없는 추정 상수**다(원안도 마찬가지). 버스는 아직 `bus_weight`에
`stop_sequence` 컬럼이 없어(§7.2, 김재우님 확인 대기 중) 지금은 버스 구간에 항상 `factor=1.0`
(보너스 없음)이 적용된다 — 데이터가 붙기 전까지는 의도된 동작이다.

---

## 5. Q4 — 좌표/ID 매칭

**파일**: `matching.py`

지하철과 버스가 **완전히 다른 방식**을 쓴다 — 이유는 ODsay가 주는 ID의 성격이 다르기 때문.

| | 지하철 | 버스 |
|---|---|---|
| ODsay가 주는 값 | `stationID`(ODsay 자체 내부 체계) | `localStationID`(표준정류장ID) |
| 매칭 방식 | 좌표 반경(100m) 최근접 탐색 | **ID 직접 매칭** (`stop_std_id == localStationID`) |
| 이유 | ODsay ID가 우리 DB station_id와 다른 체계라 좌표로 재매칭해야 함 | `localStationID`가 서울시
정류장마스터의 `정류장_ID`와 완전히 일치함을 실제 대조로 확인함(backend.md §7.3) — ID로 바로
조인 가능해서 반경 매칭보다 오매칭 위험이 없음 |
| 실패 시 | `matched=False` | `matched=False` |

⚠️ **이번 재검토에서 발견 — 문서 불일치(코드는 정상, 문서가 낡음)**: `backend.md` §7.1의
"확정 값" 요약표에는 원래 "Q4 매칭 반경: 지하철 100m, **버스 50m**"라고 적혀 있었다. 하지만
바로 다음 §7.3에서 "버스는 반경 매칭 없이 ID 직접 매칭"으로 **번복**됐고, 실제 코드
(`match_bus_stop()`)도 처음부터 반경 계산을 아예 안 한다 — `BUS_STOP_MASTER.get(stop_std_id)`로
끝. 즉 **코드는 항상 옳았고, §7.1 요약표만 나중 결정을 반영 못 하고 남아있었다.** 이번에
§7.1을 §7.3 기준으로 수정해뒀다(이 문서 작성과 같은 커밋). 실제 동작에는 영향 없었던 순수
문서 버그였지만, §7.1만 보고 "버스도 반경 매칭이겠지"라고 오해할 수 있어 바로잡을 가치가
있었음.

**매칭 반경 100m/실패 처리 방향 검증**: 매칭 실패는 Q1에서 `NEUTRAL_CONGESTION_SCORE(0.5)`로
이어진다 — "모르면 극단으로 몰지 않고 중간으로 처리"라는 의도와 일치. ✅

---

## 6. Q2 — baseline과 분당개선 필터링

**파일**: `filtering.py` — `compute_minute_improvement()`, `select_candidates()`

```python
baseline = min(candidates, key=total_time_min)          # ODsay 후보 중 최속 경로

extra_time    = candidate.total_time_min - baseline.total_time_min
improvement   = baseline.congestion_score - candidate.congestion_score
ratio         = improvement / extra_time     # extra_time > 0일 때

eligible      = baseline 자신 + (ratio >= 0.02)인 후보들
recommended   = eligible 중 congestion_score가 가장 낮은(가장 쾌적한) 후보
is_same       = recommended가 baseline과 같은 후보인가
```

**임계값 0.02의 근거**: congestion_score가 0~1 스케일이라 "분당 개선"도 그 안에서 작다.
"5분 더 써서 0.1 개선(=0.02/분)" 정도는 되어야 "돌아간 보람이 있다"고 보고 잡은 **임의
자리표시자**다(명세서엔 재차인원 "인원수" 단위 기준 사례(473 vs 0.4)만 있고, 정규화된
스케일에서의 구체적 임계값은 없음 — backend.md §11에 튜닝 필요 항목으로 이미 기록돼 있음).

**extra_time ≤ 0 처리 (동시간 또는 baseline 자신)**:
- `improvement > 0` (같은 시간에 더 쾌적) → `ratio = ∞` → **무조건 eligible** (나눌 시간이
  없으니 "분당" 개념 자체가 의미 없고, 시간 손해가 0인데 더 쾌적하면 당연히 채택 대상)
- `improvement <= 0` (같은 시간에 같거나 더 혼잡) → `ratio = 0.0` → 임계값 미달로 제외
  (baseline 자신은 별도 규칙으로 항상 eligible 유지되니 실질적으로 문제 없음)

⚠️ **이번 재검토에서 발견하고 고친 실제 버그**: 응답 JSON에 내려주는
`minute_improvement_ratio` 필드에서, `ratio=∞`인 경우를 **`0.0`으로 표시**하고 있었다.
문제는 JSON에 `Infinity`를 그대로 실을 수 없어서(표준 JSON 파서가 거부함) 대체값이 필요한 건
맞는데, 하필 `0.0`을 골라서 **"개선 없음"처럼 보이는 값이 실제로는 정반대로 "같은 시간에 더
쾌적해지는 가장 좋은 케이스"에 붙어 나가고 있었다.** `is_recommended` 판정 자체(객체 identity
비교)는 이 표시값과 무관해서 추천 로직 자체는 안 틀렸지만, 프론트가 이 숫자를 그대로 사람이
읽는 문구(예: "분당 X만큼 개선")에 쓰면 명백히 오해를 살 수 있는 상태였다.

**수정**: `∞` 대신 `congestion_score` 개선폭(`baseline.congestion_score - candidate.
congestion_score`, 항상 유한하고 이 케이스에서는 항상 0보다 큼)을 보여주도록 변경.
`backend/tests/test_filtering.py`에
`test_infinite_ratio_displays_congestion_improvement_not_zero` 테스트를 추가해 회귀를 막아둠.

**추천 로직 자체의 안전성**: `eligible`은 baseline을 무조건 포함하도록 만들어져 있어
(`e["candidate"] is baseline or ratio >= threshold`) `min(eligible, ...)`이 빈 시퀀스에서
터질 일은 없다 — 후보가 하나뿐이거나 전부 baseline보다 나쁘면 `recommended == baseline`,
`is_same == True`가 되어 프론트가 "가장 빠른 경로가 가장 쾌적하기도 합니다"로 표시할 수 있게
한 설계(backend.md §10)와 맞물려 있다.

**사소한 참고 사항 (문제 아님)**: `total_time_min`이 정확히 같은 후보가 여러 개면
`min()`은 그중 ODsay 원본 순서상 첫 번째만 `is_fastest=True`로 표시한다 — 동시에 여러 후보가
"가장 빠름" 타이틀을 나눠 가지는 상황은 없다. 실용적으로 결과에 영향 없음(추천 후보 선정
로직은 동일하게 정확히 동작).

---

## 7. 테스트 커버리지 지도

| 시나리오 | 테스트 |
|---|---|
| Q1 방향/공식 | `test_scoring.py::test_subway_score_uses_congestion_pct_and_divisor` 등 |
| Q1 상한(1.0 cap) | `test_score_capped_at_one` |
| Q3 방향(단조성) | `test_stop_sequence_discount_monotonically_increases_toward_one` |
| Q3 경계값 | `test_stop_sequence_discount_none_is_neutral` |
| Q4 지하철 반경 매칭 | `test_matching.py` |
| Q4 버스 ID 직접 매칭 | `test_matching.py`, `test_search_router.py::test_bus_segment_has_matched_stop_id_when_known` |
| Q2 baseline 선정 | `test_filtering.py::test_baseline_is_fastest_candidate` |
| Q2 나쁜 추천 배제 | `test_slower_and_more_congested_candidate_is_never_recommended` |
| Q2 임계값 경계 | `test_big_improvement_for_small_extra_time_is_recommended`,
`test_small_improvement_for_large_extra_time_is_not_recommended` |
| Q2 무한대 표시값(이번에 추가) | `test_infinite_ratio_displays_congestion_improvement_not_zero` |
| 엔드투엔드 | `test_search_router.py` (실제 ODsay 샘플 응답 17개 후보로 전체 파이프라인 검증) |

전체 실행: `python -m pytest backend/tests -q` — 현재 60개 전체 통과.

---

## 8. 종합 결론 (이번 재검토)

- **정규화 방향(0=쾌적)은 Q1·Q3·Q4 전 구간에서 뒤집힘 없이 일관됨.** 이게 제일 위험한
  실패 모드였는데 실제로 검증해보니 문제 없었음.
- **버그 1건 수정**: 분당개선이 무한대인(=가장 좋은) 케이스가 응답에 `0.0`(=개선 없음처럼
  보임)으로 나가던 것 → congestion_score 개선폭을 보여주도록 수정.
- **문서 불일치 1건 수정**: backend.md §7.1 요약표가 버스 매칭 방식(§7.3에서 번복된 ID 직접
  매칭)을 반영 못 하고 있던 것 → 표 갱신.
- **버그는 아니지만 지켜볼 것**: `NEUTRAL_CONGESTION_SCORE=0.5`가 실제 배치 데이터 분포에서도
  "중립"인지는 실데이터 연결 후 재확인 권장. `IMPROVEMENT_RATIO_THRESHOLD=0.02`는 원래부터
  임의 상수로 문서화돼 있음(튜닝 대상, backend.md §11).
