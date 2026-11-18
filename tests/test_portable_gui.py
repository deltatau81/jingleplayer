"""Portable GUI integration, with all filesystem access isolated under tmp_path."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import jingleplayer_gui_pyside6 as gui
import jingleplayer_packages as packages


def settings():
    return {"schema_version": 2, "buttons": {
        "texts": [f"Slot {i}" for i in range(50)], "colors": ["#123456"] * 50,
        "paths": [""] * 50, "volumes": [-3] * 50, "per_row": [2, 0, 0, 0, 0]},
        "fadeout_duration": 123, "button_height": 2,
        "volume": 42, "window_size": [1000, 600], "last_folder": ""}


@pytest.fixture
def context(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    logic = gui.jingleplayer_logic
    # initialize_settings updates these module globals. Restore every one after
    # each test; no real home/settings/audio or application tests are affected.
    names = ("settings", "button_texts", "button_colors", "jingle_paths", "button_volumes",
             "buttons_per_row", "fadeout_duration", "button_height", "set_volume",
             "_loaded_settings_path", "_settings_snapshot", "_original_settings_bytes",
             "_backup_required", "_write_blocked_error", "_source_exists")
    for name in names:
        monkeypatch.setattr(logic, name, deepcopy(getattr(logic, name)))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "fake-home"))
    active = tmp_path / "settings/jingleplayer_settings.json"
    active.parent.mkdir()
    initial = settings()
    initial["last_folder"] = str(tmp_path)
    active.write_text(json.dumps(initial), encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", active)
    playing, stops = [], []
    monkeypatch.setattr(logic, "get_playing_indices", lambda: list(playing))
    monkeypatch.setattr(logic, "check_sound_end", lambda: [])

    def stop(index, duration):
        stops.append((index, duration))
        playing.remove(index)
        return {"indicator_update": {"index": index, "playing": False}}

    monkeypatch.setattr(logic, "stop_jingle", stop)
    messages, questions = [], []
    for kind in ("critical", "information", "warning"):
        monkeypatch.setattr(QMessageBox, kind, lambda parent, title, text, k=kind:
                            messages.append((k, title, text)))

    def question(parent, title, text, *args):
        questions.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("", False))
    window = gui.create_main_window()
    value = SimpleNamespace(app=app, window=window, active=active, initial=initial,
                            messages=messages, questions=questions, playing=playing, stops=stops)
    yield value
    if window._package_job is not None:
        window._package_job.wait(10000)
        for _ in range(10):
            app.processEvents()
    window._package_busy = False
    window._settings_writes_blocked = True
    window.close()
    window.deleteLater()
    app.processEvents()


def drain(context):
    for _ in range(1000):
        context.app.processEvents()
        if not context.window._package_busy:
            return
        time.sleep(0.005)  # Yield the GIL to Python filesystem worker threads.
        QTest.qWait(10)
    pytest.fail("package job did not finish")


def make_package(tmp_path):
    board = settings()
    board["volume"] = 99
    board["window_size"] = [800, 500]
    board["buttons"]["texts"][0] = "Imported"
    board["buttons"]["texts"][49] = "Hidden Unicode 音楽"
    board["buttons"]["colors"][49] = "#abcdef"
    board["buttons"]["volumes"][49] = 7
    sound = tmp_path / "Grüße.MP3"
    sound.write_bytes(b"test audio bytes")
    board["buttons"]["paths"][0] = board["buttons"]["paths"][49] = str(sound)
    package = tmp_path / "package"
    packages.export_package_directory(board, package)
    return package


def select_import(monkeypatch, package):
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a, **k: str(package))


def select_export(monkeypatch, destination, base=None):
    def directory(parent, title):
        if "Basisordner" in title:
            return str(base) if base is not None else ""
        return str(destination.parent)
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", directory)
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: (destination.name, True))


def test_actions_and_export_cancel_unchanged(context):
    window = context.window
    assert window.export_action.text() == "Soundboard exportieren..."
    assert window.import_action.text() == "Soundboard importieren..."
    before = context.active.read_bytes()
    window._export_soundboard()
    assert not window._package_busy
    assert context.active.read_bytes() == before and not context.stops


def test_export_snapshot_all_slots_includes_unsaved_edits(context, tmp_path, monkeypatch):
    calls = []
    gui.jingleplayer_logic.button_texts[49] = "Unsaved hidden"
    select_export(monkeypatch, tmp_path / "new")

    def export(snapshot, destination, *, source_base):
        calls.append((snapshot, destination, source_base, QThread.currentThread()))

    monkeypatch.setattr(packages, "export_package_directory", export)
    before = context.active.read_bytes()
    context.window._export_soundboard()
    drain(context)
    assert len(calls) == 1 and len(calls[0][0]["buttons"]["paths"]) == 50
    assert calls[0][0]["buttons"]["texts"][49] == "Unsaved hidden"
    assert calls[0][3] != context.app.thread()
    assert context.active.read_bytes() == before and not context.stops


@pytest.mark.parametrize("error", [FileExistsError("already exists"), PermissionError("disk full / denied")])
def test_export_errors_leave_runtime_and_disk_unchanged(context, tmp_path, monkeypatch, error):
    select_export(monkeypatch, tmp_path / "new")

    def fail(*a, **k):
        raise error

    monkeypatch.setattr(packages, "export_package_directory", fail)
    before = gui.jingleplayer_logic.get_current_settings()
    context.window._export_soundboard()
    drain(context)
    assert gui.jingleplayer_logic.get_current_settings() == before
    assert context.messages[-1][0] == "critical" and not context.stops


def test_export_relative_paths_request_explicit_base(context, tmp_path, monkeypatch):
    gui.jingleplayer_logic.jingle_paths[49] = "relative.wav"
    chosen_base = tmp_path / "audio"
    chosen_base.mkdir()
    (chosen_base / "relative.wav").write_bytes(b"audio")
    select_export(monkeypatch, tmp_path / "new", chosen_base)
    calls = []
    monkeypatch.setattr(packages, "export_package_directory", lambda *a, **k: calls.append(k))
    context.window._export_soundboard()
    drain(context)
    assert calls == [{"source_base": chosen_base}]


def test_real_gui_export_validated_and_source_unchanged(context, tmp_path, monkeypatch):
    audio = tmp_path / "音楽.WAV"
    audio.write_bytes(b"audio")
    gui.jingleplayer_logic.jingle_paths[49] = str(audio)
    destination = tmp_path / "exported board"
    select_export(monkeypatch, destination)
    original = context.active.read_bytes()
    context.playing.extend([1, 50])
    context.window._export_soundboard()
    drain(context)
    exported = packages.validate_package_directory(destination)
    assert len(exported.settings["buttons"]["paths"]) == 50
    assert exported.settings["buttons"]["paths"][49].startswith("Musik/")
    assert context.active.read_bytes() == original and audio.read_bytes() == b"audio"
    assert context.playing == [1, 50] and not context.stops


def test_relative_base_cancel_does_not_export(context, tmp_path, monkeypatch):
    gui.jingleplayer_logic.jingle_paths[49] = "relative.wav"
    select_export(monkeypatch, tmp_path / "new")
    monkeypatch.setattr(packages, "export_package_directory", lambda *a, **k: pytest.fail("base canceled"))
    context.window._export_soundboard()
    assert not context.window._package_busy


def test_import_selection_cancel_no_side_effects(context):
    context.playing.extend([1, 50])
    before = context.active.read_bytes()
    context.window._import_soundboard()
    assert context.active.read_bytes() == before and not context.stops
    assert not context.window._package_busy


def test_invalid_package_no_confirmation_or_playback_stop(context, tmp_path, monkeypatch):
    select_import(monkeypatch, tmp_path)
    context.window._import_soundboard()
    drain(context)
    assert not context.questions and not context.stops
    assert "Ungültiges" in context.messages[-1][1]


def test_import_preview_cancel_no_preparation_or_playback_change(context, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    monkeypatch.setattr(packages, "prepare_package_import", lambda *a: pytest.fail("must not prepare"))
    context.playing.append(1)
    before = context.active.read_bytes()
    context.window._import_soundboard()
    drain(context)
    assert context.active.read_bytes() == before and context.playing == [1]
    assert not context.stops and not context.messages


def test_real_import_reload_close_and_hidden_slots(context, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    activate = packages.activate_prepared_import
    calls = []

    def once(*args):
        calls.append(args)
        return activate(*args)

    monkeypatch.setattr(packages, "activate_prepared_import", once)
    context.playing.extend([1, 50])
    old_size = (context.window.width(), context.window.height())
    context.window._import_soundboard()
    drain(context)
    assert len(calls) == 1 and context.stops == [(1, 0), (50, 0)]
    assert "1 Audiodateien" in context.questions[0] and "2 zugewiesene Tasten" in context.questions[0]
    assert "Fenstergröße und Gesamtlautstärke" in context.questions[0]
    window = context.window
    assert window.jingle_texts[0] == "Imported" and window.jingle_texts[49] == "Hidden Unicode 音楽"
    assert len(window.jingle_paths) == 50 and window.jingle_paths[0] == window.jingle_paths[49]
    assert all(not tile.playing for tile in window.jingle_tiles)
    assert window.jingle_volumes == [-3] * 49 + [7]
    assert window.jingle_colors[49] == "#abcdef"
    assert window.last_folder == context.initial["last_folder"]
    assert window.jingle_tiles[0].jingle_text == "Imported"
    assert window.volume_slider.value() == 42 and window.volume_value_label.text() == "42 %"
    assert (window.width(), window.height()) == old_size
    assert not window._settings_writes_blocked and window.sound_end_timer.isActive()
    # Force the existing close-save path to prove it uses imported runtime data.
    window.resize(window.width() + 10, window.height() + 10)
    window.close()
    disk = json.loads(context.active.read_bytes())
    assert disk["buttons"]["texts"][49] == "Hidden Unicode 音楽"
    assert Path(disk["buttons"]["paths"][49]).is_relative_to(context.active.parent / "library")
    assert disk["volume"] == 42
    assert disk["last_folder"] == context.initial["last_folder"]
    assert disk["buttons"]["volumes"][49] == 7
    assert Path(calls[0][0].preparation_directory).exists()  # Retain; no public cleanup API.


@pytest.mark.parametrize("outcome", ["not_committed", "committed", "indeterminate"])
def test_activation_outcomes_and_stale_save_protection(context, tmp_path, monkeypatch, outcome):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    real_activate = packages.activate_prepared_import

    def fail(*args):
        recovery = tmp_path / "recovery-report"
        if outcome == "committed":
            real_activate(*args)
        raise packages.ActivationError("injected", outcome=outcome, recovery_directory=recovery,
                                       installed_directory=None, retained_paths=[recovery])

    monkeypatch.setattr(packages, "activate_prepared_import", fail)
    context.window._import_soundboard()
    drain(context)
    text = context.messages[-1][2]
    assert "recovery-report" in text
    if outcome == "indeterminate":
        assert context.window._restart_required and context.window._settings_writes_blocked
        monkeypatch.setattr(gui.jingleplayer_logic, "save_settings", lambda *a: pytest.fail("stale write"))
        context.window.resize(1200, 700)
        context.window.close()
        assert "keine automatische Wiederherstellung" in text
    elif outcome == "committed":
        assert context.messages[-1][1] == "Soundboard importiert"
        assert context.window.jingle_texts[0] == "Imported"
    else:
        assert context.messages[-1][1] == "Import nicht aktiviert"
        assert context.window.jingle_texts[0] == "Slot 0"


def test_committed_reload_failure_locks_saves_and_close(context, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)

    def reload_failure():
        raise RuntimeError("reload failure")

    monkeypatch.setattr(context.window, "_reload_after_import", reload_failure)
    context.window._import_soundboard()
    drain(context)
    assert "auf dem Datenträger aktiviert" in context.messages[-1][2]
    assert context.window._restart_required and not context.window.sound_end_timer.isActive()
    monkeypatch.setattr(gui.jingleplayer_logic, "save_settings", lambda *a: pytest.fail("stale save"))
    context.window.resize(1200, 700)
    context.window.close()
    assert json.loads(context.active.read_bytes())["buttons"]["texts"][0] == "Imported"


def test_busy_guards_reentrant_mutation_and_close(context, monkeypatch):
    window = context.window
    assert window._begin_package_operation()
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a, **k: pytest.fail("reentrant"))
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: pytest.fail("reentrant"))
    before = gui.jingleplayer_logic.get_current_settings()
    window._import_soundboard()
    window._export_soundboard()
    window._open_settings_dialog()
    window._open_jingle_editor(1)
    window._handle_volume_change(7)
    window._save_application_settings(7, [10] * 5, 3)
    window._handle_tile_click(1)
    assert not window._save_settings_with_feedback(before, "test")
    from PySide6.QtGui import QCloseEvent
    close = QCloseEvent()
    window.closeEvent(close)
    assert not close.isAccepted()
    assert gui.jingleplayer_logic.get_current_settings() == before
    window._finish_package_operation()


def test_visible_editor_blocks_operations(context):
    dialog = QDialog(context.window)
    dialog.show()
    context.window._export_soundboard()
    assert not context.window._package_busy
    dialog.reject()


def test_package_changes_after_preview_no_activation_or_playback_stop(context, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    prepare = packages.prepare_package_import

    def changed(*args):
        prepared = prepare(*args)
        prepared.source_package.settings["buttons"]["texts"][49] = "different board"
        return prepared

    monkeypatch.setattr(packages, "prepare_package_import", changed)
    monkeypatch.setattr(packages, "activate_prepared_import", lambda *a: pytest.fail("preview changed"))
    context.window._import_soundboard()
    drain(context)
    assert not context.stops
    assert "nach der Vorschau verändert" in context.messages[-1][2]


def test_job_keeps_event_loop_responsive_and_completion_on_gui_thread(context):
    import threading
    from PySide6.QtCore import QTimer
    release = threading.Event()
    callbacks = []
    ticks = []
    timer = QTimer(context.window)
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    assert context.window._begin_package_operation()

    def work():
        release.wait(2)
        return QThread.currentThread()

    def done(result, error):
        callbacks.append((result, QThread.currentThread(), error))
        context.window._finish_package_operation()

    context.window._run_package_job("Test", work, done)
    for _ in range(10):
        context.app.processEvents()
        time.sleep(0.01)
    assert ticks and context.window._package_busy
    release.set()
    drain(context)
    timer.stop()
    assert callbacks[0][0] != context.app.thread()
    assert callbacks[0][1] == context.app.thread() and callbacks[0][2] is None


def test_playback_stop_failure_prevents_activation(context, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    context.playing.append(50)
    monkeypatch.setattr(gui.jingleplayer_logic, "stop_jingle", lambda *a: {})
    monkeypatch.setattr(packages, "activate_prepared_import", lambda *a: pytest.fail("audio still playing"))
    original = context.active.read_bytes()
    context.window._import_soundboard()
    drain(context)
    assert context.active.read_bytes() == original
    assert context.messages[-1][1] == "Import nicht aktiviert"
    assert context.window.sound_end_timer.isActive()


@pytest.mark.parametrize("name", ["", " ", ".", "..", "../escape", "a/b", "a\\b", "C:board",
                                  "CON", "nul.wav", "COM1", "LPT²", "CLOCK$", "CONIN$", "CONOUT$", "a.", "a ", "a?", "a*",
                                  'a"', "a<", "a>", "a|", "a\0", "a\n"])
def test_export_invalid_package_names(context, tmp_path, monkeypatch, name):
    select_export(monkeypatch, tmp_path / "new")
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: (name, True))
    monkeypatch.setattr(packages, "export_package_directory", lambda *a, **k: pytest.fail("invalid destination"))
    original = context.active.read_bytes()
    context.window._export_soundboard()
    assert not context.window._package_busy
    assert context.active.read_bytes() == original
    assert "Ungültiger Paketname" in context.messages[-1][2]


def test_export_existing_destination_is_preserved(context, tmp_path, monkeypatch):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep").write_bytes(b"keep")
    select_export(monkeypatch, target)
    context.window._export_soundboard()
    assert (target / "keep").read_bytes() == b"keep"
    assert "existiert bereits" in context.messages[-1][2]
    assert not context.window._package_busy


def test_export_package_name_cancel_does_not_preflight(context, tmp_path, monkeypatch):
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a: ("typed name", False))
    monkeypatch.setattr(context.window, "_preflight_export", lambda *a: pytest.fail("name canceled"))
    original = gui.jingleplayer_logic.get_current_settings()
    context.window._export_soundboard()
    assert not context.window._package_busy
    assert gui.jingleplayer_logic.get_current_settings() == original


@pytest.mark.parametrize("proceed,fail_backend", [(False, False), (True, False), (True, True)])
def test_missing_visible_and_hidden_assignments_only_cleared_in_export_snapshot(
        context, tmp_path, monkeypatch, proceed, fail_backend):
    missing = tmp_path / "Missing 音楽.wav"
    valid = tmp_path / "valid.wav"
    valid.write_bytes(b"audio")
    logic = gui.jingleplayer_logic
    logic.jingle_paths[0] = logic.jingle_paths[49] = str(missing)
    logic.jingle_paths[1] = str(valid)
    before = logic.get_current_settings()
    disk_before = context.active.read_bytes()
    target = tmp_path / "Board 音楽"
    select_export(monkeypatch, target)
    warnings = []

    def confirm(values):
        warnings.append(values)
        return proceed

    monkeypatch.setattr(context.window, "_confirm_missing_export", confirm)
    if fail_backend:
        def fail(*a, **k):
            raise PermissionError("no space / permission denied")
        monkeypatch.setattr(packages, "export_package_directory", fail)
    context.window._export_soundboard()
    drain(context)
    assert len(warnings) == 1 and set(warnings[0]) == {0, 49}
    assert "Taste 1: Slot 0" in warnings[0][0]
    assert "Taste 50: Slot 49" in warnings[0][49]
    assert str(missing) in warnings[0][49]
    assert logic.get_current_settings() == before
    assert context.active.read_bytes() == disk_before and not context.stops
    if proceed and not fail_backend:
        exported = packages.validate_package_directory(target)
        expected = deepcopy(before)
        expected.pop("last_folder")
        expected["buttons"]["paths"][0] = expected["buttons"]["paths"][49] = ""
        expected["buttons"]["paths"][1] = exported.settings["buttons"]["paths"][1]
        assert exported.settings == expected
        assert len(exported.assets) == 1
        assert (target / exported.assets[0].path).read_bytes() == b"audio"
        assert str(target) in context.messages[-1][2]
    else:
        assert not target.exists()


@pytest.mark.parametrize("problem", ["unreadable", "directory", "unsupported", "backend_rejects"])
def test_existing_problematic_files_never_offered_for_omission(context, tmp_path, monkeypatch, problem):
    audio = tmp_path / ("audio.ogg" if problem == "unsupported" else "audio.wav")
    if problem == "directory":
        audio.mkdir()
    else:
        audio.write_bytes(b"existing bytes")
    gui.jingleplayer_logic.jingle_paths[49] = str(audio)
    select_export(monkeypatch, tmp_path / "new")
    monkeypatch.setattr(context.window, "_confirm_missing_export", lambda *a: pytest.fail("not a missing file"))
    if problem == "unreadable":
        real_open = gui.os.open

        def denied(path, *args, **kwargs):
            if Path(path) == audio:
                raise PermissionError("not readable")
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(gui.os, "open", denied)
    if problem == "backend_rejects":
        def invalid(*a, **k):
            raise packages.PackageValidationError("integrity", str(audio), "invalid/corrupt asset")
        monkeypatch.setattr(packages, "export_package_directory", invalid)
    original = gui.jingleplayer_logic.get_current_settings()
    context.window._export_soundboard()
    drain(context)
    assert gui.jingleplayer_logic.get_current_settings() == original
    assert context.messages[-1][0] == "critical"
    assert str(audio) in context.messages[-1][2]


def test_missing_warning_defaults_to_cancel_and_lists_assignments(context, monkeypatch):
    observed = []

    def cancel(box):
        observed.append((box.text(), box.informativeText(), box.defaultButton().text(),
                         [b.text() for b in box.buttons()]))
        box.defaultButton().click()

    monkeypatch.setattr(QMessageBox, "exec", cancel)
    assert not context.window._confirm_missing_export({49: "Taste 50: Hidden\n/missing.wav"})
    assert "Taste 50: Hidden" in observed[0][0] and "/missing.wav" in observed[0][0]
    assert "Tasteneinstellungen" in observed[0][1]
    assert observed[0][2] == "Export abbrechen"
    assert "Ohne fehlende Dateien exportieren" in observed[0][3]


def test_relative_missing_preflight_uses_selected_base(context, tmp_path, monkeypatch):
    gui.jingleplayer_logic.jingle_paths[49] = "missing.wav"
    base = tmp_path / "explicit base"
    base.mkdir()
    select_export(monkeypatch, tmp_path / "new", base)
    captured = []
    monkeypatch.setattr(context.window, "_confirm_missing_export", lambda missing: captured.append(missing) or True)
    context.window._export_soundboard()
    drain(context)
    assert set(captured[0]) == {49}
    assert str(base / "missing.wav") in captured[0][49]
    assert packages.validate_package_directory(tmp_path / "new").assets == ()


def test_source_removed_after_preflight_is_not_silently_omitted(context, tmp_path, monkeypatch):
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    gui.jingleplayer_logic.jingle_paths[49] = str(source)
    destination = tmp_path / "new"
    select_export(monkeypatch, destination)
    export = packages.export_package_directory

    def disappeared(*args, **kwargs):
        source.unlink()
        return export(*args, **kwargs)

    monkeypatch.setattr(packages, "export_package_directory", disappeared)
    monkeypatch.setattr(context.window, "_confirm_missing_export", lambda *a: pytest.fail("missing after preflight"))
    context.window._export_soundboard()
    drain(context)
    assert not destination.exists()
    assert gui.jingleplayer_logic.jingle_paths[49] == str(source)
    assert context.messages[-1][0] == "critical"


def test_missing_and_unreadable_assignments_together_block_omission(context, tmp_path, monkeypatch):
    missing = tmp_path / "missing.wav"
    unreadable = tmp_path / "unreadable.wav"
    unreadable.write_bytes(b"audio")
    gui.jingleplayer_logic.jingle_paths[0] = str(missing)
    gui.jingleplayer_logic.jingle_paths[49] = str(unreadable)
    before = gui.jingleplayer_logic.get_current_settings()
    active_bytes = context.active.read_bytes()
    select_export(monkeypatch, tmp_path / "new")
    real_open = gui.os.open

    def denied(path, *args, **kwargs):
        if Path(path) == unreadable:
            raise PermissionError("explicit access denial")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(gui.os, "open", denied)
    monkeypatch.setattr(context.window, "_confirm_missing_export", lambda *a: pytest.fail("blocked file present"))
    monkeypatch.setattr(packages, "export_package_directory", lambda *a, **k: pytest.fail("must not export"))
    context.window._export_soundboard()
    drain(context)
    assert context.messages[-1][0] == "critical"
    assert str(missing) in context.messages[-1][2] and str(unreadable) in context.messages[-1][2]
    assert gui.jingleplayer_logic.get_current_settings() == before
    assert context.active.read_bytes() == active_bytes
