#!/bin/bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { echo "Run on Linux" >&2; exit 1; }
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$project_root"
# PyInstaller resolves relative data sources against the generated spec directory.
python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name Jingleplayer --add-data "$project_root/HELP.md:." \
  --add-data "$project_root/assets/jingleplayer.ico:assets" \
  --workpath "$project_root/build/linux/work" \
  --specpath "$project_root/build/linux/spec" \
  --distpath "$project_root/dist/linux" \
  "$project_root/jingleplayer_app.py"
test -x "$project_root/dist/linux/Jingleplayer/Jingleplayer"
