# Contributing to Squelch

Thank you for your interest in contributing to Squelch.

## Before You Start

- Check [open issues](https://github.com/dawardy/squelch/issues)
  before starting work on a feature
- For significant changes, open an issue first to discuss approach
- Squelch is licensed GPL v3 — all contributions must be compatible

## Development Setup

```bash
# Clone
git clone https://github.com/dawardy/squelch.git
cd squelch

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run the app
python main.py --debug
```

## Code Standards

**Language:** Python 3.11+ with `from __future__ import annotations`

**Style:**
- 4-space indentation
- Max line length: 79 characters (PEP 8)
- Type hints on all public functions
- Docstrings on all public classes and methods

**Every file must have:**
- `from __future__ import annotations` as the first code line
- GPL v3 license header (see any existing file for the template)

**Error handling:**
- Never use bare `except:` — always specify the exception type
- Silent `except ... pass` is acceptable in cleanup paths
- Always log unexpected exceptions: `log.debug/warning/error()`

**Security:**
- `shell=False` on all subprocess calls
- Validate all user input through `core/validator.py`
- Never log credentials or sensitive data
- Add `# nosec BXXX` with a comment explaining why for any
  intentional Bandit exception

## Testing

Run tests before submitting:

```bash
python -m pytest tests/ -v

# Security scan
pip install bandit
bandit -r . --exclude ./venv --severity-level medium
```

All PRs must:
- Pass all existing tests
- Add tests for new functionality
- Have 0 new Bandit high/medium findings

## Adding a Rig Preset

Edit `core/rig_presets.py` — add a `RigPreset` to the `PRESETS` dict:

```python
"Manufacturer Model": RigPreset(
    name         = "Manufacturer Model",
    hamlib_model = 370,     # from rigctl -l
    baud         = 19200,
    ptt_method   = "CAT",   # CAT / RTS / DTR / VOX
    data_mode    = "USB",   # USB / FM / etc
    usb_hints    = ["CP210", "Model"],  # USB device name substrings
    supports_cat = True,
    category     = "HF",    # HF / VHF/UHF / Portable / Student etc
    notes        = "Brief description for users",
    radio_menu_steps = [
        "Step 1: Set CAT baud to 19200",
        ...
    ],
),
```

## Adding a Help Article

Edit `ui/tabs/help_tab.py` — add a tuple to `HELP_ARTICLES`:

```python
("Article Title", "Category", """
# Article Title

Content in simple Markdown-like format.
Indented lines render as code blocks.
"""),
```

## Adding an EmComm Template

Edit `winlink/templates.py` — add a function and entry to `TEMPLATE_LIST`.

## Plugin Development

See `plugins/README.md` for the plugin API.

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes with tests
4. Run the full test suite
5. Run Bandit security scan
6. Commit with a clear message
7. Push and open a Pull Request against `main`

## Code of Conduct

- Be respectful and constructive
- Focus on the technical merits
- Amateur radio is for everyone — welcome all license classes
  and experience levels

## Questions?

Open an issue tagged `question` or start a Discussion.

73 de github.com/dawardy/squelch
