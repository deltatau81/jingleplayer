"""Launch actual frozen executable from a temporary working directory."""
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from jingleplayer_version import APP_VERSION
root = Path(__file__).resolve().parent
system = platform.system()
if system == "Windows":
    exe = root / "dist/Jingleplayer.exe"
elif system == "Darwin":
    exe = root / "dist/macos" / platform.machine() / "Jingleplayer.app/Contents/MacOS/Jingleplayer"
else:
    exe = root / "dist/linux/Jingleplayer/Jingleplayer"
with tempfile.TemporaryDirectory(prefix="jingleplayer-launch-") as temp:
    report = Path(temp) / "report.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    subprocess.run([str(exe), "--build-smoke-test", str(report)], cwd=temp, env=env, check=True, timeout=120)
    assert json.loads(report.read_text()) == {"version": APP_VERSION, "success": True}
print("Frozen runtime smoke check passed (dummy audio/offscreen Qt)")
