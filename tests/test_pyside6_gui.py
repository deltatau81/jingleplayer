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

    def update_settings(texts, colors, paths, per_row, fadeout, button_height, window_size, volume):
        settings["buttons"]["texts"] = list(texts)
        settings["buttons"]["colors"] = list(colors)
        settings["buttons"]["paths"] = list(paths)
        settings["buttons"]["per_row"] = list(per_row)
        settings["fadeout_duration"] = fadeout
        settings["button_height"] = button_height
        settings["window_size"] = list(window_size)
        settings["volume"] = volume

    def set_button_volume(index, volume_db):
        settings["buttons"]["volumes"][index - 1] = int(volume_db)

    def set_last_folder(folder):
        settings["last_folder"] = str(folder)

    monkeypatch.setattr(gui.jingleplayer_logic, "initialize_settings", lambda: initialize_calls.append(True))
    monkeypatch.setattr(gui.jingleplayer_logic, "get_current_settings", lambda: deepcopy(settings))
    monkeypatch.setattr(gui.jingleplayer_logic, "save_settings", lambda value: saved_settings.append(deepcopy(value)))
    monkeypatch.setattr(gui.jingleplayer_logic, "check_sound_end", lambda: [])
    monkeypatch.setattr(gui.jingleplayer_logic, "update_settings_data", update_settings)
    monkeypatch.setattr(gui.jingleplayer_logic, "set_button_volume", set_button_volume)
    monkeypatch.setattr(gui.jingleplayer_logic, "set_last_folder", set_last_folder)

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


def test_edit_dialog_loads_all_values_and_enables_save(qt_app):
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
    assert dialog.save_button.isEnabled()

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
    assert dialog.selected_folder == str(gui.Path("C:/Other/new.mp3").parent)
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


def test_save_button_accepts_dialog(qt_app):
    dialog = gui.JingleEditDialog("A", "red", "a.wav", 0, "C:/Start")

    dialog.save_button.click()

    assert dialog.result() == gui.QDialog.DialogCode.Accepted


def test_accepted_edit_updates_runtime_tile_engine_and_complete_settings(
    qt_app, isolated_settings, mocked_audio, monkeypatch
):
    settings, _, saved_settings = isolated_settings
    original_settings = deepcopy(settings)
    volume_calls = []
    audio_play_calls, audio_stop_calls = mocked_audio

    def set_button_volume(index, volume_db):
        volume_calls.append((index, volume_db))
        settings["buttons"]["volumes"][index - 1] = volume_db

    class AcceptedDialog:
        def __init__(self, *args):
            pass

        def exec(self):
            return gui.QDialog.DialogCode.Accepted

        def get_values(self):
            return {
                "text": "Changed A",
                "color": "#00ff00",
                "path": "C:/Other/new.wav",
                "volume_db": 7,
                "selected_folder": None,
            }

    monkeypatch.setattr(gui.jingleplayer_logic, "set_button_volume", set_button_volume)
    monkeypatch.setattr(gui, "JingleEditDialog", AcceptedDialog)
    window = gui.create_main_window()
    tile = window.jingle_tiles[0]
    tile.set_playing(True)

    window._open_jingle_editor(1)

    assert settings["buttons"]["texts"] == ["Changed A", "B"]
    assert settings["buttons"]["colors"] == ["#00ff00", "blue"]
    assert settings["buttons"]["paths"] == ["C:/Other/new.wav", "b.mp3"]
    assert settings["buttons"]["volumes"] == [7, 4]
    assert window.jingle_texts == ["Changed A", "B"]
    assert window.jingle_colors == ["#00ff00", "blue"]
    assert window.jingle_paths == ["C:/Other/new.wav", "b.mp3"]
    assert window.jingle_volumes == [7, 4]
    assert tile.label.text() == "Changed A"
    assert tile.playing is True
    assert "background-color: #00ff00" in tile.styleSheet()
    assert "border: 3px solid #ffffff" in tile.styleSheet()
    assert tile.label.styleSheet().startswith(f"color: {gui.contrasting_text_color('#00ff00')}")
    assert window.jingle_tiles[1].label.text() == "B"
    assert window.jingle_tiles[1].jingle_color == "blue"
    assert volume_calls == [(1, 7)]
    assert audio_play_calls == []
    assert audio_stop_calls == []
    assert len(saved_settings) == 1

    expected_settings = deepcopy(original_settings)
    expected_settings["buttons"]["texts"][0] = "Changed A"
    expected_settings["buttons"]["colors"][0] = "#00ff00"
    expected_settings["buttons"]["paths"][0] = "C:/Other/new.wav"
    expected_settings["buttons"]["volumes"][0] = 7
    assert saved_settings[0] == expected_settings

    tile.set_playing(False)
    assert "background-color: #00ff00" in tile.styleSheet()
    assert "border: 1px solid rgba(0, 0, 0, 45)" in tile.styleSheet()

    tile.clicked.emit(1)
    assert audio_play_calls == [(1, "C:/Other/new.wav", 750)]
    window.close()


@pytest.mark.parametrize("index", [1, 2])
def test_accepted_edit_updates_only_requested_list_position(
    qt_app, isolated_settings, monkeypatch, index
):
    settings, _, _ = isolated_settings
    original = deepcopy(settings["buttons"])

    class AcceptedDialog:
        def __init__(self, *args):
            pass

        def exec(self):
            return gui.QDialog.DialogCode.Accepted

        def get_values(self):
            return {
                "text": f"Changed {index}",
                "color": "#ffffff",
                "path": f"changed-{index}.wav",
                "volume_db": index,
                "selected_folder": None,
            }

    monkeypatch.setattr(gui, "JingleEditDialog", AcceptedDialog)
    window = gui.create_main_window()

    window._open_jingle_editor(index)

    changed_position = index - 1
    other_position = 1 - changed_position
    assert settings["buttons"]["texts"][changed_position] == f"Changed {index}"
    assert settings["buttons"]["colors"][changed_position] == "#ffffff"
    assert settings["buttons"]["paths"][changed_position] == f"changed-{index}.wav"
    assert settings["buttons"]["volumes"][changed_position] == index
    for key in ("texts", "colors", "paths", "volumes"):
        assert settings["buttons"][key][other_position] == original[key][other_position]
    window.close()


@pytest.mark.parametrize(
    ("selected_folder", "expected_folder"),
    [("C:/Picked", "C:/Picked"), (None, "C:/Jingles")],
)
def test_last_folder_changes_only_for_browsed_file_after_accept(
    qt_app, isolated_settings, monkeypatch, selected_folder, expected_folder
):
    settings, _, saved_settings = isolated_settings

    class AcceptedDialog:
        def __init__(self, *args):
            pass

        def exec(self):
            return gui.QDialog.DialogCode.Accepted

        def get_values(self):
            return {
                "text": "A",
                "color": "red",
                "path": "C:/Picked/new.wav",
                "volume_db": -3,
                "selected_folder": selected_folder,
            }

    monkeypatch.setattr(gui, "JingleEditDialog", AcceptedDialog)
    window = gui.create_main_window()

    window._open_jingle_editor(1)

    assert settings["last_folder"] == expected_folder
    assert window.last_folder == expected_folder
    assert saved_settings[-1]["last_folder"] == expected_folder
    window.close()


def test_saved_edit_is_visible_after_reopen_restart_and_close(
    qt_app, isolated_settings, monkeypatch
):
    settings, _, saved_settings = isolated_settings
    opened_values = []

    class FirstAcceptedDialog:
        def __init__(self, *args):
            pass

        def exec(self):
            return gui.QDialog.DialogCode.Accepted

        def get_values(self):
            return {
                "text": "Persistent",
                "color": "#123456",
                "path": "persistent.mp3",
                "volume_db": -8,
                "selected_folder": "C:/Persistent",
            }

    monkeypatch.setattr(gui, "JingleEditDialog", FirstAcceptedDialog)
    first_window = gui.create_main_window()
    first_window._open_jingle_editor(1)
    first_window.close()
    saved_after_close = deepcopy(saved_settings[-1])

    class ReopenedDialog:
        def __init__(self, text, color, path, volume_db, last_folder, parent):
            opened_values.append((text, color, path, volume_db, last_folder))

        def exec(self):
            return gui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(gui, "JingleEditDialog", ReopenedDialog)
    restarted_window = gui.create_main_window()
    restarted_window._open_jingle_editor(1)

    assert restarted_window.jingle_tiles[0].label.text() == "Persistent"
    assert opened_values == [("Persistent", "#123456", "persistent.mp3", -8, "C:/Persistent")]
    assert saved_after_close["buttons"]["texts"][0] == "Persistent"
    assert saved_after_close["buttons"]["colors"][0] == "#123456"
    assert saved_after_close["buttons"]["paths"][0] == "persistent.mp3"
    assert saved_after_close["buttons"]["volumes"][0] == -8
    assert saved_after_close["last_folder"] == "C:/Persistent"
    restarted_window.close()


def test_settings_button_replaces_main_window_fadeout_control(qt_app, isolated_settings):
    _, _, saved_settings = isolated_settings

    window = gui.create_main_window()

    assert window.settings_button.text() == "Einstellungen"
    assert not hasattr(window, "fadeout_spin")
    assert window.fadeout_duration == 750
    assert saved_settings == []
    window.close()


def test_settings_dialog_shows_fadeout_and_read_only_layout_values(qt_app):
    dialog = gui.SettingsDialog(750, [8, 5, 6, 4, 9], 3)

    assert dialog.windowTitle() == "Einstellungen"
    assert dialog.fadeout_spin.minimum() == 0
    assert dialog.fadeout_spin.maximum() == gui.MAX_FADEOUT_DURATION_MS
    assert dialog.fadeout_spin.singleStep() == 1
    assert dialog.fadeout_spin.suffix() == " ms"
    assert dialog.fadeout_spin.value() == 750
    assert len(dialog.per_row_spins) == 5
    assert [spin.value() for spin in dialog.per_row_spins] == [8, 5, 6, 4, 9]
    assert all(spin.minimum() == 0 for spin in dialog.per_row_spins)
    assert all(spin.maximum() == 10 for spin in dialog.per_row_spins)
    assert all(not spin.isEnabled() for spin in dialog.per_row_spins)
    assert dialog.button_height_spin.value() == 3
    assert not dialog.button_height_spin.isEnabled()
    dialog.reject()


def test_settings_button_opens_modal_dialog(qt_app, isolated_settings, monkeypatch):
    received = []

    class DialogProbe:
        def __init__(self, fadeout, per_row, button_height, parent):
            received.append((fadeout, per_row, button_height, parent))

        def exec(self):
            return gui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(gui, "SettingsDialog", DialogProbe)
    window = gui.create_main_window()

    window.settings_button.click()

    assert received == [(750, [2, 0, 0, 0, 0], 3, window)]
    window.close()


def test_cancelled_settings_dialog_changes_nothing(qt_app, isolated_settings, monkeypatch):
    settings, _, saved_settings = isolated_settings
    original_settings = deepcopy(settings)

    class RejectedDialog:
        def __init__(self, *args):
            self.fadeout_spin = type("Value", (), {"value": lambda self: 2500})()

        def exec(self):
            return gui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(gui, "SettingsDialog", RejectedDialog)
    window = gui.create_main_window()
    original_states = [tile.playing for tile in window.jingle_tiles]

    window._open_settings_dialog()

    assert settings == original_settings
    assert window.fadeout_duration == 750
    assert [tile.playing for tile in window.jingle_tiles] == original_states
    assert saved_settings == []
    window.close()


def test_settings_dialog_save_accepts_while_escape_and_close_reject(qt_app):
    accepted_dialog = gui.SettingsDialog(750, [2, 0, 0, 0, 0], 3)
    save_button = accepted_dialog.button_box.button(gui.QDialogButtonBox.StandardButton.Save)

    save_button.click()

    assert accepted_dialog.result() == gui.QDialog.DialogCode.Accepted

    escape_dialog = gui.SettingsDialog(750, [2, 0, 0, 0, 0], 3)
    escape_dialog.show()
    qt_app.processEvents()
    QTest.keyClick(escape_dialog, Qt.Key.Key_Escape)
    assert escape_dialog.result() == gui.QDialog.DialogCode.Rejected

    close_dialog = gui.SettingsDialog(750, [2, 0, 0, 0, 0], 3)
    close_dialog.show()
    qt_app.processEvents()
    close_dialog.close()
    assert close_dialog.result() == gui.QDialog.DialogCode.Rejected


def test_accepted_settings_dialog_saves_only_fadeout(qt_app, isolated_settings, monkeypatch):
    settings, _, saved_settings = isolated_settings
    original_per_row = list(settings["buttons"]["per_row"])
    original_height = settings["button_height"]

    class AcceptedDialog:
        def __init__(self, *args):
            self.fadeout_spin = type("Value", (), {"value": lambda self: 2500})()

        def exec(self):
            return gui.QDialog.DialogCode.Accepted

    monkeypatch.setattr(gui, "SettingsDialog", AcceptedDialog)
    window = gui.create_main_window()

    window._open_settings_dialog()

    assert window.fadeout_duration == 2500
    assert settings["fadeout_duration"] == 2500
    assert settings["buttons"]["per_row"] == original_per_row
    assert settings["button_height"] == original_height
    assert len(saved_settings) == 1
    window.close()


def test_saved_settings_dialog_updates_only_fadeout_without_audio_or_tile_changes(
    qt_app, isolated_settings, mocked_audio
):
    settings, _, saved_settings = isolated_settings
    original_settings = deepcopy(settings)
    play_calls, stop_calls = mocked_audio
    window = gui.create_main_window()
    window.jingle_tiles[0].set_playing(True)
    original_tile_style = window.jingle_tiles[0].styleSheet()

    window._save_fadeout_duration(2500)

    assert window.fadeout_duration == 2500
    assert settings["fadeout_duration"] == 2500
    assert play_calls == []
    assert stop_calls == []
    assert window.jingle_tiles[0].playing is True
    assert window.jingle_tiles[0].styleSheet() == original_tile_style
    assert len(saved_settings) == 1
    expected_settings = deepcopy(original_settings)
    expected_settings["fadeout_duration"] = 2500
    assert saved_settings[0] == expected_settings
    window.close()


def test_play_and_stop_use_changed_fadeout(qt_app, isolated_settings, mocked_audio):
    window = gui.create_main_window()
    play_calls, stop_calls = mocked_audio

    window._save_fadeout_duration(2500)
    window.jingle_tiles[0].clicked.emit(1)
    window.jingle_tiles[0].clicked.emit(1)

    assert play_calls == [(1, "a.wav", 2500)]
    assert stop_calls == [(1, 2500)]
    window.close()


def test_changed_fadeout_survives_close_and_simulated_restart(qt_app, isolated_settings):
    settings, _, saved_settings = isolated_settings
    first_window = gui.create_main_window()

    first_window._save_fadeout_duration(1800)
    first_window.close()
    saved_after_close = deepcopy(saved_settings[-1])

    restarted_window = gui.create_main_window()

    assert settings["fadeout_duration"] == 1800
    assert saved_after_close["fadeout_duration"] == 1800
    assert restarted_window.fadeout_duration == 1800
    restarted_window.close()
