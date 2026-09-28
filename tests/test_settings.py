import json

import pytest

import jingleplayer_logic as logic


def old_settings(buttons):
    return {
        "buttons": buttons,
        "fadeout_duration": 1000,
        "button_height": 2,
        "window_size": [800, 600],
        "volume": 80,
        "last_folder": ".",
    }


@pytest.mark.parametrize(
    ("existing, expected"),
    [
        (None, [0, 0, 0]),
        ([4], [4, 0, 0]),
        ([-3, 2, 7, 9], [-3, 2, 7]),
    ],
)
def test_volume_settings_are_migrated_to_button_count(tmp_path, monkeypatch, existing, expected):
    buttons = {
        "texts": ["A", "B", "C"],
        "colors": ["red", "green", "blue"],
        "paths": ["a.wav", "b.wav", "c.wav"],
        "per_row": [3, 0, 0, 0, 0],
    }
    if existing is not None:
        buttons["volumes"] = existing
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(old_settings(buttons)), encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()

    assert loaded["buttons"]["volumes"] == expected
    assert loaded["volume"] == 80
    assert loaded["buttons"]["texts"] == ["A", "B", "C"]


def test_missing_legacy_top_level_values_receive_defaults(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    assert len(loaded["buttons"]["volumes"]) == logic.DEFAULT_BUTTON_COUNT
    assert loaded["fadeout_duration"] == logic.DEFAULT_FADEOUT_DURATION
