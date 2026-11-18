from copy import deepcopy
import json

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QImage, QColor

import jingleplayer_gui_pyside6 as gui
import jingleplayer_logic as logic
import jingleplayer_presets as presets
from jingleplayer_audio_pools import PoolSelector
from test_portable_gui import context, make_package, select_import, drain


@pytest.fixture
def board(context, monkeypatch):
    monkeypatch.setattr(logic, "playing_channels", {})
    monkeypatch.setattr(logic, "_pool_selector", PoolSelector())
    yield context
    assert QThreadPool.globalInstance().waitForDone(10000)
    context.app.processEvents()


def paths(tmp_path):
    result = []
    for directory in ("first", "second", "third"):
        path = tmp_path / directory / "same.wav"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"fake audio")
        result.append(str(path))
    return result


def save_pool(board, files, mode="sequential", index=1):
    config = {"audio_pool": files, "audio_pool_mode": mode, "selected_audio": files[0]}
    values = {"pool": config, "path": "", "text": "Pool", "color": "#2468ac",
              "volume_db": -4, "selected_folder": None}
    board.window._save_pool_editor(index, values)
    return values


def active():
    data = logic.get_preset_settings()
    return data["presets"][presets._preset_index(data, data["active_preset_id"])]


def test_dialog_add_remove_reorder_clear_and_mode(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    dialog = gui.JingleEditDialog("A", "red", files[0], 0, str(tmp_path), board.window)
    editor = dialog.pool_editor
    assert editor.source_type.currentText() == "Einzeldatei"
    editor.source_type.setCurrentIndex(1)
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileNames", lambda *a: (files + [files[0]], ""))
    editor.add_files()
    assert editor.paths() == files
    editor.files.setCurrentRow(2)
    editor.mode.setCurrentIndex(editor.mode.findData("manual"))
    editor.move_file(-1)
    assert editor.paths() == [files[0], files[2], files[1]]
    assert editor.value()["selected_audio"] == files[2]
    editor.remove_file()
    assert editor.value()["selected_audio"] == files[1]
    assert editor.paths() == [files[0], files[1]]
    editor.clear_files()
    assert dialog.get_values()["pool"] is None and dialog.get_values()["path"] == ""
    dialog.reject()


def test_async_missing_marker_and_dialog_cancel_leave_settings_unchanged(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    missing = str(tmp_path / "missing.wav")
    before = board.active.read_bytes()
    dialog = gui.JingleEditDialog("A", "red", "", 0, "", board.window)
    dialog.pool_editor.configure({"audio_pool": [files[0], missing], "audio_pool_mode": "manual", "selected_audio": missing})
    assert QThreadPool.globalInstance().waitForDone(10000)
    board.app.processEvents()
    assert "fehlt" in dialog.pool_editor.files.item(1).text()
    dialog.reject()
    monkeypatch.setattr(gui.JingleEditDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    board.window._open_jingle_editor(1)
    assert board.active.read_bytes() == before


def test_existing_pool_loads_in_real_editor_and_accepted_reorder_is_saved(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    save_pool(board, files, "manual")

    def edit(dialog):
        assert dialog.pool_editor.paths() == files
        assert dialog.pool_editor.mode.currentData() == "manual"
        assert not dialog.path_edit.isEnabled()
        dialog.pool_editor.files.setCurrentRow(2)
        dialog.pool_editor.move_file(-1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(gui.JingleEditDialog, "exec", edit)
    board.window._open_jingle_editor(1)
    assert active()["audio_pools"]["1"]["audio_pool"] == [files[0], files[2], files[1]]
    assert board.window.jingle_tiles[0].pool_combo.currentData() == files[2]


def test_manual_pool_keeps_transparent_background_and_resize(board, tmp_path):
    save_pool(board, paths(tmp_path), "manual")
    image = QImage(120, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    path = tmp_path / "background.png"
    assert image.save(str(path))
    data = logic.get_preset_settings()
    data["presets"][0]["background_image"] = str(path)
    assert logic.save_settings(data)["success"]
    board.window._reload_after_import()
    board.window.show()
    for width, height in ((1100, 700), (850, 600)):
        board.window.resize(width, height)
        board.app.processEvents()
        canvas = board.window.background_canvas
        tile = board.window.jingle_tiles[0]
        assert tile.pool_combo.count() == 3 and tile.pool_combo.isVisible()
        rendered = canvas.grab().toImage()
        origin = tile.mapTo(canvas, tile.rect().topLeft())
        ratio = canvas.devicePixelRatioF()
        pixel = rendered.pixelColor(round((origin.x() + 10) * ratio), round((origin.y() + 10) * ratio))
        for actual, expected in zip(pixel.getRgb()[:3], (5, 6, 173)):
            assert abs(actual - expected) <= 2
        assert canvas._scaled.size() == canvas.size() * ratio


def test_long_manual_paths_do_not_force_wide_tiles(board, tmp_path):
    files = [str(tmp_path / ("long-directory-" * 40) / name) for name in ("a.wav", "b.wav")]
    save_pool(board, files, "manual")
    combo = board.window.jingle_tiles[0].pool_combo
    assert combo.sizeHint().width() < 200
    assert combo.itemData(1, gui.Qt.ItemDataRole.ToolTipRole) == files[1]


@pytest.mark.parametrize("mode", ["sequential", "random", "manual"])
def test_save_restart_duplicate_switch_hidden_slots_and_globals(board, tmp_path, mode):
    files = paths(tmp_path)
    original_id = logic.get_preset_settings()["active_preset_id"]
    globals_before = {k: logic.get_preset_settings()[k] for k in ("window_size", "volume", "last_folder")}
    save_pool(board, files, mode)
    # Hidden slot: same transactional path, even though no visible tile exists.
    data = logic.get_preset_settings()
    data["presets"][0]["audio_pools"]["50"] = deepcopy(data["presets"][0]["audio_pools"]["1"])
    data["presets"][0]["buttons"]["paths"][49] = files[0]
    assert logic.save_settings(data)["success"]
    logic.initialize_settings()
    assert active()["audio_pools"]["50"]["audio_pool"] == files
    assert {k: logic.get_preset_settings()[k] for k in globals_before} == globals_before
    assert logic.manage_presets("duplicate", original_id, "Copy", activate=True)["success"]
    assert active()["audio_pools"]["1"]["audio_pool"] == files
    assert logic.manage_presets("rename", logic.settings["active_preset_id"], "Renamed")["success"]
    assert active()["audio_pools"]["50"]["audio_pool"] == files
    assert logic.manage_presets("switch", original_id)["success"]
    board.window._reload_after_import()
    assert len(logic.get_current_settings()["buttons"]["paths"]) == 50
    assert bool(getattr(board.window.jingle_tiles[0], "pool_combo", None)) == (mode == "manual")


def test_manual_selection_persists_without_start_and_button_starts_selected(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    save_pool(board, files, "manual")
    combo = board.window.jingle_tiles[0].pool_combo
    calls = []
    monkeypatch.setattr(logic, "play_jingle", lambda index, path, duration:
                        calls.append(path) or {"success": True, "indicator_update": {"playing": True}})
    assert combo.itemText(0) != combo.itemText(1)  # same basename, different directories
    combo.setCurrentIndex(2)
    assert not calls
    assert active()["audio_pools"]["1"]["selected_audio"] == files[2]
    assert json.loads(board.active.read_bytes())["presets"][0]["audio_pools"]["1"]["selected_audio"] == files[2]
    board.window._handle_tile_click(1)
    assert calls == [files[2]] and board.window.jingle_tiles[0].playing
    combo.setCurrentIndex(1)
    assert calls == [files[2]] and board.window.jingle_tiles[0].playing
    logic.initialize_settings()
    board.window._reload_after_import()
    assert board.window.jingle_tiles[0].pool_combo.currentData() == files[1]


def test_failed_save_and_failed_manual_selection_leave_document_and_gui_unchanged(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    save_pool(board, files, "manual")
    before, original_bytes = logic.get_preset_settings(), board.active.read_bytes()
    combo = board.window.jingle_tiles[0].pool_combo
    monkeypatch.setattr(logic, "save_settings", lambda *a: {"success": False, "error": "disk denied"})
    combo.setCurrentIndex(1)
    assert combo.currentIndex() == 0
    save_pool(board, files[::-1], "random")
    assert logic.get_preset_settings() == before and board.active.read_bytes() == original_bytes
    assert board.window.jingle_paths[0] == files[0]


def test_export_multi_pool_blocked_before_chooser_including_hidden_slot(board, tmp_path, monkeypatch):
    files = paths(tmp_path)
    data = logic.get_preset_settings()
    config = {"audio_pool": files, "audio_pool_mode": "random", "selected_audio": files[0]}
    data["presets"][0]["audio_pools"] = {"50": config}
    data["presets"][0]["buttons"]["paths"][49] = files[0]
    assert logic.save_settings(data)["success"]
    logic.initialize_settings()
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a: pytest.fail("lossy export reached chooser"))
    before = board.active.read_bytes()
    board.window._export_soundboard()
    assert not board.window._package_busy and board.active.read_bytes() == before
    assert "18D" in board.messages[-1][2]


@pytest.mark.parametrize("mode", ["replace", "new"])
def test_old_package_import_clears_only_replaced_pool(board, tmp_path, monkeypatch, mode):
    files = paths(tmp_path)
    save_pool(board, files)
    original_id = logic.settings["active_preset_id"]
    package = make_package(tmp_path)
    monkeypatch.setattr(gui.QInputDialog, "getItem", lambda *a, **k: (
        "Als neues Preset" if mode == "new" else "Aktives Preset ersetzen", True))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("Imported", True))
    select_import(monkeypatch, package)
    board.window._import_soundboard()
    drain(board)
    assert "audio_pools" not in active()
    if mode == "new":
        source = next(p for p in logic.settings["presets"] if p["id"] == original_id)
        assert source["audio_pools"]["1"]["audio_pool"] == files
