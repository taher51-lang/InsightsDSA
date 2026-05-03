"""
WSGI entrypoint for production servers (uWSGI, Gunicorn, etc.).

Ensures ``src`` is on ``sys.path`` so ``insightsdsa`` imports resolve when the
process cwd is the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from insightsdsa.app import app as application  # noqa: E402
