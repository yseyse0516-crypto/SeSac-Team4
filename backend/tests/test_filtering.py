import pytest

from app.services.filtering import (
    IMPROVEMENT_RATIO_THRESHOLD,
    ScoredCandidate,
    compute_minute_improvement,
    select_candidates,
)


def _candidate(total_time_min, congestion_score):
    return ScoredCandidate(
        path_type="subway+bus",
        total_time_min=total_time_min,
        congestion_score=congestion_score,
        segments=[],
    )


def test_baseline_is_fastest_candidate():
    fast = _candidate(60, 0.8)
    slow = _candidate(74, 0.3)
    results, _ = select_candidates([slow, fast])
    # fastest 후보 자신은 항상 결과에 포함됨
    fastest_result = next(r for r in results if r["candidate"] is fast)
    assert fastest_result is not None


def test_slower_and_more_congested_candidate_is_never_recommended():
    baseline = _candidate(60, 0.3)
    strictly_worse = _candidate(90, 0.5)  # 더 느리면서 더 혼잡 — 나쁜 추천의 전형
    results, _ = select_candidates([baseline, strictly_worse])
    worse_result = next(r for r in results if r["candidate"] is strictly_worse)
    assert worse_result["is_recommended"] is False
    assert worse_result["minute_improvement_ratio"] < 0


def test_big_improvement_for_small_extra_time_is_recommended():
    baseline = _candidate(60, 0.9)  # 빠르지만 혼잡
    comfortable = _candidate(65, 0.1)  # 5분만 더 써서 훨씬 쾌적 (0.16/분 개선)
    results, is_same = select_candidates([baseline, comfortable])

    comfortable_result = next(r for r in results if r["candidate"] is comfortable)
    assert comfortable_result["minute_improvement_ratio"] == pytest.approx((0.9 - 0.1) / 5)
    assert comfortable_result["minute_improvement_ratio"] >= IMPROVEMENT_RATIO_THRESHOLD
    assert comfortable_result["is_recommended"] is True
    assert is_same is False


def test_small_improvement_for_large_extra_time_is_not_recommended():
    baseline = _candidate(60, 0.5)
    barely_better = _candidate(80, 0.45)  # 20분 더 써서 고작 0.05 개선 (0.0025/분)
    results, _ = select_candidates([baseline, barely_better])

    result = next(r for r in results if r["candidate"] is barely_better)
    assert result["minute_improvement_ratio"] < IMPROVEMENT_RATIO_THRESHOLD
    assert result["is_recommended"] is False


def test_is_same_when_fastest_is_also_recommended():
    only = _candidate(60, 0.3)
    results, is_same = select_candidates([only])
    assert is_same is True
    assert results[0]["is_recommended"] is True


def test_same_time_but_less_congested_is_always_eligible():
    baseline = _candidate(60, 0.5)
    equally_fast_more_comfortable = _candidate(60, 0.2)
    ratio = compute_minute_improvement(baseline, equally_fast_more_comfortable)
    assert ratio == float("inf")


def test_empty_candidate_list():
    results, is_same = select_candidates([])
    assert results == []
    assert is_same is False
