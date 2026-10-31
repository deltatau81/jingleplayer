#!/bin/bash
set -euo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

[[ "$#" -eq 0 ]] || fail "This script accepts no arguments; it builds for the native Mac architecture."
[[ "$(uname -s)" == "Darwin" ]] || fail "Run this script on macOS. Windows and Linux builds are not supported."

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
native_arch="$(uname -m)"
case "$native_arch" in
    arm64|x86_64) ;;
    *) fail "Unsupported architecture '$native_arch'. Use a native arm64 or x86_64 Mac." ;;
esac

# Rosetta can report x86_64 on Apple Silicon. Require a native shell and Python.
translated="$(/usr/sbin/sysctl -in sysctl.proc_translated 2>/dev/null || true)"
[[ "$translated" != "1" ]] || fail "Rosetta translation is active. Open a native terminal and use native arm64 Python 3.11."

python_bin=""
for candidate in python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 11))' >/dev/null 2>&1; then
            python_bin="$(command -v "$candidate")"
            break
        fi
    fi
done
[[ -n "$python_bin" ]] || fail "Python 3.11 was not found on PATH. Activate a native Python 3.11 environment and retry."

python_arch="$("$python_bin" -c 'import platform; print(platform.machine())')"
[[ "$python_arch" == "$native_arch" ]] || fail "Python architecture '$python_arch' does not match native '$native_arch'. Activate a matching Python 3.11 environment."
"$python_bin" -m PyInstaller --version >/dev/null 2>&1 || fail "PyInstaller is unavailable in '$python_bin'. Prepare the development environment from requirements-dev.txt and retry."

entry_point="$project_root/jingleplayer_app.py"
help_file="$project_root/HELP.md"
ico_file="$project_root/assets/jingleplayer.ico"
icns_file="$project_root/assets/jingleplayer.icns"
for required_file in "$entry_point" "$help_file" "$ico_file" "$icns_file"; do
    [[ -f "$required_file" && -r "$required_file" ]] || fail "Required file is missing or unreadable: $required_file. Restore the real asset or source file before building."
done

work_dir="$project_root/build/macos/$native_arch/work"
spec_dir="$project_root/build/macos/$native_arch/spec"
dist_dir="$project_root/dist/macos/$native_arch"
mkdir -p -- "$work_dir" "$spec_dir" "$dist_dir"
cd -- "$project_root"

printf 'Building Jingleplayer for %s with %s\n' "$native_arch" "$python_bin"
# No Developer ID identity or notarization is configured. PyInstaller may ad-hoc sign.
"$python_bin" -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --name "Jingleplayer" \
    --target-arch "$native_arch" \
    --osx-bundle-identifier "org.jingleplayer.Jingleplayer" \
    --icon "$icns_file" \
    --add-data "$help_file:." \
    --add-data "$ico_file:assets" \
    --workpath "$work_dir" \
    --specpath "$spec_dir" \
    --distpath "$dist_dir" \
    "$entry_point" || fail "PyInstaller failed. Review its diagnostics above; no dependencies were installed by this script."

app_path="$dist_dir/Jingleplayer.app"
[[ -d "$app_path" ]] || fail "PyInstaller completed without producing the expected bundle: $app_path"
[[ -x "$app_path/Contents/MacOS/Jingleplayer" ]] || fail "The bundle executable is missing or not executable: $app_path/Contents/MacOS/Jingleplayer"
printf 'Development bundle created: %s\n' "$app_path"
printf 'Native runtime testing is required before distribution.\n'
