# Contributing to Squelch

Squelch welcomes contributions from the ham radio and SDR communities.

## Getting Started

1. Fork the repo at github.com/dawardy/squelch
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run `python install_check.py` to verify nothing is broken
5. Submit a pull request against the `develop` branch

## What We Need Help With

- Testing on hardware we don't have (HackRF, LimeSDR, BladeRF, Airspy)
- Linux port (bootstrap.sh, OP25 integration)
- New digital mode decoders
- Bug reports with full error logs from `logs/squelch.log`
- Documentation improvements

## Code Style

- Python 3.11+
- PEP 8, 100 char line limit
- Docstrings on all public classes and methods
- No new mandatory dependencies without discussion in an issue first

## Reporting Bugs

Open a GitHub issue with:
- Squelch version
- OS and Python version
- Hardware (rig model, SDR type)
- Full error from `logs/squelch.log`
- Steps to reproduce

## Download Sources

All external dependencies must link to official or well-established
open source sources only. No mirrors, no unofficial builds.
