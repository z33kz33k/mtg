# Aider Coding Conventions

## Core Principles
- **Paramount**: Never ever create or change anything unless specifically asked to.
- **Conciseness**: Prefer minimal code changes. Do not refactor unless asked.
- **Ask Before Action**: If a request is ambiguous or high-risk, ask for clarification before acting.
- **Security**: Never hardcode secrets. Use environment variables.

## Technical Standards
- **Language**: Python 3.12+
- **Styling**: Use Black formatting for Python.
- **Typing**: Use strict type hints (`mypy` compliant).
- **Documentation**: Use Google-style docstrings for all public functions/classes.
- **Git**: Do not touch Git unless asked.

## Workflow
- Add comments explaining *why* something is done, not *what* is done.
- When starting a new feature, first describe your plan in a few bullet points.

## Python
- Prefer `pathlib` over `os.path`.
- Always put properties in classes before `__init__` and other methods.
- For mutated states that are part of object's public API use properties with setters and an underlying truly private attribute (double leading underscore)
- 