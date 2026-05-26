# Contributing to Squelch

Thanks for your interest in contributing.

## Setup
```
git clone https://github.com/dawardy/squelch.git
cd squelch
python installer.py
```

## Running tests
```
venv\Scripts\python -m pytest tests/ -q
```

There are currently 401 tests. PRs must keep them passing.

## Code style
- Python: PEP 8, 4-space indent, line length ~80 chars
- All new modules need at least a smoke test in `tests/`
- Subprocess calls must use `shell=False` and an arg list
- Don't add `eval()`, `exec(str)`, or `pickle.load()` from untrusted data
- Network calls use HTTPS unless there's a documented exception

## Versioning
Squelch follows [SemVer](https://semver.org/) for pre-1.0:
- **PATCH** — bug fixes, security, housekeeping (no new features)
- **MINOR** — new features, backwards compatible
- **MAJOR** — breaking changes or 1.0 release

Bump with: `python bump_version.py patch|minor|major`
Then add a CHANGELOG entry.

## Pull requests
1. Create a branch from `main`
2. Make your changes with tests
3. Run the full suite: `pytest tests/`
4. Update CHANGELOG.md under `[Unreleased]`
5. Open a PR
