"""
Core data models for decision tracking.

Inspired by Minsky's Society of Mind:
- active_context: K-lines - what agents/tools were active when deciding
- related_decisions: Connect new K-lines to old ones (societies of memories)
- mental_state: Reconstruction hints for future self
- teaching_notes: What past-self wants future-self to know
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class Outcome(str, Enum):
    """Possible outcomes for a reviewed decision."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


class Stakes(str, Enum):
    """Stakes level for a decision."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(str, Enum):
    """Status of a decision."""
    PENDING = "pending"
    REVIEWED = "reviewed"


class MentalState(str, Enum):
    """
    Mental state when making the decision.
    Helps future-self reconstruct the context (Minsky: reconstruction, not retrieval).
    """
    DELIBERATE = "deliberate"      # Careful, reasoned analysis
    REACTIVE = "reactive"          # Quick response to situation
    EXPLORATORY = "exploratory"    # Trying something new, uncertain
    HABITUAL = "habitual"          # Standard practice, routine
    PRESSURED = "pressured"        # Under time/resource constraints


class ReasonType(str, Enum):
    """
    Type of reasoning used to support a decision.

    From Minsky Ch 18: "The more reasons we can find in favor of a
    particular decision, the more confidence we can have in it."

    Tracking reason types helps calibration: which reasoning styles
    are most reliable for you?
    """
    PATTERN = "pattern"            # Similar to past experience that worked
    ANALYSIS = "analysis"          # First principles reasoning
    AUTHORITY = "authority"        # Expert/source recommends this
    INTUITION = "intuition"        # Gut feeling, can't fully articulate
    EMPIRICAL = "empirical"        # Based on data/evidence
    ANALOGY = "analogy"            # Similar to X, so should work here
    ELIMINATION = "elimination"    # Other options ruled out
    CONSTRAINT = "constraint"      # Required by external factors


@dataclass
class PreDecisionProtocol:
    """
    Tracks that the pre-decision workflow was followed.
    
    Evidence that the agent queried similar decisions and checked
    guardrails before making this decision.
    """
    query_run: bool = False
    similar_found: int = 0
    guardrails_checked: bool = False
    guardrails_passed: bool = False

    def to_dict(self) -> dict:
        return {
            "query_run": self.query_run,
            "similar_found": self.similar_found,
            "guardrails_checked": self.guardrails_checked,
            "guardrails_passed": self.guardrails_passed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PreDecisionProtocol":
        return cls(
            query_run=data.get("query_run", False),
            similar_found=data.get("similar_found", 0),
            guardrails_checked=data.get("guardrails_checked", False),
            guardrails_passed=data.get("guardrails_passed", False),
        )


@dataclass
class RelatedDecision:
    """
    A reference to a related past decision with similarity distance.
    """
    id: str
    title: Optional[str] = None
    distance: Optional[float] = None

    def to_dict(self) -> dict:
        result = {"id": self.id}
        if self.title:
            result["title"] = self.title
        if self.distance is not None:
            result["distance"] = self.distance
        return result

    @classmethod
    def from_dict(cls, data: dict | str) -> "RelatedDecision":
        # Handle legacy format (just a string ID)
        if isinstance(data, str):
            return cls(id=data)
        return cls(
            id=data.get("id", ""),
            title=data.get("title"),
            distance=data.get("distance"),
        )


@dataclass
class Reason:
    """
    A single reason supporting a decision.

    Multiple independent reasons = stronger argument (parallel bundles).
    """
    reason_type: ReasonType
    text: str
    strength: float = 0.5  # 0.0 = weak, 1.0 = strong

    def __post_init__(self):
        if isinstance(self.reason_type, str):
            self.reason_type = ReasonType(self.reason_type)
        self.strength = max(0.0, min(1.0, float(self.strength)))

    def to_dict(self) -> dict:
        return {
            "type": self.reason_type.value,
            "text": self.text,
            "strength": self.strength,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Reason":
        return cls(
            reason_type=data.get("type", data.get("reason_type", "analysis")),
            text=data["text"],
            strength=data.get("strength", 0.5),
        )


@dataclass
class Decision:
    """
    A single decision with metadata for tracking and review.

    Core Attributes:
        id: Unique identifier for the decision
        timestamp: When the decision was made
        summary: Brief description of the decision
        confidence: Confidence level (0.0 to 1.0)
        category: Category/domain of the decision
        stakes: How important is this decision
        context: Additional context about the situation
        alternatives: Other options that were considered
        review_date: When to review the outcome
        status: Current status (pending/reviewed)

    K-Line Attributes (Society of Mind):
        active_context: What tools/files/APIs were active when deciding
        related_decisions: IDs of related past decisions (K-line hierarchy)
        mental_state: How the decision was made (reconstruction hint)
        teaching_notes: What past-self wants future-self to know

    Review Attributes:
        outcome: Result after review
        actual_result: What actually happened
        lessons: What was learned
        reviewed_at: When the review was done
    """

    summary: str
    confidence: float

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: str = "general"
    stakes: Stakes = Stakes.MEDIUM
    context: Optional[str] = None
    alternatives: list[str] = field(default_factory=list)
    review_date: Optional[datetime] = None
    status: Status = Status.PENDING

    # K-Line fields (Society of Mind)
    active_context: list[str] = field(default_factory=list)
    related_decisions: list[RelatedDecision] = field(default_factory=list)
    mental_state: Optional[MentalState] = None
    teaching_notes: Optional[str] = None

    # Pre-decision protocol tracking
    pre_decision_protocol: Optional[PreDecisionProtocol] = None

    # Multiple reasons (Minsky Ch 18: strength from multitude)
    reasons: list[Reason] = field(default_factory=list)

    # Post-review fields
    outcome: Optional[Outcome] = None
    actual_result: Optional[str] = None
    lessons: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate and normalize fields."""
        # Clamp confidence to [0, 1]
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

        # Convert string enums if needed
        if isinstance(self.stakes, str):
            self.stakes = Stakes(self.stakes)
        if isinstance(self.status, str):
            self.status = Status(self.status)
        if isinstance(self.outcome, str):
            self.outcome = Outcome(self.outcome)
        if isinstance(self.mental_state, str):
            self.mental_state = MentalState(self.mental_state)

    @property
    def is_pending(self) -> bool:
        """Check if decision is pending review."""
        return self.status == Status.PENDING

    @property
    def is_due(self) -> bool:
        """Check if decision is due for review."""
        if not self.review_date or not self.is_pending:
            return False
        return datetime.utcnow() >= self.review_date

    @property
    def outcome_binary(self) -> Optional[float]:
        """
        Convert outcome to binary for Brier score calculation.

        Returns:
            1.0 for success, 0.0 for failure, None for partial/inconclusive
        """
        if self.outcome == Outcome.SUCCESS:
            return 1.0
        elif self.outcome == Outcome.FAILURE:
            return 0.0
        return None

    def set_review_in_days(self, days: int) -> None:
        """Set review date to N days from now."""
        self.review_date = datetime.utcnow() + timedelta(days=days)

    def link_decision(self, decision_id: str, title: Optional[str] = None, distance: Optional[float] = None) -> None:
        """Link this decision to a related past decision (K-line hierarchy)."""
        # Check if already linked
        for rd in self.related_decisions:
            if rd.id == decision_id:
                return
        self.related_decisions.append(RelatedDecision(id=decision_id, title=title, distance=distance))

    def add_context(self, context_item: str) -> None:
        """Add an active context item (tool, file, API, etc.)."""
        if context_item not in self.active_context:
            self.active_context.append(context_item)

    def add_reason(
        self,
        reason_type: ReasonType | str,
        text: str,
        strength: float = 0.5
    ) -> None:
        """
        Add a reason supporting this decision.

        Multiple independent reasons = stronger argument (parallel bundles).
        """
        if isinstance(reason_type, str):
            reason_type = ReasonType(reason_type)
        self.reasons.append(Reason(reason_type=reason_type, text=text, strength=strength))

    @property
    def reason_types_used(self) -> list[str]:
        """Get list of unique reason types used."""
        return list(set(r.reason_type.value for r in self.reasons))

    @property
    def average_reason_strength(self) -> Optional[float]:
        """Get average strength of all reasons."""
        if not self.reasons:
            return None
        return sum(r.strength for r in self.reasons) / len(self.reasons)

    @property
    def reason_diversity_score(self) -> float:
        """
        Calculate diversity of reasoning types (0.0 to 1.0).

        From noxious6's insight: decisions that feel well-supported often have
        correlated reasons that fail together. True robustness comes from
        independent, diverse reasoning types.

        Score = unique_types / total_reasons
        - 1.0 = every reason is a different type (maximum diversity)
        - 0.2 = 5 reasons all same type (weak, correlated)

        Returns:
            Diversity score, or 0.0 if no reasons
        """
        if not self.reasons:
            return 0.0
        unique_types = len(set(r.reason_type for r in self.reasons))
        return unique_types / len(self.reasons)

    @property
    def has_diverse_reasons(self) -> bool:
        """
        Check if decision has sufficiently diverse reasoning.

        Threshold: more than half of reasons should be different types.
        A decision with 2 reasons of same type is NOT diverse.
        A decision with 4 reasons needs at least 3 unique types.
        """
        if len(self.reasons) < 2:
            return True  # Single reason or none is trivially diverse
        return self.reason_diversity_score > 0.5

    def get_reason_diversity_warning(self) -> Optional[str]:
        """
        Return a warning if reasons appear correlated.

        Returns:
            Warning message if diversity is low, None otherwise
        """
        if len(self.reasons) < 2:
            return None

        score = self.reason_diversity_score
        if score <= 0.5:
            types_used = self.reason_types_used
            return (
                f"Low reason diversity ({score:.0%}). "
                f"All reasons are type: {', '.join(types_used)}. "
                f"Consider adding independent reasoning types for robustness."
            )

    def review(
        self,
        outcome: Outcome | str,
        actual_result: Optional[str] = None,
        lessons: Optional[str] = None,
    ) -> None:
        """
        Record the outcome of this decision.

        Args:
            outcome: What happened (success/failure/partial/inconclusive)
            actual_result: Description of what actually happened
            lessons: What was learned from this decision
        """
        if isinstance(outcome, str):
            outcome = Outcome(outcome)

        self.outcome = outcome
        self.actual_result = actual_result
        self.lessons = lessons
        self.reviewed_at = datetime.utcnow()
        self.status = Status.REVIEWED

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "confidence": self.confidence,
            "category": self.category,
            "stakes": self.stakes.value,
            "context": self.context,
            "alternatives": self.alternatives,
            "review_date": self.review_date.isoformat() if self.review_date else None,
            "status": self.status.value,
            # K-Line fields
            "active_context": self.active_context,
            "related_decisions": [rd.to_dict() for rd in self.related_decisions],
            "mental_state": self.mental_state.value if self.mental_state else None,
            "teaching_notes": self.teaching_notes,
            # Pre-decision protocol
            "pre_decision_protocol": self.pre_decision_protocol.to_dict() if self.pre_decision_protocol else None,
            # Reasons (Minsky Ch 18)
            "reasons": [r.to_dict() for r in self.reasons],
            # Review fields
            "outcome": self.outcome.value if self.outcome else None,
            "actual_result": self.actual_result,
            "lessons": self.lessons,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        """Create Decision from dictionary."""
        # Parse datetime fields
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("review_date"), str):
            data["review_date"] = datetime.fromisoformat(data["review_date"])
        if isinstance(data.get("reviewed_at"), str):
            data["reviewed_at"] = datetime.fromisoformat(data["reviewed_at"])

        # Parse reasons
        if "reasons" in data and data["reasons"]:
            data["reasons"] = [Reason.from_dict(r) for r in data["reasons"]]

        # Parse related_decisions (handle both legacy string list and new format)
        if "related_decisions" in data and data["related_decisions"]:
            data["related_decisions"] = [RelatedDecision.from_dict(rd) for rd in data["related_decisions"]]

        # Parse pre_decision_protocol
        if "pre_decision_protocol" in data and data["pre_decision_protocol"]:
            data["pre_decision_protocol"] = PreDecisionProtocol.from_dict(data["pre_decision_protocol"])

        return cls(**data)

    def to_markdown(self) -> str:
        """Export decision as markdown."""
        lines = [
            f"## {self.summary}",
            "",
            f"- **ID:** `{self.id}`",
            f"- **Date:** {self.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"- **Confidence:** {self.confidence:.0%}",
            f"- **Category:** {self.category}",
            f"- **Stakes:** {self.stakes.value}",
        ]

        if self.mental_state:
            lines.append(f"- **Mental State:** {self.mental_state.value}")

        if self.context:
            lines.extend(["", f"**Context:** {self.context}"])

        if self.teaching_notes:
            lines.extend(["", f"**Teaching Notes:** {self.teaching_notes}"])

        if self.reasons:
            lines.extend(["", "**Reasons (parallel support):**"])
            for r in self.reasons:
                strength_bar = "●" * int(r.strength * 5) + "○" * (5 - int(r.strength * 5))
                lines.append(f"- [{r.reason_type.value}] {r.text} ({strength_bar})")

            # Add diversity warning if applicable
            warning = self.get_reason_diversity_warning()
            if warning:
                lines.extend(["", f"⚠️ **Diversity Warning:** {warning}"])

        if self.active_context:
            lines.extend(["", "**Active Context (K-Lines):**"])
            for ctx in self.active_context:
                lines.append(f"- {ctx}")

        if self.alternatives:
            lines.extend(["", "**Alternatives considered:**"])
            for alt in self.alternatives:
                lines.append(f"- {alt}")

        if self.related_decisions:
            lines.extend(["", "**Related Decisions:**"])
            for rd in self.related_decisions:
                if rd.distance is not None:
                    lines.append(f"- {rd.title or rd.id} (distance: {rd.distance:.3f})")
                else:
                    lines.append(f"- {rd.title or rd.id}")

        if self.pre_decision_protocol:
            pdp = self.pre_decision_protocol
            lines.extend(["", "**Pre-Decision Protocol:**"])
            lines.append(f"- Query run: {'✅' if pdp.query_run else '❌'} (found {pdp.similar_found})")
            lines.append(f"- Guardrails: {'✅ passed' if pdp.guardrails_passed else '❌ blocked' if pdp.guardrails_checked else '⏭️ skipped'}")

        if self.review_date:
            lines.append(f"- **Review Date:** {self.review_date.strftime('%Y-%m-%d')}")

        if self.status == Status.REVIEWED:
            lines.extend([
                "",
                "### Outcome",
                f"- **Result:** {self.outcome.value if self.outcome else 'N/A'}",
            ])
            if self.actual_result:
                lines.append(f"- **What happened:** {self.actual_result}")
            if self.lessons:
                lines.append(f"- **Lessons:** {self.lessons}")
            if self.reviewed_at:
                lines.append(f"- **Reviewed:** {self.reviewed_at.strftime('%Y-%m-%d')}")

        return "\n".join(lines)
