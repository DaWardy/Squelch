from __future__ import annotations
# Squelch test configuration
import sys
from pathlib import Path

# Ensure squelch root is on the path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent))
