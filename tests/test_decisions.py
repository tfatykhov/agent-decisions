"""
Tests for agent-decisions.
"""

import tempfile

import pytest

from agent_decisions import Decision, Journal, Outcome, Stakes
from agent_decisions.models import ReasonType
from agent_decisions.stats import calculate_brier_score


class TestDecision:
    """Tests for the Decision model."""

    def test_create_decision(self):
        d = Decision(summary="Test decision", confidence=0.8)
        assert d.summary == "Test decision"
        assert d.confidence == 0.8
        assert d.is_pending
        assert len(d.id) == 8

    def test_confidence_clamping(self):
        d1 = Decision(summary="Over", confidence=1.5)
        assert d1.confidence == 1.0

        d2 = Decision(summary="Under", confidence=-0.5)
        assert d2.confidence == 0.0

    def test_review(self):
        d = Decision(summary="Test", confidence=0.7)
        assert d.is_pending

        d.review(Outcome.SUCCESS, actual_result="It worked!", lessons="Trust the process")

        assert not d.is_pending
        assert d.outcome == Outcome.SUCCESS
        assert d.actual_result == "It worked!"
        assert d.lessons == "Trust the process"
        assert d.reviewed_at is not None

    def test_outcome_binary(self):
        d1 = Decision(summary="Success", confidence=0.8)
        d1.review(Outcome.SUCCESS)
        assert d1.outcome_binary == 1.0

        d2 = Decision(summary="Failure", confidence=0.8)
        d2.review(Outcome.FAILURE)
        assert d2.outcome_binary == 0.0

        d3 = Decision(summary="Partial", confidence=0.8)
        d3.review(Outcome.PARTIAL)
        assert d3.outcome_binary is None

    def test_to_dict_and_back(self):
        d = Decision(
            summary="Test roundtrip",
            confidence=0.75,
            category="testing",
            stakes=Stakes.HIGH,
            context="Some context",
            alternatives=["Option A", "Option B"],
        )
        d.set_review_in_days(7)

        data = d.to_dict()
        d2 = Decision.from_dict(data)

        assert d2.summary == d.summary
        assert d2.confidence == d.confidence
        assert d2.category == d.category
        assert d2.stakes == d.stakes
        assert d2.alternatives == d.alternatives

    def test_to_markdown(self):
        d = Decision(summary="Markdown test", confidence=0.9, category="docs")
        md = d.to_markdown()

        assert "## Markdown test" in md
        assert "90%" in md
        assert "docs" in md


class TestReasonDiversity:
    """Tests for reason diversity scoring (noxious6's insight)."""

    def test_no_reasons_returns_zero(self):
        d = Decision(summary="No reasons", confidence=0.8)
        assert d.reason_diversity_score == 0.0
        # No reasons is trivially diverse (nothing to correlate)
        assert d.has_diverse_reasons is True

    def test_single_reason_full_diversity(self):
        d = Decision(summary="One reason", confidence=0.8)
        d.add_reason(ReasonType.ANALYSIS, "First principles", 0.8)
        assert d.reason_diversity_score == 1.0
        assert d.has_diverse_reasons is True

    def test_all_same_type_low_diversity(self):
        d = Decision(summary="Correlated reasons", confidence=0.8)
        d.add_reason(ReasonType.PATTERN, "Saw this before", 0.7)
        d.add_reason(ReasonType.PATTERN, "Similar to project X", 0.8)
        d.add_reason(ReasonType.PATTERN, "Matches template", 0.6)

        # 1 unique type / 3 reasons = 0.33
        assert d.reason_diversity_score == pytest.approx(0.333, abs=0.01)
        assert d.has_diverse_reasons is False

    def test_two_same_type_not_diverse(self):
        """P1 fix: 2 reasons of same type should NOT be diverse."""
        d = Decision(summary="Two correlated reasons", confidence=0.8)
        d.add_reason(ReasonType.AUTHORITY, "Expert says so", 0.8)
        d.add_reason(ReasonType.AUTHORITY, "Paper says so", 0.7)

        # 1 unique type / 2 reasons = 0.5, but should NOT be diverse
        assert d.reason_diversity_score == 0.5
        assert d.has_diverse_reasons is False
        assert d.get_reason_diversity_warning() is not None

    def test_diverse_reasons_high_score(self):
        d = Decision(summary="Independent reasons", confidence=0.8)
        d.add_reason(ReasonType.PATTERN, "Saw this before", 0.7)
        d.add_reason(ReasonType.ANALYSIS, "First principles", 0.8)
        d.add_reason(ReasonType.EMPIRICAL, "Data supports it", 0.9)

        # 3 unique types / 3 reasons = 1.0
        assert d.reason_diversity_score == 1.0
        assert d.has_diverse_reasons is True

    def test_partial_diversity(self):
        d = Decision(summary="Mixed", confidence=0.8)
        d.add_reason(ReasonType.PATTERN, "Pattern 1", 0.7)
        d.add_reason(ReasonType.PATTERN, "Pattern 2", 0.6)
        d.add_reason(ReasonType.ANALYSIS, "Analysis", 0.8)
        d.add_reason(ReasonType.EMPIRICAL, "Data", 0.9)

        # 3 unique types / 4 reasons = 0.75
        assert d.reason_diversity_score == 0.75
        assert d.has_diverse_reasons is True

    def test_diversity_warning_when_low(self):
        d = Decision(summary="Correlated", confidence=0.8)
        d.add_reason(ReasonType.AUTHORITY, "Expert says so", 0.8)
        d.add_reason(ReasonType.AUTHORITY, "Paper says so", 0.7)
        d.add_reason(ReasonType.AUTHORITY, "Docs say so", 0.6)

        warning = d.get_reason_diversity_warning()
        assert warning is not None
        assert "Low reason diversity" in warning
        assert "authority" in warning

    def test_no_warning_when_diverse(self):
        d = Decision(summary="Diverse", confidence=0.8)
        d.add_reason(ReasonType.ANALYSIS, "First principles", 0.8)
        d.add_reason(ReasonType.EMPIRICAL, "Data supports it", 0.9)

        warning = d.get_reason_diversity_warning()
        assert warning is None

    def test_markdown_includes_warning(self):
        d = Decision(summary="Correlated decision", confidence=0.8)
        d.add_reason(ReasonType.INTUITION, "Feels right", 0.7)
        d.add_reason(ReasonType.INTUITION, "Gut says yes", 0.6)
        d.add_reason(ReasonType.INTUITION, "Just know it", 0.5)

        md = d.to_markdown()
        assert "Diversity Warning" in md


class TestJournal:
    """Tests for the Journal class."""

    def test_log_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            decision = journal.log(
                summary="Test journal",
                confidence=0.8,
                category="testing",
            )

            retrieved = journal.get(decision.id)
            assert retrieved is not None
            assert retrieved.summary == "Test journal"

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save
            j1 = Journal(tmpdir)
            d = j1.log(summary="Persist test", confidence=0.7)
            decision_id = d.id

            # Load in new journal instance
            j2 = Journal(tmpdir)
            retrieved = j2.get(decision_id)

            assert retrieved is not None
            assert retrieved.summary == "Persist test"

    def test_review_decision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            d = journal.log(summary="Review test", confidence=0.6)
            journal.review(d.id, Outcome.SUCCESS, lessons="Learned something")

            # Reload and check
            j2 = Journal(tmpdir)
            reviewed = j2.get(d.id)

            assert reviewed.outcome == Outcome.SUCCESS
            assert reviewed.lessons == "Learned something"

    def test_list_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            d1 = journal.log(summary="Pending 1", confidence=0.5)
            d2 = journal.log(summary="Pending 2", confidence=0.5)
            d3 = journal.log(summary="Reviewed", confidence=0.5)
            journal.review(d3.id, Outcome.SUCCESS)

            pending = journal.list_pending()
            assert len(pending) == 2

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            # Log some decisions
            d1 = journal.log(summary="D1", confidence=0.9, category="A")
            d2 = journal.log(summary="D2", confidence=0.8, category="A")
            d3 = journal.log(summary="D3", confidence=0.6, category="B")

            # Review some
            journal.review(d1.id, Outcome.SUCCESS)
            journal.review(d2.id, Outcome.FAILURE)

            stats = journal.stats()

            assert stats.total_decisions == 3
            assert stats.reviewed_decisions == 2
            assert stats.pending_decisions == 1
            assert stats.successes == 1
            assert stats.failures == 1
            assert stats.accuracy == 0.5


class TestBrierScore:
    """Tests for Brier score calculation."""

    def test_perfect_calibration(self):
        """100% confident and always right = 0 Brier score."""
        decisions = [
            Decision(summary=f"D{i}", confidence=1.0)
            for i in range(5)
        ]
        for d in decisions:
            d.review(Outcome.SUCCESS)

        brier = calculate_brier_score(decisions)
        assert brier == 0.0

    def test_perfectly_wrong(self):
        """100% confident and always wrong = 1 Brier score."""
        decisions = [
            Decision(summary=f"D{i}", confidence=1.0)
            for i in range(5)
        ]
        for d in decisions:
            d.review(Outcome.FAILURE)

        brier = calculate_brier_score(decisions)
        assert brier == 1.0

    def test_random_baseline(self):
        """50% confident with 50/50 outcomes ≈ 0.25 Brier score."""
        decisions = []
        for i in range(10):
            d = Decision(summary=f"D{i}", confidence=0.5)
            d.review(Outcome.SUCCESS if i % 2 == 0 else Outcome.FAILURE)
            decisions.append(d)

        brier = calculate_brier_score(decisions)
        assert brier == 0.25

    def test_ignores_non_binary_outcomes(self):
        """Partial and inconclusive outcomes are excluded."""
        decisions = [
            Decision(summary="D1", confidence=0.9),
            Decision(summary="D2", confidence=0.5),
        ]
        decisions[0].review(Outcome.SUCCESS)
        decisions[1].review(Outcome.PARTIAL)  # Should be excluded

        brier = calculate_brier_score(decisions)
        # Only D1: (0.9 - 1)^2 = 0.01
        assert brier == pytest.approx(0.01)


class TestCLIValidate:
    """Tests for the validate CLI command."""

    def test_validate_finds_low_diversity(self):
        """Validate identifies decisions with all same reason type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            # Create decision with low diversity
            d = journal.log(summary="Correlated reasons", confidence=0.8)
            decision = journal.get(d.id)
            decision.add_reason(ReasonType.PATTERN, "Pattern 1", 0.7)
            decision.add_reason(ReasonType.PATTERN, "Pattern 2", 0.8)
            decision.add_reason(ReasonType.PATTERN, "Pattern 3", 0.6)
            journal._save_file(decision)  # Re-save with reasons

            # Verify low diversity
            reloaded = journal.get(d.id)
            assert len(reloaded.reasons) == 3
            assert reloaded.reason_diversity_score == pytest.approx(0.333, abs=0.01)

    def test_validate_passes_diverse_decisions(self):
        """Validate passes decisions with diverse reasons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal(tmpdir)

            d = journal.log(summary="Diverse reasons", confidence=0.8)
            decision = journal.get(d.id)
            decision.add_reason(ReasonType.PATTERN, "Pattern", 0.7)
            decision.add_reason(ReasonType.ANALYSIS, "Analysis", 0.8)
            decision.add_reason(ReasonType.EMPIRICAL, "Data", 0.9)
            journal._save_file(decision)

            reloaded = journal.get(d.id)
            assert reloaded.has_diverse_reasons is True
