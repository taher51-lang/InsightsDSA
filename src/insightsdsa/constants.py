"""Paths shared across the package (templates/static live under the package)."""

from pathlib import Path

# Directory containing this file: .../src/insightsdsa
PACKAGE_ROOT = Path(__file__).resolve().parent
# Repository root (parent of ``src/``)
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
