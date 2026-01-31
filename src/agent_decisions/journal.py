"""
Journal - file-based decision storage and retrieval.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from .models import Decision, Outcome, Stakes, Status
from .stats import Stats, calculate_stats


class Journal:
    """
    File-based decision journal.
    
    Stores decisions as YAML files in a directory structure:
    decisions/
      YYYY/
        MM/
          YYYY-MM-DD-decision-XXX.md
      DECISIONS.md  (index/summary)
    """
    
    def __init__(self, path: str | Path = "./decisions"):
        """
        Initialize journal at the given path.
        
        Args:
            path: Directory to store decisions
        """
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Decision] = {}
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all decisions from disk into cache."""
        self._cache.clear()
        
        # Walk through year/month directories
        for year_dir in self.path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                
                for file in month_dir.glob("*.yaml"):
                    try:
                        decision = self._load_file(file)
                        self._cache[decision.id] = decision
                    except Exception as e:
                        print(f"Warning: Failed to load {file}: {e}")
    
    def _load_file(self, path: Path) -> Decision:
        """Load a single decision from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return Decision.from_dict(data)
    
    def _save_file(self, decision: Decision) -> Path:
        """Save a decision to a YAML file."""
        # Create directory structure: YYYY/MM/
        date = decision.timestamp
        dir_path = self.path / f"{date.year}" / f"{date.month:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Filename: YYYY-MM-DD-decision-XXX.yaml
        filename = f"{date.strftime('%Y-%m-%d')}-decision-{decision.id}.yaml"
        file_path = dir_path / filename
        
        with open(file_path, "w") as f:
            yaml.dump(decision.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        return file_path
    
    def _find_file(self, decision_id: str) -> Optional[Path]:
        """Find the file path for a decision by ID."""
        for year_dir in self.path.iterdir():
            if not year_dir.is_dir():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for file in month_dir.glob(f"*-decision-{decision_id}.yaml"):
                    return file
        return None
    
    def log(
        self,
        summary: str,
        confidence: float,
        category: str = "general",
        stakes: Stakes | str = Stakes.MEDIUM,
        context: Optional[str] = None,
        alternatives: Optional[list[str]] = None,
        review_days: Optional[int] = None,
    ) -> Decision:
        """
        Log a new decision.
        
        Args:
            summary: Brief description of the decision
            confidence: Confidence level (0.0 to 1.0)
            category: Category/domain
            stakes: Importance level
            context: Additional context
            alternatives: Other options considered
            review_days: Days until review (sets review_date)
        
        Returns:
            The created Decision object
        """
        if isinstance(stakes, str):
            stakes = Stakes(stakes)
        
        decision = Decision(
            summary=summary,
            confidence=confidence,
            category=category,
            stakes=stakes,
            context=context,
            alternatives=alternatives or [],
        )
        
        if review_days:
            decision.set_review_in_days(review_days)
        
        self._save_file(decision)
        self._cache[decision.id] = decision
        self._update_index()
        
        return decision
    
    def get(self, decision_id: str) -> Optional[Decision]:
        """Get a decision by ID."""
        return self._cache.get(decision_id)
    
    def review(
        self,
        decision_id: str,
        outcome: Outcome | str,
        actual_result: Optional[str] = None,
        lessons: Optional[str] = None,
    ) -> Optional[Decision]:
        """
        Record the outcome of a decision.
        
        Args:
            decision_id: ID of the decision to review
            outcome: What happened
            actual_result: Description of what actually happened
            lessons: What was learned
        
        Returns:
            The updated Decision, or None if not found
        """
        decision = self._cache.get(decision_id)
        if not decision:
            return None
        
        decision.review(outcome, actual_result, lessons)
        self._save_file(decision)
        self._update_index()
        
        return decision
    
    def list_all(self) -> list[Decision]:
        """Get all decisions."""
        return list(self._cache.values())
    
    def list_pending(self) -> list[Decision]:
        """Get all pending (unreviewed) decisions."""
        return [d for d in self._cache.values() if d.is_pending]
    
    def list_due(self) -> list[Decision]:
        """Get all decisions due for review."""
        return [d for d in self._cache.values() if d.is_due]
    
    def list_by_category(self, category: str) -> list[Decision]:
        """Get all decisions in a category."""
        return [d for d in self._cache.values() if d.category == category]
    
    def stats(self) -> Stats:
        """Calculate statistics for all decisions."""
        return calculate_stats(list(self._cache.values()))
    
    def _update_index(self) -> None:
        """Update the DECISIONS.md index file."""
        stats = self.stats()
        
        lines = [
            "# Decision Journal",
            "",
            f"*Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC*",
            "",
            "## Summary",
            "",
            f"- **Total Decisions:** {stats.total_decisions}",
            f"- **Reviewed:** {stats.reviewed_decisions}",
            f"- **Pending:** {stats.pending_decisions}",
        ]
        
        if stats.accuracy is not None:
            lines.append(f"- **Accuracy:** {stats.accuracy:.1%}")
        if stats.brier_score is not None:
            lines.append(f"- **Brier Score:** {stats.brier_score:.3f}")
        
        # Recent decisions
        recent = sorted(self._cache.values(), key=lambda d: d.timestamp, reverse=True)[:10]
        if recent:
            lines.extend([
                "",
                "## Recent Decisions",
                "",
            ])
            for d in recent:
                status = "✅" if d.outcome == Outcome.SUCCESS else "❌" if d.outcome == Outcome.FAILURE else "⏳"
                lines.append(
                    f"- {status} `{d.id}` [{d.timestamp.strftime('%Y-%m-%d')}] "
                    f"{d.summary[:50]}{'...' if len(d.summary) > 50 else ''}"
                )
        
        # Pending reviews
        due = self.list_due()
        if due:
            lines.extend([
                "",
                "## Due for Review",
                "",
            ])
            for d in due:
                lines.append(f"- `{d.id}` {d.summary[:50]}")
        
        index_path = self.path / "DECISIONS.md"
        with open(index_path, "w") as f:
            f.write("\n".join(lines))
    
    def export_markdown(self) -> str:
        """Export all decisions as markdown."""
        decisions = sorted(self._cache.values(), key=lambda d: d.timestamp, reverse=True)
        
        lines = [
            "# Decision Journal Export",
            "",
            f"*Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC*",
            "",
            "---",
            "",
        ]
        
        for d in decisions:
            lines.append(d.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def export_json(self) -> str:
        """Export all decisions as JSON."""
        decisions = sorted(self._cache.values(), key=lambda d: d.timestamp, reverse=True)
        return json.dumps([d.to_dict() for d in decisions], indent=2, default=str)
