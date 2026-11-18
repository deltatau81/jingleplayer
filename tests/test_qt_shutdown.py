"""Exercise native Qt reference ownership in a separate interpreter."""

import os
import subprocess
import sys


def test_qt_void_calls_preserve_none_and_process_exits_cleanly():
    # No application, pygame, widgets, image decoder or project imports: this
    # isolates the binding regression PYSIDE-3509 from application lifetimes.
    script = """
import sys
from PySide6.QtCore import QTimer
timer = QTimer()
for i in range(20):
    timer.setInterval(i)
before = sys.getrefcount(None)
for i in range(100):
    timer.setInterval(i)
after = sys.getrefcount(None)
assert after == before, (before, after)
"""
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        env={**os.environ, "PYTHONFAULTHANDLER": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"Qt subprocess exited with {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
