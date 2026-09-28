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
        (None, []),
        ([4], [4]),
        ([-3, 2, 7, 9], [-3, 2, 7, 9]),
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

    assert loaded["buttons"]["volumes"][:len(expected)] == expected
    assert loaded["buttons"]["volumes"][len(expected):] == [0] * (logic.DEFAULT_BUTTON_COUNT - len(expected))
    assert len(loaded["buttons"]["volumes"]) == logic.DEFAULT_BUTTON_COUNT
    assert loaded["volume"] == 80
    assert loaded["buttons"]["texts"][:3] == ["A", "B", "C"]
    assert len(loaded["buttons"]["texts"]) == logic.DEFAULT_BUTTON_COUNT


def test_missing_legacy_top_level_values_receive_defaults(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    assert len(loaded["buttons"]["volumes"]) == logic.DEFAULT_BUTTON_COUNT
    assert loaded["fadeout_duration"] == logic.DEFAULT_FADEOUT_DURATION


def test_default_initialization_creates_all_runtime_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "settings_file", tmp_path / "missing.json")

    logic.initialize_settings()

    assert len(logic.button_texts) == logic.DEFAULT_BUTTON_COUNT
    assert len(logic.button_colors) == logic.DEFAULT_BUTTON_COUNT
    assert len(logic.jingle_paths) == logic.DEFAULT_BUTTON_COUNT
    assert len(logic.button_volumes) == logic.DEFAULT_BUTTON_COUNT


def test_short_legacy_settings_are_extended_to_all_slots(tmp_path, monkeypatch):
    buttons = {
        "texts": ["A", "B"],
        "colors": ["red", "blue"],
        "paths": ["a.wav", "b.mp3"],
        "volumes": [-3, 4],
        "per_row": [2, 0, 0, 0, 0],
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(old_settings(buttons)), encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()

    assert loaded["buttons"]["texts"][:2] == ["A", "B"]
    assert loaded["buttons"]["texts"][2:] == [
        f"Jingle {index}" for index in range(3, logic.DEFAULT_BUTTON_COUNT + 1)
    ]
    assert loaded["buttons"]["colors"][:2] == ["red", "blue"]
    assert loaded["buttons"]["colors"][2:] == ["SystemButtonFace"] * 48
    assert loaded["buttons"]["paths"][:2] == ["a.wav", "b.mp3"]
    assert loaded["buttons"]["paths"][2:] == [""] * 48
    assert loaded["buttons"]["volumes"][:2] == [-3, 4]
    assert loaded["buttons"]["volumes"][2:] == [0] * 48


def test_full_and_oversized_slot_lists_are_normalized_without_changing_prefix(tmp_path, monkeypatch):
    count = logic.DEFAULT_BUTTON_COUNT + 3
    buttons = {
        "texts": [f"Text {index}" for index in range(count)],
        "colors": [f"Color {index}" for index in range(count)],
        "paths": [f"{index}.wav" for index in range(count)],
        "volumes": list(range(count)),
        "per_row": [8, 5, 6, 4, 9],
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(old_settings(buttons)), encoding="utf-8")
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()

    for key in ("texts", "colors", "paths", "volumes"):
        assert loaded["buttons"][key] == buttons[key][:logic.DEFAULT_BUTTON_COUNT]


def test_reducing_and_restoring_per_row_preserves_all_slot_data(monkeypatch):
    texts = [f"Text {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    colors = [f"Color {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    paths = [f"{index}.wav" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    volumes = [index - 25 for index in range(logic.DEFAULT_BUTTON_COUNT)]
    monkeypatch.setattr(logic, "button_volumes", list(volumes))

    logic.update_settings_data(texts, colors, paths, [2, 0, 0, 0, 0], 1000, 2, [800, 600], 80)
    reduced = logic.get_current_settings()

    assert reduced["buttons"]["per_row"] == [2, 0, 0, 0, 0]
    assert reduced["buttons"]["texts"] == texts
    assert reduced["buttons"]["colors"] == colors
    assert reduced["buttons"]["paths"] == paths
    assert reduced["buttons"]["volumes"] == volumes

    logic.update_settings_data(texts, colors, paths, [8, 5, 6, 4, 9], 1000, 2, [800, 600], 80)
    restored = logic.get_current_settings()

    assert restored["buttons"]["per_row"] == [8, 5, 6, 4, 9]
    assert restored["buttons"]["texts"] == texts
    assert restored["buttons"]["volumes"] == volumes


def test_empty_and_out_of_range_per_row_is_normalized_without_changing_slots(monkeypatch):
    texts = [f"Text {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    monkeypatch.setattr(logic, "button_volumes", [0] * logic.DEFAULT_BUTTON_COUNT)

    logic.update_settings_data(
        texts,
        ["blue"] * logic.DEFAULT_BUTTON_COUNT,
        [""] * logic.DEFAULT_BUTTON_COUNT,
        [0, 0, 0, 0, 0],
        1000,
        2,
        [800, 600],
        80,
    )

    current = logic.get_current_settings()
    assert current["buttons"]["per_row"] == [10, 10, 10, 10, 10]
    assert current["buttons"]["texts"] == texts
    assert current["buttons"]["colors"] == ["blue"] * logic.DEFAULT_BUTTON_COUNT
    assert current["buttons"]["paths"] == [""] * logic.DEFAULT_BUTTON_COUNT
    assert current["buttons"]["volumes"] == [0] * logic.DEFAULT_BUTTON_COUNT

    logic.update_settings_data(
        texts,
        ["blue"] * logic.DEFAULT_BUTTON_COUNT,
        [""] * logic.DEFAULT_BUTTON_COUNT,
        [0, 12, -4, 5, 0],
        1000,
        2,
        [800, 600],
        80,
    )

    clamped = logic.get_current_settings()
    assert clamped["buttons"]["per_row"] == [0, 10, 0, 5, 0]
    assert clamped["buttons"]["texts"] == texts
    assert clamped["buttons"]["colors"] == ["blue"] * logic.DEFAULT_BUTTON_COUNT
    assert clamped["buttons"]["paths"] == [""] * logic.DEFAULT_BUTTON_COUNT
    assert clamped["buttons"]["volumes"] == [0] * logic.DEFAULT_BUTTON_COUNT


@pytest.mark.parametrize(
    "per_row",
    [
        [0, 5, 0, 0, 0],
        [0, 0, 6, 0, 0],
        [0, 0, 0, 0, 9],
    ],
)
def test_leading_empty_rows_remain_valid_without_changing_slots(monkeypatch, per_row):
    texts = [f"Text {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    colors = [f"Color {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    paths = [f"{index}.wav" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    volumes = [index - 25 for index in range(logic.DEFAULT_BUTTON_COUNT)]
    monkeypatch.setattr(logic, "button_volumes", list(volumes))

    logic.update_settings_data(texts, colors, paths, per_row, 1000, 2, [800, 600], 80)

    current = logic.get_current_settings()
    assert current["buttons"]["per_row"] == per_row
    assert current["buttons"]["texts"] == texts
    assert current["buttons"]["colors"] == colors
    assert current["buttons"]["paths"] == paths
    assert current["buttons"]["volumes"] == volumes


def test_reduced_layout_persists_and_reloads_all_slots(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(logic, "settings_file", path)
    texts = [f"Persistent {index}" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    colors = ["blue"] * logic.DEFAULT_BUTTON_COUNT
    paths = [f"{index}.wav" for index in range(logic.DEFAULT_BUTTON_COUNT)]
    monkeypatch.setattr(logic, "button_volumes", list(range(logic.DEFAULT_BUTTON_COUNT)))

    logic.update_settings_data(texts, colors, paths, [2, 0, 0, 0, 0], 1000, 2, [800, 600], 80)
    logic.save_settings(logic.get_current_settings())
    reloaded = logic.load_settings()

    assert reloaded["buttons"]["per_row"] == [2, 0, 0, 0, 0]
    assert reloaded["buttons"]["texts"] == texts
    assert reloaded["buttons"]["paths"] == paths
    assert reloaded["buttons"]["volumes"] == list(range(logic.DEFAULT_BUTTON_COUNT))
