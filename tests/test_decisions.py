"""
Tests for agent-decisions.
"""

import tempfile
from pathlib import Path

import pytest

from agent_decisions import Decision, Journal, Outcome, Stakes
from agent_decisions.stats import calculate_brier_score, calculate_stats


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
