import os
from copy import deepcopy

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame  # noqa: E402

import jingleplayer_gui_pyside6 as gui  # noqa: E402


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def isolated_settings(monkeypatch):
    settings = {
        "buttons": {
            "texts": ["A", "B"],
            "colors": ["red", "blue"],
            "paths": ["a.wav", "b.mp3"],
            "volumes": [-3, 4],
            "per_row": [2, 0, 0, 0, 0],
        },
        "fadeout_duration": 750,
        "button_height": 3,
        "window_size": [1153, 509],
        "volume": 65,
        "last_folder": "C:/Jingles",
    }
    initialize_calls = []
    saved_settings = []

    monkeypatch.setattr(gui.jingleplayer_logic, "initialize_settings", lambda: initialize_calls.append(True))
    monkeypatch.setattr(gui.jingleplayer_logic, "get_current_settings", lambda: deepcopy(settings))
    monkeypatch.setattr(gui.jingleplayer_logic, "save_settings", lambda value: saved_settings.append(deepcopy(value)))
    monkeypatch.setattr(gui.jingleplayer_logic, "check_sound_end", lambda: [])

    return settings, initialize_calls, saved_settings


@pytest.fixture
def mocked_audio(monkeypatch):
    play_calls = []
    stop_calls = []

    def play(index, path, fadeout_duration):
        play_calls.append((index, path, fadeout_duration))
        return {"indicator_update": {"index": index, "playing": True}, "success": True}

    def stop(index, fadeout_duration):
        stop_calls.append((index, fadeout_duration))
        return {"indicator_update": {"index": index, "playing": False}}

    monkeypatch.setattr(gui.jingleplayer_logic, "play_jingle", play)
    monkeypatch.setattr(gui.jingleplayer_logic, "stop_jingle", stop)
    return play_calls, stop_calls


def test_main_window_can_be_constructed_and_closed(qt_app, isolated_settings):
    _, initialize_calls, _ = isolated_settings
    window = gui.create_main_window()

    assert window.windowTitle() == "Jingleplayer"
    assert gui.resource_path("assets/jingleplayer.ico").is_file()
    assert not window.windowIcon().isNull()
    assert initialize_calls == [True]

    window.show()
    qt_app.processEvents()
    assert window.isVisible()

    window.close()
    qt_app.processEvents()
    assert not window.isVisible()


def test_saved_window_size_is_applied(qt_app, isolated_settings):
    window = gui.create_main_window()

    assert window.width() == 1153
    assert window.height() == 509

    window.close()
    qt_app.processEvents()


def test_closing_saves_size_without_changing_other_settings(qt_app, isolated_settings):
    original_settings, _, saved_settings = isolated_settings
    window = gui.create_main_window()
    window.resize(900, 640)

    window.close()
    qt_app.processEvents()

    assert len(saved_settings) == 1
    assert saved_settings[0]["window_size"] == [900, 640]

    expected_settings = deepcopy(original_settings)
    expected_settings["window_size"] = [900, 640]
    assert saved_settings[0] == expected_settings


def test_per_row_creates_32_tiles_in_five_explicit_rows(qt_app, isolated_settings):
    settings, _, _ = isolated_settings
    settings["buttons"]["per_row"] = [8, 5, 6, 4, 9]
    settings["buttons"]["texts"] = [f"Jingle {index}" for index in range(32)]
    settings["buttons"]["colors"] = ["#0080ff"] * 32

    window = gui.create_main_window()

    assert len(window.row_layouts) == 5
    assert len(window.jingle_tiles) == 32
    assert [layout.count() for layout in window.row_layouts] == [8, 5, 6, 4, 9]

    window.close()
    qt_app.processEvents()


def test_zero_button_rows_remain_present(qt_app, isolated_settings):
    settings, _, _ = isolated_settings
    settings["buttons"]["per_row"] = [2, 0, 1, 0, 2]
    settings["buttons"]["texts"] = [f"Jingle {index}" for index in range(5)]
    settings["buttons"]["colors"] = ["#00ff00"] * 5

    window = gui.create_main_window()

    assert len(window.row_layouts) == 5
    assert len(window.jingle_tiles) == 5
    assert [layout.count() for layout in window.row_layouts] == [2, 0, 1, 0, 2]

    window.close()
    qt_app.processEvents()


def test_tiles_use_saved_texts_and_colors(qt_app, isolated_settings):
    settings, _, _ = isolated_settings
    settings["buttons"]["per_row"] = [2, 0, 0, 0, 0]
    settings["buttons"]["texts"] = ["Sweet Caroline", "völlig losgelöst"]
    settings["buttons"]["colors"] = ["#0080ff", "#ffff00"]

    window = gui.create_main_window()

    assert [tile.label.text() for tile in window.jingle_tiles] == ["Sweet Caroline", "völlig losgelöst"]
    assert [tile.jingle_color for tile in window.jingle_tiles] == ["#0080ff", "#ffff00"]
    assert "background-color: #0080ff" in window.jingle_tiles[0].styleSheet()
    assert window.jingle_tiles[0].label.styleSheet().startswith("color: #ffffff")
    assert window.jingle_tiles[1].label.styleSheet().startswith("color: #111111")

    window.close()
    qt_app.processEvents()


def test_tiles_use_a_styled_frame_for_reliable_background_painting(qt_app, isolated_settings):
    settings, _, _ = isolated_settings
    settings["buttons"]["per_row"] = [1, 0, 0, 0, 0]
    settings["buttons"]["texts"] = ["Visible card"]
    settings["buttons"]["colors"] = ["#0080ff"]

    window = gui.create_main_window()
    tile = window.jingle_tiles[0]

    assert isinstance(tile, QFrame)
    assert tile.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert "QFrame#jingleTile" in tile.styleSheet()

    window.close()
    qt_app.processEvents()


def test_incomplete_text_and_color_lists_are_handled_defensively(qt_app, isolated_settings):
    settings, _, _ = isolated_settings
    settings["buttons"]["per_row"] = [2, 2, 0, 0, 0]
    settings["buttons"]["texts"] = ["Only complete entry", "Missing color"]
    settings["buttons"]["colors"] = ["#ff0000"]

    window = gui.create_main_window()

    assert len(window.row_layouts) == 5
    assert len(window.jingle_tiles) == 1
    assert [layout.count() for layout in window.row_layouts] == [1, 0, 0, 0, 0]
    assert window.jingle_tiles[0].label.text() == "Only complete entry"

    window.close()
    qt_app.processEvents()


def test_idle_tile_click_starts_its_jingle(qt_app, isolated_settings, mocked_audio):
    window = gui.create_main_window()
    play_calls, stop_calls = mocked_audio
    window.show()
    qt_app.processEvents()

    QTest.mouseClick(window.jingle_tiles[0], Qt.MouseButton.LeftButton)

    assert play_calls == [(1, "a.wav", 750)]
    assert stop_calls == []
    assert window.jingle_tiles[0].playing is True

    window.close()


def test_second_tile_click_stops_the_same_jingle(qt_app, isolated_settings, mocked_audio):
    window = gui.create_main_window()
    play_calls, stop_calls = mocked_audio

    window.jingle_tiles[0].clicked.emit(1)
    window.jingle_tiles[0].clicked.emit(1)

    assert play_calls == [(1, "a.wav", 750)]
    assert stop_calls == [(1, 750)]
    assert window.jingle_tiles[0].playing is False

    window.close()


def test_different_tiles_play_independently(qt_app, isolated_settings, mocked_audio):
    window = gui.create_main_window()
    play_calls, _ = mocked_audio

    window.jingle_tiles[0].clicked.emit(1)
    window.jingle_tiles[1].clicked.emit(2)

    assert play_calls == [(1, "a.wav", 750), (2, "b.mp3", 750)]
    assert window.jingle_tiles[0].playing is True
    assert window.jingle_tiles[1].playing is True

    window.close()


def test_failed_playback_does_not_mark_tile_as_playing(qt_app, isolated_settings, monkeypatch):
    monkeypatch.setattr(
        gui.jingleplayer_logic,
        "play_jingle",
        lambda index, path, fadeout: {"error": "Playback failed", "success": False},
    )
    window = gui.create_main_window()

    window.jingle_tiles[0].clicked.emit(1)

    assert window.jingle_tiles[0].playing is False

    window.close()


def test_playing_border_preserves_saved_background_color(qt_app, isolated_settings, mocked_audio):
    window = gui.create_main_window()
    tile = window.jingle_tiles[0]

    tile.clicked.emit(1)

    assert "background-color: #ff0000" in tile.styleSheet()
    assert "border: 3px solid #ffffff" in tile.styleSheet()

    window.close()


def test_natural_end_resets_only_the_reported_tile(qt_app, isolated_settings, monkeypatch):
    window = gui.create_main_window()
    window.jingle_tiles[0].set_playing(True)
    window.jingle_tiles[1].set_playing(True)
    monkeypatch.setattr(
        gui.jingleplayer_logic,
        "check_sound_end",
        lambda: [{"index": 1, "playing": False}],
    )

    window._poll_sound_end()

    assert window.jingle_tiles[0].playing is False
    assert window.jingle_tiles[1].playing is True
    window.close()


@pytest.mark.parametrize("no_updates", [None, {}, []])
def test_no_end_update_leaves_tiles_unchanged(qt_app, isolated_settings, monkeypatch, no_updates):
    window = gui.create_main_window()
    window.jingle_tiles[0].set_playing(True)
    monkeypatch.setattr(gui.jingleplayer_logic, "check_sound_end", lambda: no_updates)

    window._poll_sound_end()

    assert window.jingle_tiles[0].playing is True
    window.close()


def test_multiple_natural_ends_are_applied_in_one_poll(qt_app, isolated_settings, monkeypatch):
    window = gui.create_main_window()
    window.jingle_tiles[0].set_playing(True)
    window.jingle_tiles[1].set_playing(True)
    monkeypatch.setattr(
        gui.jingleplayer_logic,
        "check_sound_end",
        lambda: [
            {"index": 1, "playing": False},
            {"index": 2, "playing": False},
        ],
    )

    window._poll_sound_end()

    assert window.jingle_tiles[0].playing is False
    assert window.jingle_tiles[1].playing is False
    window.close()


def test_end_update_for_idle_tile_is_idempotent(qt_app, isolated_settings, monkeypatch):
    window = gui.create_main_window()
    monkeypatch.setattr(
        gui.jingleplayer_logic,
        "check_sound_end",
        lambda: [{"index": 1, "playing": False}],
    )

    window._poll_sound_end()

    assert window.jingle_tiles[0].playing is False
    window.close()


def test_sound_end_timer_is_active_until_window_closes(qt_app, isolated_settings):
    window = gui.create_main_window()

    assert window.sound_end_timer.isActive()
    assert window.sound_end_timer.interval() == gui.jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS

    window.close()
    qt_app.processEvents()

    assert not window.sound_end_timer.isActive()


def test_global_volume_controls_load_saved_value(qt_app, isolated_settings):
    window = gui.create_main_window()

    assert window.volume_slider.minimum() == 0
    assert window.volume_slider.maximum() == 100
    assert window.volume_slider.value() == 65
    assert window.volume_value_label.text() == "65 %"

    window.close()


def test_global_volume_change_updates_engine_label_and_settings(
    qt_app, isolated_settings, monkeypatch
):
    settings, _, saved_settings = isolated_settings
    original_settings = deepcopy(settings)
    volume_calls = []

    def set_volume(volume_percent):
        volume_calls.append(volume_percent)
        settings["volume"] = volume_percent
        return {"volume_set": volume_percent}

    monkeypatch.setattr(gui.jingleplayer_logic, "set_volume_logic", set_volume)
    window = gui.create_main_window()

    window.volume_slider.setValue(42)

    assert window.volume_value_label.text() == "42 %"
    assert volume_calls == [42]
    assert saved_settings[-1]["volume"] == 42
    expected_settings = deepcopy(original_settings)
    expected_settings["volume"] = 42
    assert saved_settings[-1] == expected_settings

    window.close()


def test_changed_global_volume_is_loaded_after_simulated_restart(
    qt_app, isolated_settings, monkeypatch
):
    settings, _, _ = isolated_settings

    def set_volume(volume_percent):
        settings["volume"] = volume_percent
        return {"volume_set": volume_percent}

    monkeypatch.setattr(gui.jingleplayer_logic, "set_volume_logic", set_volume)
    first_window = gui.create_main_window()
    first_window.volume_slider.setValue(37)
    first_window.close()

    restarted_window = gui.create_main_window()

    assert restarted_window.volume_slider.value() == 37
    assert restarted_window.volume_value_label.text() == "37 %"
    restarted_window.close()


def test_right_click_requests_edit_without_left_click(qt_app):
    tile = gui.JingleTile(7, "Jingle", "#0080ff")
    clicked_indices = []
    edited_indices = []
    tile.clicked.connect(clicked_indices.append)
    tile.edit_requested.connect(edited_indices.append)
    tile.show()
    qt_app.processEvents()

    QTest.mouseClick(tile, Qt.MouseButton.RightButton)

    assert edited_indices == [7]
    assert clicked_indices == []
    tile.close()


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (1, ("A", "red", "a.wav", -3, "C:/Jingles")),
        (2, ("B", "blue", "b.mp3", 4, "C:/Jingles")),
    ],
)
def test_editor_receives_values_for_requested_one_based_index(
    qt_app, isolated_settings, monkeypatch, index, expected
):
    received = []

    class DialogProbe:
        def __init__(self, text, color, path, volume_db, last_folder, parent):
            received.append((text, color, path, volume_db, last_folder))

        def exec(self):
            return gui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(gui, "JingleEditDialog", DialogProbe)
    window = gui.create_main_window()

    window._open_jingle_editor(index)

    assert received == [expected]
    window.close()


def test_edit_dialog_loads_all_values_and_disables_save(qt_app):
    dialog = gui.JingleEditDialog("Tor", "#0080ff", "C:/Audio/tor.wav", -6, "C:/Audio")

    assert dialog.windowTitle() == "Jingle bearbeiten"
    assert dialog.name_edit.text() == "Tor"
    assert dialog.color_value == "#0080ff"
    assert "background-color: #0080ff" in dialog.color_button.styleSheet()
    assert dialog.path_edit.text() == "C:/Audio/tor.wav"
    assert dialog.volume_spin.minimum() == -10
    assert dialog.volume_spin.maximum() == 10
    assert dialog.volume_spin.value() == -6
    assert dialog.volume_spin.suffix() == " dB"
    assert not dialog.save_button.isEnabled()

    dialog.reject()


def test_rejected_dialog_changes_no_settings_or_tile(qt_app, isolated_settings):
    settings, _, saved_settings = isolated_settings
    original_settings = deepcopy(settings)
    window = gui.create_main_window()
    tile = window.jingle_tiles[0]
    original_style = tile.styleSheet()
    original_paths = list(window.jingle_paths)
    dialog = gui.JingleEditDialog("A", "red", "a.wav", -3, "C:/Jingles", window)

    dialog.name_edit.setText("Changed")
    dialog.path_edit.setText("changed.mp3")
    dialog.color_value = "#00ff00"
    dialog._update_color_preview()
    dialog.volume_spin.setValue(10)
    dialog.reject()

    assert settings == original_settings
    assert saved_settings == []
    assert tile.label.text() == "A"
    assert tile.styleSheet() == original_style
    assert window.jingle_paths == original_paths
    window.close()


def test_file_dialog_changes_only_temporary_path(qt_app, monkeypatch):
    dialog = gui.JingleEditDialog("A", "red", "old.wav", 0, "C:/Start")
    calls = []

    def choose_file(parent, title, directory, file_filter):
        calls.append((title, directory, file_filter))
        return ("C:/Other/new.mp3", file_filter)

    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", choose_file)

    dialog._browse_audio_file()

    assert calls == [("Audiodatei auswählen", "C:/Start", "Audiodateien (*.mp3 *.wav)")]
    assert dialog.path_edit.text() == "C:/Other/new.mp3"
    assert dialog.last_folder == "C:/Start"
    dialog.reject()


def test_color_dialog_changes_only_temporary_color(qt_app, monkeypatch):
    dialog = gui.JingleEditDialog("A", "#ff0000", "a.wav", 0, "C:/Start")

    monkeypatch.setattr(
        gui.QColorDialog,
        "getColor",
        lambda initial, parent, title: gui.QColor("#00ff00"),
    )

    dialog._choose_color()

    assert dialog.color_value == "#00ff00"
    assert "background-color: #00ff00" in dialog.color_button.styleSheet()
    dialog.reject()


def test_escape_and_window_close_reject_edit_dialog(qt_app):
    escape_dialog = gui.JingleEditDialog("A", "red", "a.wav", 0, "C:/Start")
    escape_dialog.show()
    qt_app.processEvents()

    QTest.keyClick(escape_dialog, Qt.Key.Key_Escape)

    assert escape_dialog.result() == gui.QDialog.DialogCode.Rejected

    close_dialog = gui.JingleEditDialog("A", "red", "a.wav", 0, "C:/Start")
    close_dialog.show()
    qt_app.processEvents()

    close_dialog.close()

    assert close_dialog.result() == gui.QDialog.DialogCode.Rejected
