"""Optional generation progress; the final CLI result remains a single JSON object."""

from __future__ import annotations

import json
import sys
from typing import Callable


ProgressCallback = Callable[[str, str], None]


def report_progress(callback: ProgressCallback | None, stage: str, message: str) -> None:
    if callback is not None:
        callback(stage, message)


def write_progress(stage: str, message: str) -> None:
    print(json.dumps({
        "type": "service-architect:progress", "stage": stage, "message": message,
    }), file=sys.stderr, flush=True)
