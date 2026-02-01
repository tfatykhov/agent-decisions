# CLI Reference

The `decide` command-line tool allows you to log, track, and review decisions from your terminal.

## Installation

The CLI is installed with the package:

```bash
pip install agent-decisions
```

## Global Options

- `--dir, -d PATH`: Specify the decision journal directory (default: `./decisions`).
- `--help`: Show help message.

## Commands

### `decide log`
Log a new decision.

**Usage:**
```bash
decide log "Switch to PostgreSQL" \
  --confidence 0.85 \
  --category architecture \
  --stakes high \
  --review-in 30d \
  --reason "analysis:Postgres handles concurrency better" \
  --reason "pattern:Similar to Project X:0.9"
```

**Options:**
- `-c, --confidence FLOAT`: Confidence level (0.0-1.0) **[Required]**
- `-t, --category TEXT`: Category/domain (default: "general")
- `-s, --stakes [low|medium|high|critical]`: Importance level
- `-r, --review-in DURATION`: Review timeframe (e.g., '7d', '2w', '1m')
- `-R, --reason TEXT`: Reason in format `type:text` or `type:text:strength`
- `-k, --active-context TEXT`: Active context/tools (repeatable)
- `-a, --alternative TEXT`: Alternatives considered (repeatable)
- `-m, --mental-state [deliberate|reactive|...]`: Your mental state

### `decide list`
List decisions.

**Usage:**
```bash
decide list --due              # Show decisions due for review
decide list --pending          # Show all pending decisions
decide list --category arch    # Filter by category
```

**Options:**
- `-p, --pending`: Show only pending decisions
- `--due`: Show only decisions due for review
- `-t, --category TEXT`: Filter by category
- `-n, --limit INT`: Max number to show (default: 20)

### `decide review`
Record the outcome of a decision.

**Usage:**
```bash
decide review <ID> --outcome success \
  --result "Performance improved by 50%" \
  --lessons "Always benchmark before switching"
```

**Options:**
- `-o, --outcome [success|failure|partial|inconclusive]` **[Required]**
- `-r, --result TEXT`: What actually happened
- `-l, --lessons TEXT`: What was learned

### `decide show`
Show details of a specific decision.

**Usage:**
```bash
decide show <ID>
```

### `decide stats`
Show statistics and calibration scores.

**Usage:**
```bash
decide stats
```

### `decide plot`
Generate calibration visualizations.

**Usage:**
```bash
decide plot --type calibration --output cal.png
decide plot --show  # Display interactively
```

**Options:**
- `-t, --type [calibration|brier|confidence|reasons|dashboard]`: Plot type
- `-o, --output PATH`: Save to file (PNG)
- `-s, --show`: Display window
- `-w, --window INT`: Rolling window size for Brier score

### `decide serve`
Start the web dashboard.

**Usage:**
```bash
decide serve --port 8080
```

**Options:**
- `-p, --port INT`: Port to bind to (default: 5000)
- `-h, --host TEXT`: Host to bind to (default: 127.0.0.1)
- `--debug`: Enable Flask debug mode

### `decide export`
Export decisions to other formats.

**Usage:**
```bash
decide export --format json > backup.json
```

**Options:**
- `-f, --format [markdown|json]`: Output format (default: markdown)
