import os
from copy import deepcopy

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
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

    return settings, initialize_calls, saved_settings


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
