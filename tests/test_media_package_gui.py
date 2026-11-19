from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

import jingleplayer_gui_pyside6 as gui
import jingleplayer_logic as logic
import jingleplayer_media_packages as media
from test_portable_gui import context, drain, select_export
from test_media_packages import bundle
from test_media_packages import wav


def test_full_zip_export_includes_all_presets_hidden_pools_and_backgrounds(context, bundle, tmp_path, monkeypatch):
    document, _, _, _ = bundle
    assert logic.save_settings(document)["success"]
    context.window._reload_after_import()
    before = context.active.read_bytes()
    select_export(monkeypatch, tmp_path / "all-presets")
    context.window._export_soundboard()
    drain(context)
    archive = tmp_path / "all-presets.zip"
    result = media.validate_archive(archive)
    assert len(result.settings["presets"]) == 3 and len(result.assets) == 3
    assert context.active.read_bytes() == before
    assert any(str(archive) in message[2] for message in context.messages)


@pytest.mark.parametrize("cancel", ["parent", "name"])
def test_zip_export_cancel_leaves_settings_and_audio_unchanged(context, tmp_path, monkeypatch, cancel):
    before = context.active.read_bytes()
    if cancel == "name":
        monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
        monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a: ("", False))
    context.window._export_soundboard()
    assert not context.window._package_busy and context.active.read_bytes() == before
    assert not context.stops and not list(tmp_path.glob("*.zip"))


def test_zip_import_preview_install_restart_and_duplicate_import(context, bundle, monkeypatch):
    _, archive, _, _ = bundle
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a: (str(archive), ""))
    context.window._import_zip_soundboard()
    drain(context)
    assert len(logic.settings["presets"]) == 4
    assert any("3 Presets" in q and "2 Audiodateien" in q and "1 Hintergrundbilder" in q
               and "imported_soundboards" in q for q in context.questions)
    assert not context.window._restart_required
    assert context.window.preset_combo.count() == 4
    assert all(Path(raw).is_relative_to(context.active.parent / "imported_soundboards")
               for raw, _ in media._refs({**logic.settings, "presets": logic.settings["presets"][1:]}))
    context.window._reload_after_import()
    assert not context.window.background_canvas.pixmap.isNull()
    assert logic.get_active_audio_pool(50)["audio_pool_mode"] == "manual"
    before_dirs = set((context.active.parent / "imported_soundboards").iterdir())
    context.window._import_zip_soundboard()
    drain(context)
    assert len(logic.settings["presets"]) == 7
    assert len(set((context.active.parent / "imported_soundboards").iterdir()) - before_dirs) == 1


def test_zip_import_cancel_and_corruption_do_not_change_settings(context, bundle, monkeypatch):
    _, archive, _, _ = bundle
    before = context.active.read_bytes()
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a: ("", ""))
    context.window._import_zip_soundboard()
    assert not context.window._package_busy
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a: (str(archive), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    context.window._import_zip_soundboard()
    drain(context)
    assert context.active.read_bytes() == before
    archive.write_bytes(b"corrupt ZIP")
    context.window._import_zip_soundboard()
    drain(context)
    assert context.active.read_bytes() == before and not context.window._restart_required
    assert context.messages[-1][0] == "critical"


def test_zip_export_missing_media_is_not_silently_omitted(context, bundle, tmp_path, monkeypatch):
    document, _, _, _ = bundle
    assert logic.save_settings(document)["success"]
    context.window._reload_after_import()
    Path(document["presets"][0]["background_image"]).unlink()
    select_export(monkeypatch, tmp_path / "missing")
    before = context.active.read_bytes()
    context.window._export_soundboard()
    drain(context)
    assert not (tmp_path / "missing.zip").exists()
    assert context.active.read_bytes() == before
    assert context.messages[-1][0] == "critical"


def test_relative_single_file_asks_base_while_pool_uses_settings_folder(context, tmp_path, monkeypatch):
    legacy_folder = tmp_path / "legacy"
    legacy_file = wav(legacy_folder / "single.wav")
    pooled_file = wav(context.active.parent / "pool.wav")
    document = logic.get_preset_settings()
    preset = document["presets"][0]
    preset["buttons"]["paths"][0] = "single.wav"
    preset["buttons"]["paths"][1] = "pool.wav"
    preset["audio_pools"] = {"2": {"audio_pool": ["pool.wav"], "audio_pool_mode": "manual", "selected_audio": "pool.wav"}}
    assert logic.save_settings(document)["success"]
    context.window._reload_after_import()
    folders = iter([str(tmp_path), str(legacy_folder)])
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a: next(folders))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a: ("relative", True))
    before = context.active.read_bytes()
    context.window._export_soundboard()
    drain(context)
    result = media.validate_archive(tmp_path / "relative.zip")
    assert {a.path for a in result.assets} == {"audio/single.wav", "audio/pool.wav"}
    assert context.active.read_bytes() == before


def test_zip_import_save_failure_rolls_back_and_keeps_old_presets(context, bundle, monkeypatch):
    _, archive, _, _ = bundle
    original = media.storage.save_preset_settings

    def fail_commit(path, data, *, expected, before_commit=None):
        if before_commit is not None:
            raise media.storage.PresetStorageError("write", path, "disk failure")
        return original(path, data, expected=expected)

    monkeypatch.setattr(media.storage, "save_preset_settings", fail_commit)
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a: (str(archive), ""))
    context.window._import_zip_soundboard()
    drain(context)
    assert len(logic.settings["presets"]) == 1
    assert not list((context.active.parent / "imported_soundboards").iterdir())
    assert not context.window._restart_required and not context.window._settings_writes_blocked
    assert context.messages[-1][0] == "critical"


def test_zip_operation_prevents_reentry_and_disables_legacy_actions(context, tmp_path, monkeypatch):
    select_export(monkeypatch, tmp_path / "one")
    context.window._export_soundboard()
    assert context.window._package_busy
    assert not context.window.legacy_export_action.isEnabled() and not context.window.legacy_import_action.isEnabled()
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a: pytest.fail("reentrant dialog"))
    context.window._import_zip_soundboard()
    drain(context)
    assert context.window.legacy_export_action.isEnabled() and context.window.legacy_import_action.isEnabled()
