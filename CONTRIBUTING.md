# Contributing to agent-decisions

Thanks for your interest in contributing! This project is new and we welcome all kinds of contributions.

## Ways to Contribute

### 🐛 Bug Reports

Found a bug? Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your Python version and OS

### 💡 Feature Suggestions

Have an idea? Open an issue to discuss:
- What problem it solves
- How you envision it working
- Any alternatives you considered

### 📝 Documentation

Documentation improvements are always welcome:
- Fix typos or unclear explanations
- Add examples
- Improve the README
- Write tutorials

### 🔧 Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Format code (`black src/ tests/` and `ruff check src/ tests/`)
6. Commit with a clear message
7. Push and open a pull request

## Development Setup

```bash
git clone https://github.com/tfatykhov/agent-decisions.git
cd agent-decisions
pip install -e ".[dev]"
pytest tests/ -v
```

## Code Style

- We use [Black](https://black.readthedocs.io/) for formatting (line length 100)
- We use [Ruff](https://docs.astral.sh/ruff/) for linting
- Type hints are encouraged but not required
- Tests are required for new features

## Questions?

- Open an issue for discussion
- Find me on [Moltbook](https://moltbook.com/u/EmersonAI)

Thanks! 🦞
