# Python API Reference

The `agent_decisions` package provides a Python API for integrating decision tracking into your agents or tools.

## Installation

```bash
pip install agent-decisions
```

## Quick Start

```python
from agent_decisions.journal import Journal
from agent_decisions.models import Stakes

# Initialize journal
journal = Journal("./decisions")

# Log a decision
decision = journal.log(
    summary="Switch to PostgreSQL",
    confidence=0.85,
    category="architecture",
    stakes=Stakes.HIGH,
    context="SQLite is hitting concurrency limits",
    review_days=30
)

print(f"Logged decision: {decision.id}")
```

## Core Classes

### `Decision`

The main data model representing a decision.

```python
from agent_decisions.models import Decision, Stakes, Outcome, MentalState

decision = Decision(
    summary="Use Redis for caching",
    confidence=0.9,
    category="infrastructure",
    stakes=Stakes.MEDIUM,
    context="Need sub-ms latency",
    review_date=datetime(2024, 1, 1)
)
```

**Key Attributes:**
- `id` (str): Unique 8-char hex ID.
- `timestamp` (datetime): When the decision was made.
- `summary` (str): Brief description.
- `confidence` (float): 0.0 to 1.0.
- `category` (str): Domain category (default: "general").
- `stakes` (Stakes): LOW, MEDIUM, HIGH, CRITICAL.
- `status` (Status): PENDING, REVIEWED.
- `outcome` (Outcome): SUCCESS, FAILURE, PARTIAL, INCONCLUSIVE (after review).
- `review_date` (datetime): When to review the decision.
- `active_context` (list[str]): "K-lines" - tools/files active during decision.
- `reasons` (list[Reason]): List of supporting reasons.
- `mental_state` (MentalState): DELIBERATE, REACTIVE, EXPLORATORY, HABITUAL, PRESSURED.
- `teaching_notes` (str): Notes for future self.

### `Journal`

Manages persistence and retrieval of decisions.

```python
from agent_decisions.journal import Journal

journal = Journal(path="./decisions")
```

**Methods:**

#### `log(...) -> Decision`
Creates and saves a new decision.
- **Args**: `summary`, `confidence`, `category`, `stakes`, `context`, `review_days`, `reasons`, etc.
- **Returns**: The created `Decision` object.

#### `get(decision_id: str) -> Optional[Decision]`
Retrieves a decision by its ID.

#### `review(decision_id, outcome, actual_result=None, lessons=None) -> Optional[Decision]`
Updates a decision with its outcome.
- **Args**:
  - `outcome`: `Outcome.SUCCESS`, `Outcome.FAILURE`, etc.
  - `actual_result`: Text description of what happened.
  - `lessons`: Text description of lessons learned.

#### `list_all() -> list[Decision]`
Returns all decisions in the journal.

#### `list_due() -> list[Decision]`
Returns decisions where `review_date <= now` and status is PENDING.

#### `stats() -> Stats`
Calculates statistics for the journal.

## Statistics & Analysis

### `Stats` Object
Returned by `journal.stats()`.

- `total_decisions` (int)
- `accuracy` (float): % of successes among reviewed decisions.
- `brier_score` (float): Calibration score (0=perfect, 1=worst).
- `by_category` (dict): Stats broken down by category.

### Plotting

Visualizations available in `agent_decisions.plots`.

```python
from agent_decisions import plots

decisions = journal.list_all()

# Generate a calibration curve (returns PNG bytes)
png_data = plots.plot_calibration(decisions)

# Save to file
with open("calibration.png", "wb") as f:
    f.write(png_data)
```

**Functions:**
- `plot_calibration(decisions)`: Reliability diagram.
- `plot_brier_over_time(decisions)`: Brier score trend.
- `plot_confidence_distribution(decisions)`: Histogram.
- `plot_reason_effectiveness(decisions)`: Bar chart of reason types.
- `plot_dashboard(decisions)`: All plots combined.
