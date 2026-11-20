#!/bin/bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { echo "Run on Linux" >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name Jingleplayer --add-data 'HELP.md:.' \
  --add-data 'assets/jingleplayer.ico:assets' \
  --workpath build/linux/work --specpath build/linux/spec --distpath dist/linux \
  jingleplayer_app.py
test -x dist/linux/Jingleplayer/Jingleplayer
