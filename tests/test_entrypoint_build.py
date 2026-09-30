import re
from pathlib import Path

import jingleplayer_app
import jingleplayer_logic


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_product_entrypoint_delegates_once_and_returns_exit_code(monkeypatch):
    calls = []
    monkeypatch.setattr(
        jingleplayer_app.jingleplayer_gui_pyside6,
        "main",
        lambda: calls.append(True) or 23,
    )
    monkeypatch.setattr(
        jingleplayer_logic,
        "initialize_settings",
        lambda: (_ for _ in ()).throw(AssertionError("entry point initialized settings")),
    )

    result = jingleplayer_app.main()

    assert result == 23
    assert calls == [True]


def test_product_entrypoint_has_no_tkinter_gui_dependency():
    assert "jingleplayer_gui_tkinter" not in jingleplayer_app.__dict__


def test_windows_build_targets_pyside6_product_entrypoint_and_resources():
    script = (PROJECT_ROOT / "build_windows.ps1").read_text(encoding="utf-8")
    compact = re.sub(r"\s+", " ", script)

    assert 'Join-Path $ProjectRoot "jingleplayer_app.py"' in compact
    assert "jingleplayer_gui_tkinter.py" not in script
    assert re.search(r"--onefile\b", script)
    assert re.search(r"--windowed\b", script)
    assert re.search(r'--name\s+"Jingleplayer"', compact)
    assert 'Join-Path $ProjectRoot "assets\\jingleplayer.ico"' in compact
    assert '--icon "$Icon"' in compact
    assert '--add-data "$Icon;assets"' in compact
    assert 'Join-Path $ProjectRoot "HELP.md"' in compact
    assert '--add-data "$HelpFile;."' in compact


def test_windows_build_uses_unique_system_temp_directory_for_pytest():
    script = (PROJECT_ROOT / "build_windows.ps1").read_text(encoding="utf-8")

    assert "[System.IO.Path]::GetTempPath()" in script
    assert "[guid]::NewGuid()" in script
    assert 'jingleplayer-pytest-temp"' not in script
    assert '--basetemp="$TestTemp"' in script
