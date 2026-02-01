# Contributing to agent-decisions

Thanks for your interest in contributing! This project follows a "decisions as code" philosophy, and we welcome contributions that help agents make better decisions.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/tfatykhov/agent-decisions.git
   cd agent-decisions
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   Install the package in editable mode with all optional dependencies (dev, web, plots):
   ```bash
   pip install -e ".[dev,web,plots]"
   ```

## Testing

We use `pytest` for testing.

### Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_decisions.py
```

### Writing Tests
- Place tests in the `tests/` directory.
- Name files `test_*.py`.
- Ensure high coverage for core logic (`models.py`, `stats.py`).

## Code Style

We enforce strict code style to maintain quality.

- **Formatter**: [Black](https://black.readthedocs.io/)
- **Linter**: [Ruff](https://docs.astral.sh/ruff/)
- **Type Checking**: [MyPy](https://mypy-lang.org/)

### Pre-commit Checks
Before committing, run:
```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/ --fix

# Type check
mypy src/
```

## PR Workflow

1. **Create a Feature Branch**
   Always work on a branch, never on `main`.
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Commit Changes**
   Write clear, descriptive commit messages.
   ```bash
   git commit -m "feat: add support for custom plotting styles"
   ```

3. **Verify Locally**
   Run tests and linting one last time.
   ```bash
   pytest && ruff check src/
   ```

4. **Push and Create PR**
   Push your branch and open a Pull Request via GitHub.
   ```bash
   git push -u origin feature/your-feature-name
   ```

5. **Code Review**
   - Wait for review (usually from a sub-agent like CodeReviewer).
   - Address feedback with new commits.
   - Do not force-push unless necessary; we prefer history.

## Documentation

- Documentation lives in `docs/`.
- Use Markdown.
- Update `docs/API.md` if you change public APIs.
- Update `docs/CLI.md` if you change CLI commands.
