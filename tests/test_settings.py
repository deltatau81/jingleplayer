import json
import os
from pathlib import Path

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


def full_settings(slot_count=50, schema_version=None):
    data = old_settings({
        "texts": [f"Text {index}" for index in range(slot_count)],
        "colors": [f"Color {index}" for index in range(slot_count)],
        "paths": [f"{index}.wav" for index in range(slot_count)],
        "volumes": list(range(slot_count)),
        "per_row": [8, 5, 6, 4, 9],
    })
    if schema_version is not None:
        data["schema_version"] = schema_version
    return data


def write_settings_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_new_install_load_is_side_effect_free_and_first_save_creates_file(tmp_path, monkeypatch):
    path = tmp_path / "missing-parent" / "jingleplayer_settings.json"
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()

    assert loaded["schema_version"] == logic.CURRENT_SCHEMA_VERSION
    assert len(loaded["buttons"]["texts"]) == logic.DEFAULT_BUTTON_COUNT
    assert not path.parent.exists()
    assert not path.exists()
    result = logic.save_settings(loaded)
    assert result == {"success": True, "skipped": False, "error": None}
    assert path.is_file()
    assert not (path.parent / logic.PRE_PYSIDE6_BACKUP_NAME).exists()


@pytest.mark.parametrize("slot_count", [32, 40, 50])
def test_unversioned_load_normalizes_without_writing_and_unchanged_save_skips(
    tmp_path, monkeypatch, slot_count
):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(slot_count))
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()

    assert path.read_bytes() == original
    assert len(loaded["buttons"]["texts"]) == 50
    assert loaded["schema_version"] == 2
    assert logic.get_settings_persistence_status()["backup_required"] is True
    result = logic.save_settings(loaded)
    assert result == {"success": True, "skipped": True, "error": None}
    assert path.read_bytes() == original
    assert not (tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME).exists()


@pytest.mark.parametrize("slot_count", [32, 40, 50])
@pytest.mark.parametrize("schema_version", [None, 1])
def test_first_changed_legacy_save_creates_exact_backup_and_schema_two(
    tmp_path, monkeypatch, schema_version, slot_count
):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(slot_count, schema_version))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 81

    result = logic.save_settings(loaded)

    assert result["success"] is True
    assert result["skipped"] is False
    assert (tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME).read_bytes() == original
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2
    assert len(saved["buttons"]["texts"]) == 50
    assert logic.get_settings_persistence_status()["backup_required"] is False


def test_identical_existing_backup_allows_retry_without_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    backup = tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME
    original = write_settings_bytes(path, full_settings(40))
    backup.write_bytes(original)
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 82

    result = logic.save_settings(loaded)

    assert result["success"] is True
    assert backup.read_bytes() == original


def test_different_existing_backup_blocks_save(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    backup = tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME
    original = write_settings_bytes(path, full_settings(40))
    backup.write_bytes(b"different")
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 83

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert path.read_bytes() == original
    assert backup.read_bytes() == b"different"


def test_backup_creation_failure_blocks_save(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(40))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 84
    real_open = open

    def failing_open(file, mode="r", *args, **kwargs):
        if Path(file).name == logic.PRE_PYSIDE6_BACKUP_NAME and mode == "xb":
            raise PermissionError("backup denied")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert path.read_bytes() == original


def test_failed_save_after_backup_keeps_backup_and_original(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    backup = tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME
    original = write_settings_bytes(path, full_settings(40))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 88
    monkeypatch.setattr(
        logic.os,
        "replace",
        lambda *args: (_ for _ in ()).throw(OSError("replace failed")),
    )

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert backup.read_bytes() == original
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_schema_two_save_needs_no_migration_backup(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    write_settings_bytes(path, full_settings(50, 2))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 85

    assert logic.save_settings(loaded)["success"] is True
    assert not (tmp_path / logic.PRE_PYSIDE6_BACKUP_NAME).exists()


def test_future_schema_is_write_blocked_and_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(50, 99))
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()
    status = logic.get_settings_persistence_status()
    result = logic.save_settings(loaded)

    assert status["write_blocked"] is True
    assert "schema_version 99" in status["error"]
    assert result["success"] is False
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "raw",
    [b"{broken", b"[]", b'{"buttons": []}'],
)
def test_invalid_existing_data_is_write_blocked(tmp_path, monkeypatch, raw):
    path = tmp_path / "jingleplayer_settings.json"
    path.write_bytes(raw)
    monkeypatch.setattr(logic, "settings_file", path)

    loaded = logic.load_settings()
    result = logic.save_settings(loaded)

    assert logic.get_settings_persistence_status()["write_blocked"] is True
    assert result["success"] is False
    assert path.read_bytes() == raw


def test_read_error_blocks_later_save(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(50, 2))
    monkeypatch.setattr(logic, "settings_file", path)
    path_type = type(path)
    real_read_bytes = path_type.read_bytes

    def failing_read(self):
        if self == path:
            raise PermissionError("read denied")
        return real_read_bytes(self)

    monkeypatch.setattr(path_type, "read_bytes", failing_read)
    loaded = logic.load_settings()

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert original == path.open("rb").read()


def test_atomic_save_uses_replace_and_leaves_no_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["last_folder"] = "Übung"
    replace_calls = []
    real_replace = os.replace

    def tracked_replace(source, destination):
        replace_calls.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(logic.os, "replace", tracked_replace)

    result = logic.save_settings(loaded)

    assert result["success"] is True
    assert len(replace_calls) == 1
    assert Path(replace_calls[0][0]).parent == path.parent
    assert replace_calls[0][1] == path
    assert list(tmp_path.glob("*.tmp")) == []
    assert json.loads(path.read_text(encoding="utf-8"))["last_folder"] == "Übung"


@pytest.mark.parametrize("failure", ["flush", "fsync", "replace"])
def test_atomic_save_failure_preserves_original_and_removes_temp(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(50, 2))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 86
    if failure == "flush":
        real_named_temporary_file = logic.tempfile.NamedTemporaryFile

        class FlushFailure:
            def __init__(self, temporary_file):
                self.temporary_file = temporary_file
                self.name = temporary_file.name

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.temporary_file.close()

            def write(self, data):
                return self.temporary_file.write(data)

            def flush(self):
                raise OSError("flush failed")

            def fileno(self):
                return self.temporary_file.fileno()

        monkeypatch.setattr(
            logic.tempfile,
            "NamedTemporaryFile",
            lambda *args, **kwargs: FlushFailure(real_named_temporary_file(*args, **kwargs)),
        )
    elif failure == "fsync":
        monkeypatch.setattr(logic.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("fsync failed")))
    else:
        monkeypatch.setattr(logic.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("replace failed")))

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_serialization_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "jingleplayer_settings.json"
    original = write_settings_bytes(path, full_settings(50, 2))
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["unknown_object"] = object()

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert path.read_bytes() == original


def test_unknown_supported_keys_are_preserved_but_background_image_is_removed(
    tmp_path, monkeypatch
):
    path = tmp_path / "jingleplayer_settings.json"
    data = full_settings(50, 2)
    data["custom_root"] = {"keep": True}
    data["background_image"] = "obsolete.png"
    data["buttons"]["custom_buttons"] = "keep"
    write_settings_bytes(path, data)
    monkeypatch.setattr(logic, "settings_file", path)
    loaded = logic.load_settings()
    loaded["volume"] = 87

    assert logic.save_settings(loaded)["success"] is True
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["custom_root"] == {"keep": True}
    assert saved["buttons"]["custom_buttons"] == "keep"
    assert "background_image" not in saved


@pytest.mark.parametrize(
    "target_bytes",
    [
        b'{"buttons":"kaputt"}',
        b"{broken",
        json.dumps(full_settings(50, 99)).encode("utf-8"),
    ],
    ids=["buttons-not-dictionary", "broken-json", "future-schema"],
)
def test_path_change_to_invalid_existing_target_is_write_blocked(
    tmp_path, monkeypatch, target_bytes
):
    path_a = tmp_path / "a" / "jingleplayer_settings.json"
    path_b = tmp_path / "b" / "jingleplayer_settings.json"
    write_settings_bytes(path_a, full_settings(50, 2))
    path_b.parent.mkdir(parents=True)
    path_b.write_bytes(target_bytes)
    monkeypatch.setattr(logic, "settings_file", path_a)
    loaded = logic.load_settings()
    loaded["volume"] = 89
    replace_calls = []
    monkeypatch.setattr(logic, "settings_file", path_b)
    monkeypatch.setattr(logic.os, "replace", lambda *args: replace_calls.append(args))

    result = logic.save_settings(loaded)

    assert result["success"] is False
    assert logic.get_settings_persistence_status()["write_blocked"] is True
    assert path_b.read_bytes() == target_bytes
    assert replace_calls == []


def test_successful_save_after_path_change_updates_loaded_path_and_next_save_skips(
    tmp_path, monkeypatch
):
    path_a = tmp_path / "a" / "jingleplayer_settings.json"
    path_b = tmp_path / "b" / "jingleplayer_settings.json"
    write_settings_bytes(path_a, full_settings(50, 2))
    monkeypatch.setattr(logic, "settings_file", path_a)
    loaded = logic.load_settings()
    monkeypatch.setattr(logic, "settings_file", path_b)

    first_result = logic.save_settings(loaded)

    assert first_result == {"success": True, "skipped": False, "error": None}
    assert logic._loaded_settings_path == path_b
    assert path_b.is_file()
    monkeypatch.setattr(
        logic,
        "_inspect_unloaded_settings_path",
        lambda: pytest.fail("Der bereits gespeicherte Pfad wurde erneut inspiziert."),
    )

    second_result = logic.save_settings(loaded)

    assert second_result == {"success": True, "skipped": True, "error": None}
