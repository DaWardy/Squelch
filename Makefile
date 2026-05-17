# Squelch — Amateur Radio Operations Platform
# Makefile for common development tasks

PYTHON     = python
PYTEST     = python -m pytest
BANDIT     = bandit
PIP        = pip

.PHONY: test test-v test-cov lint security clean install dev-install \
        package docs check all

# ── Testing ───────────────────────────────────────────────────────────────

test:
	$(PYTEST) tests/ -q

test-v:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ --cov=core --cov=network --cov=modes \
	    --cov=aprs --cov=winlink \
	    --cov-report=term-missing \
	    --cov-report=html:htmlcov

test-fast:
	$(PYTEST) tests/ -q -x --tb=short

# ── Code quality ──────────────────────────────────────────────────────────

lint:
	$(PYTHON) -c "\
	import ast, sys; \
	from pathlib import Path; \
	errors = 0; \
	files = [f for f in Path('.').rglob('*.py') \
	         if '__pycache__' not in str(f) and 'venv' not in str(f)]; \
	[ast.parse(f.read_text(encoding='utf-8', errors='replace')) \
	 for f in files]; \
	print(f'Syntax OK: {len(files)} files')"

security:
	$(BANDIT) -r . --exclude ./.git,./venv,./offline_packages \
	    --severity-level medium -f txt

check: lint security test
	@echo "All checks passed"

# ── Installation ──────────────────────────────────────────────────────────

install:
	$(PIP) install -r requirements.txt

dev-install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

# ── Packaging ─────────────────────────────────────────────────────────────

package:
	$(PYTHON) -c "\
	import zipfile, os; \
	from pathlib import Path; \
	EXCLUDE = {'__pycache__', 'venv', '.git', 'logs', \
	           'recordings', 'profiles', 'offline_packages', '.pytest_cache'}; \
	with zipfile.ZipFile('dist/Squelch_v0.9.0-alpha.zip', 'w', \
	                      zipfile.ZIP_DEFLATED) as z: \
	    for f in Path('.').rglob('*'): \
	        if any(x in str(f) for x in EXCLUDE): continue; \
	        if f.is_file(): z.write(f); \
	print('Package created: dist/Squelch_v0.9.0-alpha.zip')"

# ── Docs ──────────────────────────────────────────────────────────────────

docs:
	@echo "See docs/ directory for documentation"
	@ls -la docs/

# ── Cleanup ───────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	@echo "Cleaned"

all: dev-install check docs
	@echo "All done"

help:
	@echo "Squelch development targets:"
	@echo "  make test         Run test suite"
	@echo "  make test-v       Run tests verbose"
	@echo "  make test-cov     Run with coverage report"
	@echo "  make lint         Syntax check all files"
	@echo "  make security     Bandit security scan"
	@echo "  make check        lint + security + test"
	@echo "  make install      Install runtime dependencies"
	@echo "  make dev-install  Install all dependencies incl dev"
	@echo "  make package      Build distribution zip"
	@echo "  make clean        Remove build artifacts"
