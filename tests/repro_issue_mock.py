import sys
from unittest.mock import MagicMock

# Mock yaml module
sys.modules["yaml"] = MagicMock()

# Now import
import os
sys.path.append(os.path.abspath("agent-decisions/src"))

from agent_decisions.models import Decision, ReasonType

d = Decision(summary="Test", confidence=0.8)
d.add_reason(ReasonType.ANALYSIS, "Reason 1")
d.add_reason(ReasonType.ANALYSIS, "Reason 2")

print(f"Reasons: {len(d.reasons)}")
print(f"Unique types: {len(set(r.reason_type for r in d.reasons))}")
print(f"Score: {d.reason_diversity_score}")
print(f"Has diverse: {d.has_diverse_reasons}")
print(f"Warning: {d.get_reason_diversity_warning()}")
