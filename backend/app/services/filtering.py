"""Q2 — baseline 및 분당개선 필터링, 비교 응답(최단시간 vs 추천) 구성.

Q2 확정: baseline = ODsay 후보 중 total_time_min 최솟값 (backend.md §7.1).
분당개선 = (baseline 대비 congestion_score 개선폭) / (추가 소요시간, 분).
이 비율이 낮은 후보(시간을 많이 써서 조금만 덜 혼잡해지는 경우)는 추천에서 제외한다
(명세서 4절 — 실제 버스 데이터로 비율 473 vs 0.4 검증됨. 단 그 수치는 원본 재차인원
"인원수" 단위 기준이고, 여기서는 congestion_score가 0~1로 정규화돼 있어 스케일이 다르다 —
구체적 임계값도 명세에 없어 아래 상수는 A가 잡은 자리표시자다. 데모 튜닝 시 조정,
backend.md §11 참고).
"""
from dataclasses import dataclass
from typing import Any

# congestion_score가 0~1 스케일이라 "분당" 개선폭도 그 범위 안에서 작다.
# 예: 10분 더 써서 congestion_score가 0.3만큼 좋아지면 0.03/분 — 이 정도는 되어야
# "돌아간 보람이 있다"고 보고 임계값을 0.02로 잡았다(=5분에 0.1 개선 이상).
IMPROVEMENT_RATIO_THRESHOLD = 0.02


@dataclass
class ScoredCandidate:
    path_type: str
    total_time_min: int
    congestion_score: float
    segments: list[Any]


def compute_minute_improvement(baseline: ScoredCandidate, candidate: ScoredCandidate) -> float:
    extra_time = candidate.total_time_min - baseline.total_time_min
    improvement = baseline.congestion_score - candidate.congestion_score

    if extra_time <= 0:
        # baseline과 같거나 더 빠르면서 덜 혼잡하기까지 하면 무조건 채택 대상
        return float("inf") if improvement > 0 else 0.0
    return improvement / extra_time


def select_candidates(candidates: list[ScoredCandidate]) -> tuple[list[dict], bool]:
    """분당개선 필터링 + 추천 후보 선정.

    반환: (각 후보별 {"candidate", "minute_improvement_ratio", "is_recommended"} 리스트, is_same)
    is_same = 최단시간 후보와 추천 후보가 동일한지 (backend.md §10 데모 처리).
    """
    if not candidates:
        return [], False

    baseline = min(candidates, key=lambda c: c.total_time_min)

    enriched = [
        {"candidate": c, "ratio": compute_minute_improvement(baseline, c)} for c in candidates
    ]

    eligible = [
        e for e in enriched
        if e["candidate"] is baseline or e["ratio"] >= IMPROVEMENT_RATIO_THRESHOLD
    ]
    recommended = min(eligible, key=lambda e: e["candidate"].congestion_score)["candidate"]
    is_same = recommended is baseline

    results = []
    for e in enriched:
        ratio = e["ratio"]
        if ratio == float("inf"):
            # extra_time<=0인데 더 쾌적하기까지 한 경우 — "분당" 개념 자체가 없다(시간을
            # 안 썼으니 나눌 수가 없음). 0.0을 쓰면 "개선 없음"처럼 보여서 실제로는 가장 좋은
            # 케이스인데 오해를 산다 — 대신 congestion_score 개선폭 자체를 보여준다(스케일은
            # "분당"이 아니지만 0이 아닌 양수라 최소한 "더 쾌적하다"는 방향은 정확히 전달됨).
            display_ratio = round(baseline.congestion_score - e["candidate"].congestion_score, 2)
        else:
            display_ratio = round(ratio, 2)
        results.append({
            "candidate": e["candidate"],
            "minute_improvement_ratio": display_ratio,
            "is_recommended": e["candidate"] is recommended,
            "is_fastest": e["candidate"] is baseline,
        })
    return results, is_same
