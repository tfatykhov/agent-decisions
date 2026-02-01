# System Architecture

The `agent-decisions` system is designed to track, review, and analyze decisions made by AI agents (or humans). It follows a file-based storage approach (decisions as code) with a Python API and CLI for interaction.

## Core Modules

The system is built around four core Python modules located in `src/agent_decisions/`:

### 1. `models.py`
Defines the data structures for decisions.
- **`Decision`**: The central class representing a single decision.
- **`Reason`**: Represents a reason supporting a decision (Minsky's Society of Mind).
- **Enums**: `Stakes`, `Status`, `Outcome`, `MentalState`, `ReasonType`.
- Handles validation, serialization (to/from dict), and markdown export.

### 2. `journal.py`
Manages file-based persistence.
- **`Journal`**: The main interface for saving/loading decisions.
- **Storage**: YAML files organized by `YYYY/MM/`.
- **Indexing**: Updates `DECISIONS.md` summary file.
- **Querying**: Methods to list pending, due, or categorical decisions.

### 3. `stats.py`
Calculates performance metrics.
- **`Stats`**: Dataclass for aggregated statistics.
- **Calculations**: Brier score (calibration), accuracy, confidence stats.
- **Slicing**: Stats by category and outcome.

### 4. `plots.py`
Visualizes calibration data using Matplotlib.
- **`plot_calibration`**: Reliability diagram (predicted vs. actual).
- **`plot_brier_over_time`**: Rolling window accuracy.
- **`plot_confidence_distribution`**: Histograms of confidence.
- **`plot_dashboard`**: 2x2 grid of all plots.

## Web Dashboard (`web/app.py`)

A Flask-based web interface for visualizing the journal.
- **Routes**:
  - `/`: Dashboard summary.
  - `/decisions`: List/filter decisions.
  - `/decisions/<id>`: Detail view.
  - `/plots`: Dynamic generation of calibration plots.
  - `/stats`: Detailed statistics.
- **Templates**: Jinja2 templates in `web/templates/`.

## CLI (`cli.py`)

A Click-based command-line interface.
- Entry point: `decide` (mapped in `pyproject.toml`).
- Commands: `log`, `list`, `review`, `show`, `stats`, `export`, `plot`, `serve`.
- Uses `rich` for formatted terminal output.

## Data Flow

```mermaid
flowchart TD
    User[User / Agent]
    CLI[CLI (decide)]
    Web[Web Dashboard]
    API[Python API]
    
    subgraph Core System
        Journal[Journal Class]
        Models[Data Models]
        Stats[Stats Engine]
        Plots[Plotting Engine]
    end
    
    subgraph Storage
        Files[YAML Files (decisions/)]
        Index[DECISIONS.md]
    end
    
    User --> CLI
    User --> Web
    User --> API
    
    CLI --> Journal
    Web --> Journal
    Web --> Plots
    API --> Journal
    
    Journal --> Models
    Journal --> Files
    Journal --> Index
    
    Stats --> Models
    Plots --> Models
```

## Directory Structure

```
agent-decisions/
├── decisions/              # Default storage location
│   ├── 2023/
│   │   └── 10/
│   │       └── 2023-10-27-decision-a1b2c3d4.yaml
│   └── DECISIONS.md        # Generated index
├── src/
│   └── agent_decisions/
│       ├── cli.py          # Command-line entry point
│       ├── journal.py      # Persistence logic
│       ├── models.py       # Data classes
│       ├── plots.py        # Visualization
│       ├── stats.py        # Analysis
│       └── web/            # Web dashboard
└── docs/                   # Documentation
```
