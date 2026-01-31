"""
Agent Decisions - A lightweight decision journal for AI agents.
"""

from .models import Decision, Outcome, Stakes
from .journal import Journal
from .stats import calculate_brier_score, calculate_stats

__version__ = "0.1.0"
__all__ = [
    "Decision",
    "Outcome",
    "Stakes",
    "Journal",
    "calculate_brier_score",
    "calculate_stats",
]
