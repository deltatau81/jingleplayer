"""Application integration; all paths/widgets are isolated by the GUI fixture."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

import jingleplayer_logic as logic
import jingleplayer_packages as packages
import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage
from test_portable_gui import context, make_package, select_import, select_export, drain

REAL_STOP_ALL = logic.stop_all_playback


def test_gui_crud_switch_and_restart(context, monkeypatch):
    window = context.window
    original_id = logic.get_preset_settings()["active_preset_id"]
    assert window.preset_combo.count() == 1
    names = iter(["Neu", "Kopie", "Umbenannt"])
    monkeypatch.setattr(__import__("jingleplayer_gui_pyside6").QInputDialog, "getText", lambda *a, **k: (next(names), True))
    window._manage_preset("create")
    assert window.preset_combo.currentText() == "Neu"
    assert logic.get_current_settings()["buttons"]["paths"] == [""] * 50
    logic.jingle_paths[49] = "hidden.wav"
    logic.button_volumes[49] = 7
    window._manage_preset("duplicate")
    assert window.preset_combo.count() == 3 and window.preset_combo.currentText() == "Kopie"
    assert window.jingle_paths[49] == "hidden.wav" and window.jingle_volumes[49] == 7
    window._manage_preset("rename")
    assert window.preset_combo.currentText() == "Umbenannt"
    selected = window.preset_combo.currentData()
    logic.initialize_settings()
    assert logic.get_preset_settings()["active_preset_id"] == selected
    window.preset_combo.setCurrentIndex(window.preset_combo.findData(original_id))
    assert logic.get_preset_settings()["active_preset_id"] == original_id
    assert window.jingle_paths[49] == ""
    import jingleplayer_gui_pyside6 as gui
    monkeypatch.setattr(gui.QInputDialog, "getItem", lambda *a, **k: ("Neu", True))
    window._manage_preset("delete")
    assert window.preset_combo.count() == 2 and window.preset_combo.currentText() == "Neu"
    disk = json.loads(context.active.read_bytes())
    assert disk["schema_version"] == 3 and len(disk["presets"]) == 2
    assert disk["volume"] == context.initial["volume"]


def test_last_preset_and_name_error_keep_gui_and_disk(context, monkeypatch):
    import jingleplayer_gui_pyside6 as gui
    before = context.active.read_bytes()
    context.window._manage_preset("delete")
    assert context.active.read_bytes() == before
    assert "letzte" in context.messages[-1][2]
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("STANDARD", True))
    context.window._manage_preset("create")
    assert context.window.preset_combo.count() == 1
    assert len(logic.get_preset_settings()["presets"]) == 1
    assert logic.get_preset_settings()["presets"][0]["name"] == "Standard"


@pytest.mark.parametrize("mode", ["new", "replace"])
def test_gui_import_keeps_other_presets_and_export_is_active_only(context, tmp_path, monkeypatch, mode):
    import jingleplayer_gui_pyside6 as gui
    assert logic.manage_presets("create", "Other", activate=False)["success"]
    original = deepcopy(logic.get_preset_settings())
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    monkeypatch.setattr(gui.QInputDialog, "getItem", lambda *a, **k:
                        ("Als neues Preset" if mode == "new" else "Aktives Preset ersetzen", True))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("Imported", True))
    context.window._import_soundboard()
    drain(context)
    document = logic.get_preset_settings()
    assert len(document["presets"]) == (3 if mode == "new" else 2)
    assert document["presets"][1] == original["presets"][1]
    if mode == "new":
        assert document["presets"][:2] == original["presets"]
    assert context.window.jingle_texts[0] == "Imported"
    destination = tmp_path / "reexport"
    select_export(monkeypatch, destination)
    context.window._export_legacy_soundboard()
    drain(context)
    exported = packages.validate_package_directory(destination)
    assert exported.settings["schema_version"] == 2
    assert "presets" not in exported.settings
    assert exported.settings["buttons"]["texts"][0] == "Imported"
    assert len(exported.settings["buttons"]["paths"]) == 50


def test_stale_runtime_save_does_not_overwrite_other_instance(context):
    first = storage.load_preset_settings(context.active)
    changed = presets.create_preset(first.data, "Another instance")
    storage.save_preset_settings(context.active, changed, expected=first)
    external = context.active.read_bytes()
    logic.button_texts[49] = "local unsaved"
    result = logic.save_settings(logic.get_current_settings())
    assert not result["success"] and context.active.read_bytes() == external


def test_indeterminate_save_blocks_automatic_retry_and_close(context, monkeypatch):
    def fail(*args, **kwargs):
        raise storage.PresetStorageError("write", context.active, "unclear", outcome="indeterminate")
    monkeypatch.setattr(storage, "save_preset_settings", fail)
    logic.button_texts[49] = "unsaved"
    context.window._handle_volume_change(17)
    assert logic.get_settings_persistence_status()["write_blocked"]
    assert context.window._settings_writes_blocked
    monkeypatch.setattr(storage, "save_preset_settings", lambda *a, **k: pytest.fail("automatic retry"))
    context.window.resize(1200, 800)
    context.window.close()


def test_switch_failure_keeps_preset_and_input_data(context, monkeypatch):
    assert logic.manage_presets("create", "Other", activate=False)["success"]
    before = logic.get_preset_settings()
    target = before["presets"][1]["id"]
    original_save = storage.save_preset_settings

    def deny(path, data, **kwargs):
        if data["active_preset_id"] == target:
            raise storage.PresetStorageError("write", path, "denied")
        return original_save(path, data, **kwargs)

    monkeypatch.setattr(storage, "save_preset_settings", deny)
    assert not logic.manage_presets("switch", target)["success"]
    assert logic.get_preset_settings() == before
    assert json.loads(context.active.read_bytes()) == before


def test_stop_all_stops_untracked_fades_and_retires_events(audio, monkeypatch):
    channel = audio.channel(1)
    audio.mixer.channels = [channel]
    channel.busy = True
    channel.endevent = 1010
    channel.get_endevent = lambda: channel.endevent
    cleared = []
    monkeypatch.setattr(logic.pygame.event, "clear", lambda ids: cleared.extend(ids), raising=False)
    # The channel has already been released from button tracking by a fadeout.
    logic._next_end_event = 1011
    logic.stop_all_playback()
    assert channel.stop_calls == 1 and not channel.busy and channel.endevent == 0
    assert cleared == [1010]
    assert not logic.playing_channels and not logic._events_by_button and not logic._playbacks_by_event
    assert logic._next_end_event == 1011


def test_failed_commit_guard_cleans_temp_and_preserves_original(tmp_path):
    path = tmp_path / "settings.json"
    loaded = storage.load_preset_settings(path, initialize=True, initial_settings=logic._default_settings())
    def guard():
        raise ValueError("installed asset changed")
    with pytest.raises(storage.PresetStorageError):
        storage.save_preset_settings(path, loaded.data, expected=loaded, before_commit=guard)
    assert not path.exists() and not list(tmp_path.glob("*.tmp"))


def test_switch_stops_tracked_and_untracked_fading_channels(context, audio, monkeypatch):
    monkeypatch.setattr(logic, "stop_all_playback", REAL_STOP_ALL)
    tracked, fading = audio.channel(1), audio.channel(50)
    tracked.busy = fading.busy = True
    audio.mixer.channels = [tracked, fading]
    logic.playing_channels[1] = tracked
    logic._events_by_button[1] = 1011
    logic._playbacks_by_event[1011] = (1, tracked)
    logic._issued_end_events.update([1010, 1011])
    cleared = []
    monkeypatch.setattr(logic.pygame.event, "clear", lambda ids: cleared.extend(ids), raising=False)
    result = logic.manage_presets("create", "Next", activate=True)
    assert result["success"]
    assert not tracked.busy and not fading.busy
    assert tracked.stop_calls >= 1 and fading.stop_calls == 1
    assert set(cleared) == {1010, 1011}
    assert not logic.playing_channels and not logic._playbacks_by_event and not logic._events_by_button


def test_preset_commit_reload_failure_prevents_close_save(context, monkeypatch):
    import jingleplayer_gui_pyside6 as gui
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("Committed", True))
    monkeypatch.setattr(context.window, "_reload_after_import", lambda: (_ for _ in ()).throw(RuntimeError("reload failed")))
    context.window._manage_preset("create")
    assert context.window._restart_required and context.window._settings_writes_blocked
    assert not context.window.sound_end_timer.isActive()
    assert "gespeichert" in context.messages[-1][2]
    before = context.active.read_bytes()
    monkeypatch.setattr(logic, "save_settings", lambda *a: pytest.fail("stale close save"))
    context.window.resize(1300, 800)
    context.window.close()
    assert context.active.read_bytes() == before


def test_import_copy_failure_preserves_entire_multi_preset_document(context, tmp_path, monkeypatch):
    assert logic.manage_presets("create", "Other", activate=False)["success"]
    before = context.active.read_bytes()
    document = logic.get_preset_settings()
    source = make_package(tmp_path)
    staging, library, recovery = (tmp_path / name for name in ("staging", "library", "recovery"))
    for path in (staging, library, recovery):
        path.mkdir()
    prepared = packages.prepare_package_import(source, staging)
    monkeypatch.setattr(packages, "_copy_asset", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(packages.ActivationError) as caught:
        packages.activate_prepared_import(prepared, context.active, library, recovery,
                                         preset_mode="new", preset_name="Imported",
                                         expected=logic.get_settings_storage_token())
    assert caught.value.outcome == "not_committed"
    assert context.active.read_bytes() == before and logic.get_preset_settings() == document
    assert (caught.value.recovery_directory / packages.SETTINGS_NAME).read_bytes() == before


def test_uppercase_active_uuid_load_save_and_selector(context):
    token = storage.load_preset_settings(context.active)
    data = deepcopy(token.data)
    data["active_preset_id"] = data["active_preset_id"].upper()
    storage.save_preset_settings(context.active, data, expected=token)
    context.window._reload_after_import()
    assert context.window.preset_combo.currentText() == "Standard"
    logic.button_texts[49] = "Updated"
    assert logic.save_settings(logic.get_current_settings())["success"]
    assert presets.extract_active_board(json.loads(context.active.read_bytes()))["buttons"]["texts"][49] == "Updated"


def test_first_save_conflict_does_not_refresh_token_for_automatic_retry(context, tmp_path, monkeypatch):
    path = tmp_path / "new-parent/settings.json"
    monkeypatch.setattr(logic, "settings_file", path)
    logic.initialize_settings()
    assert logic._preset_token is None
    path.parent.mkdir()
    external = presets.create_preset(logic.get_preset_settings(), "External")
    raw = json.dumps(external).encode()
    path.write_bytes(raw)
    for _ in range(2):
        assert not logic.save_settings(logic.get_current_settings())["success"]
        assert path.read_bytes() == raw and logic._preset_token is None
