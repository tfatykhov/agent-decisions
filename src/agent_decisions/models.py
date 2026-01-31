"""
Core data models for decision tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import uuid


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


@dataclass
class Decision:
    """
    A single decision with metadata for tracking and review.
    
    Attributes:
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
        return {
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
            "outcome": self.outcome.value if self.outcome else None,
            "actual_result": self.actual_result,
            "lessons": self.lessons,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }
    
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
        
        if self.context:
            lines.extend(["", f"**Context:** {self.context}"])
        
        if self.alternatives:
            lines.extend(["", "**Alternatives considered:**"])
            for alt in self.alternatives:
                lines.append(f"- {alt}")
        
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
