"""Compatibility entry point for the modular canonical example."""

import sys
from pathlib import Path

_examples_dir = str(Path(__file__).resolve().parent.parent)
if _examples_dir not in sys.path:
    sys.path.insert(0, _examples_dir)

from processorder import project

__all__ = ["project"]
