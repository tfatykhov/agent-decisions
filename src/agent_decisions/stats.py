"""
Statistics and calibration scoring.
"""

from dataclasses import dataclass
from typing import Optional

from .models import Decision, Outcome


@dataclass
class Stats:
    """Statistics about decision-making performance."""
    
    total_decisions: int
    reviewed_decisions: int
    pending_decisions: int
    
    # Outcome counts
    successes: int
    failures: int
    partial: int
    inconclusive: int
    
    # Calibration
    brier_score: Optional[float]
    accuracy: Optional[float]
    
    # Confidence stats
    avg_confidence: Optional[float]
    avg_confidence_on_success: Optional[float]
    avg_confidence_on_failure: Optional[float]
    
    # By category
    by_category: dict[str, dict]
    
    def __str__(self) -> str:
        lines = [
            "Decision Statistics",
            "=" * 40,
            f"Total: {self.total_decisions}",
            f"  Reviewed: {self.reviewed_decisions}",
            f"  Pending: {self.pending_decisions}",
            "",
            "Outcomes:",
            f"  ✅ Success: {self.successes}",
            f"  ❌ Failure: {self.failures}",
            f"  ⚡ Partial: {self.partial}",
            f"  ❓ Inconclusive: {self.inconclusive}",
        ]
        
        if self.accuracy is not None:
            lines.extend([
                "",
                f"Accuracy: {self.accuracy:.1%}",
            ])
        
        if self.brier_score is not None:
            lines.extend([
                f"Brier Score: {self.brier_score:.3f}",
                f"  (0 = perfect, 0.25 = random, 1 = always wrong)",
            ])
        
        if self.avg_confidence is not None:
            lines.extend([
                "",
                f"Avg Confidence: {self.avg_confidence:.1%}",
            ])
            if self.avg_confidence_on_success is not None:
                lines.append(f"  On success: {self.avg_confidence_on_success:.1%}")
            if self.avg_confidence_on_failure is not None:
                lines.append(f"  On failure: {self.avg_confidence_on_failure:.1%}")
        
        if self.by_category:
            lines.extend(["", "By Category:"])
            for cat, data in sorted(self.by_category.items()):
                lines.append(f"  {cat}: {data['total']} decisions, {data.get('accuracy', 0):.0%} accuracy")
        
        return "\n".join(lines)


def calculate_brier_score(decisions: list[Decision]) -> Optional[float]:
    """
    Calculate Brier score for calibration measurement.
    
    Brier score = (1/n) * Σ(confidence - outcome)²
    
    Where outcome is 1 for success, 0 for failure.
    Lower is better: 0 = perfect, 0.25 = random, 1 = always wrong.
    
    Only includes decisions with binary outcomes (success/failure).
    """
    scored = []
    
    for d in decisions:
        if d.outcome_binary is not None:
            scored.append((d.confidence, d.outcome_binary))
    
    if not scored:
        return None
    
    total = sum((conf - outcome) ** 2 for conf, outcome in scored)
    return total / len(scored)


def calculate_stats(decisions: list[Decision]) -> Stats:
    """Calculate comprehensive statistics from a list of decisions."""
    
    total = len(decisions)
    reviewed = [d for d in decisions if not d.is_pending]
    pending = [d for d in decisions if d.is_pending]
    
    # Count outcomes
    successes = sum(1 for d in reviewed if d.outcome == Outcome.SUCCESS)
    failures = sum(1 for d in reviewed if d.outcome == Outcome.FAILURE)
    partial = sum(1 for d in reviewed if d.outcome == Outcome.PARTIAL)
    inconclusive = sum(1 for d in reviewed if d.outcome == Outcome.INCONCLUSIVE)
    
    # Calculate accuracy (success / (success + failure))
    binary_outcomes = successes + failures
    accuracy = successes / binary_outcomes if binary_outcomes > 0 else None
    
    # Brier score
    brier = calculate_brier_score(reviewed)
    
    # Confidence stats
    all_conf = [d.confidence for d in decisions]
    avg_conf = sum(all_conf) / len(all_conf) if all_conf else None
    
    success_conf = [d.confidence for d in reviewed if d.outcome == Outcome.SUCCESS]
    avg_success_conf = sum(success_conf) / len(success_conf) if success_conf else None
    
    failure_conf = [d.confidence for d in reviewed if d.outcome == Outcome.FAILURE]
    avg_failure_conf = sum(failure_conf) / len(failure_conf) if failure_conf else None
    
    # By category
    categories: dict[str, dict] = {}
    for d in decisions:
        if d.category not in categories:
            categories[d.category] = {"total": 0, "success": 0, "failure": 0}
        categories[d.category]["total"] += 1
        if d.outcome == Outcome.SUCCESS:
            categories[d.category]["success"] += 1
        elif d.outcome == Outcome.FAILURE:
            categories[d.category]["failure"] += 1
    
    # Calculate accuracy per category
    for cat_data in categories.values():
        cat_binary = cat_data["success"] + cat_data["failure"]
        cat_data["accuracy"] = cat_data["success"] / cat_binary if cat_binary > 0 else 0
    
    return Stats(
        total_decisions=total,
        reviewed_decisions=len(reviewed),
        pending_decisions=len(pending),
        successes=successes,
        failures=failures,
        partial=partial,
        inconclusive=inconclusive,
        brier_score=brier,
        accuracy=accuracy,
        avg_confidence=avg_conf,
        avg_confidence_on_success=avg_success_conf,
        avg_confidence_on_failure=avg_failure_conf,
        by_category=categories,
    )
