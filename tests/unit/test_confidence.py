"""Unit tests for confidence scoring functions."""

import pytest

from src.utils.confidence import aggregate_confidence, compute_confidence


class TestComputeConfidence:
    def test_single_source_base(self):
        cs = compute_confidence("name", source_count=1)
        assert cs.score == 0.40

    def test_two_sources_base(self):
        cs = compute_confidence("name", source_count=2)
        assert cs.score == 0.60

    def test_three_plus_sources_base(self):
        cs = compute_confidence("name", source_count=3)
        assert cs.score == 0.75

    def test_authoritative_modifier(self):
        cs = compute_confidence("name", source_count=2, authoritative_source=True)
        assert cs.score == pytest.approx(0.75)  # 0.60 + 0.15

    def test_social_only_modifier(self):
        cs = compute_confidence("name", source_count=2, social_only=True)
        assert cs.score == pytest.approx(0.50)  # 0.60 - 0.10

    def test_contradicts_seed(self):
        cs = compute_confidence("name", source_count=2, contradicts_seed=True)
        assert cs.score == pytest.approx(0.40)  # 0.60 - 0.20

    def test_corroborates_seed(self):
        cs = compute_confidence("name", source_count=2, corroborates_seed=True)
        assert cs.score == pytest.approx(0.70)  # 0.60 + 0.10

    def test_cross_source_conflict(self):
        cs = compute_confidence("name", source_count=3, cross_source_conflict=True)
        assert cs.score == pytest.approx(0.50)  # 0.75 - 0.25

    def test_min_cap(self):
        cs = compute_confidence(
            "name",
            source_count=1,
            contradicts_seed=True,
            cross_source_conflict=True,
            social_only=True,
        )
        assert cs.score >= 0.05

    def test_max_cap(self):
        cs = compute_confidence(
            "name",
            source_count=5,
            authoritative_source=True,
            corroborates_seed=True,
        )
        assert cs.score <= 0.95

    def test_zero_sources(self):
        cs = compute_confidence("name", source_count=0)
        assert cs.score == 0.05

    def test_negative_sources(self):
        cs = compute_confidence("name", source_count=-1)
        assert cs.score == 0.05

    def test_custom_rationale(self):
        cs = compute_confidence("name", source_count=2, rationale="custom note")
        assert cs.rationale == "custom note"

    def test_auto_rationale_generated(self):
        cs = compute_confidence("name", source_count=2, authoritative_source=True)
        assert "authoritative" in cs.rationale

    def test_score_precision(self):
        cs = compute_confidence("name", source_count=2)
        assert len(str(cs.score).split(".")[-1]) <= 4


class TestAggregateConfidence:
    def test_empty_list(self):
        assert aggregate_confidence([]) == 0.05

    def test_single_score(self):
        assert aggregate_confidence([0.7]) == pytest.approx(0.7)

    def test_average(self):
        assert aggregate_confidence([0.4, 0.6]) == pytest.approx(0.5)

    def test_caps_at_max(self):
        assert aggregate_confidence([0.99, 0.99]) <= 0.95

    def test_caps_at_min(self):
        assert aggregate_confidence([0.01, 0.01]) >= 0.05
