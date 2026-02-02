"""
Agent Decisions - A lightweight decision journal for AI agents.

Inspired by Minsky's Society of Mind:
- K-lines: Store active context with decisions
- Related decisions: Link decisions like K-line hierarchies
- Mental state: Reconstruction hints for future self
- Teaching notes: What past-self wants future-self to know
- Reasons: Multiple independent reasons for robustness (Ch 18)
"""

from .journal import Journal
from .models import Decision, MentalState, Outcome, Reason, ReasonType, Stakes
from .stats import calculate_brier_score, calculate_stats

__version__ = "0.5.0"
__all__ = [
    "Decision",
    "MentalState",
    "Outcome",
    "Reason",
    "ReasonType",
    "Stakes",
    "Journal",
    "calculate_brier_score",
    "calculate_stats",
]

# Optional plots module (requires matplotlib)
try:
    from . import plots
    __all__.append("plots")
except ImportError:
    plots = None  # type: ignore
