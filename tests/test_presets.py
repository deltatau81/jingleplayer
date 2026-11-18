"""Isolated model/migration tests; no application schema activation or user I/O."""

from copy import deepcopy
from pathlib import Path
import json
import os
import subprocess
import sys
from uuid import UUID, uuid4

import pytest

import jingleplayer_presets as presets


def schema2():
    return {"schema_version": 2, "window_size": [1153, 509], "volume": 65,
            "last_folder": "C:/Audio", "fadeout_duration": 750, "button_height": 3,
            "buttons": {"texts": [f"Jingle {i}" for i in range(1, 51)],
                        "colors": ["SystemButtonFace"] * 50,
                        "paths": [f"relative/{i}.wav" for i in range(50)],
                        "volumes": [-10, -3, 0, 4, 10] * 10,
                        "per_row": [2, 0, 0, 0, 0]}}


def schema3():
    return presets.migrate_settings_to_schema3(schema2())


def two_presets():
    value = schema3()
    other = deepcopy(value["presets"][0])
    other.update(id=str(uuid4()), name="Training")
    other["buttons"]["texts"][49] = "Hidden training"
    value["presets"].append(other)
    return value


def test_complete_lossless_schema2_migration_and_hidden_slots():
    original = schema2()
    original["buttons"]["paths"][:4] = [r"C:\Audio\嵐.WAV", "/Users/example/é.mp3", "../relative.wav", ""]
    before = deepcopy(original)
    result = presets.migrate_settings_to_schema3(original)
    assert result["schema_version"] == 3 and len(result["presets"]) == 1
    active = result["presets"][0]
    assert active["name"] == "Standard"
    assert UUID(active["id"]) == UUID(result["active_preset_id"])
    for key in ("buttons", "fadeout_duration", "button_height"):
        assert active[key] == original[key]
    for key in ("window_size", "volume", "last_folder"):
        assert result[key] == original[key]
    for name in ("texts", "colors", "paths", "volumes"):
        assert len(active["buttons"][name]) == 50
        assert active["buttons"][name][49] == original["buttons"][name][49]
    assert original == before
    assert presets.extract_active_board(result) == original
    result["presets"][0]["buttons"]["paths"][49] = "detached"
    assert original == before


def test_stable_identity_independent_of_mapping_order_and_idempotent_schema3():
    source = schema2()
    reordered = json.loads(json.dumps(source, sort_keys=True))
    first = presets.migrate_settings_to_schema3(source)
    assert first == presets.migrate_settings_to_schema3(reordered)
    assert presets.migrate_settings_to_schema3(first) == first
    copied = presets.validate_schema3_settings(first)
    copied["presets"][0]["name"] = "detached"
    assert first["presets"][0]["name"] == "Standard"


def test_extracts_selected_preset_not_first_and_returns_detached_snapshot():
    value = two_presets()
    value["active_preset_id"] = value["presets"][1]["id"]
    before = deepcopy(value)
    board = presets.extract_active_board(value)
    assert board["buttons"]["texts"][49] == "Hidden training"
    assert board["window_size"] == value["window_size"] and board["volume"] == 65
    assert not {"presets", "active_preset_id", "id", "name"} & board.keys()
    board["buttons"]["texts"][0] = "detached"
    board["window_size"][0] = 1
    assert value == before


@pytest.mark.parametrize("value", [None, 7, "", "not-a-uuid", "0" * 32, "{00000000-0000-0000-0000-000000000000}"])
def test_invalid_preset_ids(value):
    with pytest.raises(presets.PresetValidationError):
        presets.validate_preset_id(value)


@pytest.mark.parametrize("value", [None, 7, "", " ", " Leading", "Trailing ", "a\n", "a\0", "a\u202e"])
def test_invalid_names(value):
    with pytest.raises(presets.PresetValidationError):
        presets.validate_preset_name(value)


def test_valid_unicode_name_and_uuid_preserved():
    name = "Training 音楽 / Anzeige"
    assert presets.validate_preset_name(name) == name
    identity = str(uuid4()).upper()
    assert presets.validate_preset_id(identity) == identity


@pytest.mark.parametrize("first,second", [("Standard", "STANDARD"), ("é", "e\u0301"), ("Straße", "STRASSE")])
def test_duplicate_names_use_unicode_and_casefold(first, second):
    value = two_presets()
    value["presets"][0]["name"], value["presets"][1]["name"] = first, second
    with pytest.raises(presets.PresetValidationError) as caught:
        presets.validate_schema3_settings(value)
    assert caught.value.code == "duplicate_name"


def test_duplicate_uuid_even_with_different_casing():
    value = two_presets()
    value["presets"][1]["id"] = value["presets"][0]["id"].upper()
    with pytest.raises(presets.PresetValidationError) as caught:
        presets.validate_schema3_settings(value)
    assert caught.value.code == "duplicate_id"


@pytest.mark.parametrize("field,value", [("active_preset_id", str(uuid4())), ("active_preset_id", "bad"),
                                         ("presets", []), ("presets", {}), ("presets", None),
                                         ("schema_version", 4), ("schema_version", True)])
def test_invalid_document_structure(field, value):
    data = schema3()
    data[field] = value
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


@pytest.mark.parametrize("field,value", [("volume", -1), ("volume", 101), ("volume", True),
                                         ("window_size", [0, 600]), ("window_size", [800]),
                                         ("window_size", [800, 1.5]), ("last_folder", None)])
def test_invalid_global_values(field, value):
    data = schema3()
    data[field] = value
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


@pytest.mark.parametrize("field,value", [("button_height", 0), ("button_height", 11),
                                         ("button_height", True), ("fadeout_duration", -1),
                                         ("fadeout_duration", 2147483648), ("fadeout_duration", 1.0)])
def test_invalid_preset_ranges(field, value):
    data = schema3()
    data["presets"][0][field] = value
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


@pytest.mark.parametrize("field,value", [("texts", ["x"] * 49), ("colors", [""] * 50),
                                         ("paths", [None] * 50), ("paths", ["a\0.wav"] * 50),
                                         ("volumes", [11] * 50), ("volumes", [True] * 50),
                                         ("per_row", [0] * 5), ("per_row", [1] * 4),
                                         ("per_row", [11, 0, 0, 0, 0]), ("per_row", [1.0] * 5)])
def test_invalid_buttons(field, value):
    data = schema3()
    data["presets"][0]["buttons"][field] = value
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


@pytest.mark.parametrize("level", ["root", "preset", "buttons"])
def test_unknown_schema3_fields_explicitly_rejected(level):
    data = schema3()
    target = {"root": data, "preset": data["presets"][0], "buttons": data["presets"][0]["buttons"]}[level]
    target["unknown_path"] = "do not discard"
    before = deepcopy(data)
    with pytest.raises(presets.PresetValidationError) as caught:
        presets.validate_schema3_settings(data)
    assert caught.value.code == "unknown_fields" and "unknown_path" in str(caught.value)
    assert data == before


@pytest.mark.parametrize("version", [None, 1])
def test_supported_legacy_uses_existing_normalizer_and_preserves_prefixes(version):
    import jingleplayer_logic as logic

    legacy = schema2()
    if version is None:
        legacy.pop("schema_version")
    else:
        legacy["schema_version"] = version
    for key in ("texts", "colors", "paths", "volumes"):
        legacy["buttons"][key] = legacy["buttons"][key][:3]
    legacy.pop("fadeout_duration")
    before = deepcopy(legacy)
    expected = logic._normalize_settings_data(legacy)
    result = presets.migrate_settings_to_schema3(legacy, legacy_normalizer=logic._normalize_settings_data)
    assert presets.extract_active_board(result) == expected
    assert legacy == before


def test_empty_legacy_defaults_require_explicit_adapter(monkeypatch):
    import jingleplayer_logic as logic

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/isolated-test-home")))
    with pytest.raises(presets.PresetValidationError) as caught:
        presets.migrate_settings_to_schema3({})
    assert caught.value.code == "legacy_adapter"
    result = presets.migrate_settings_to_schema3({}, legacy_normalizer=logic._normalize_settings_data)
    assert presets.extract_active_board(result) == logic._normalize_settings_data({})


@pytest.mark.parametrize("field,value", [("buttons", None), ("buttons", []),
                                         ("volume", "65"), ("last_folder", None),
                                         ("background_image", "old.png"), ("unknown", "retain me")])
def test_legacy_repairs_and_dropped_fields_are_conflicts(field, value):
    source = schema2()
    source.pop("schema_version")
    source[field] = value
    before = deepcopy(source)
    with pytest.raises(presets.PresetValidationError):
        presets.migrate_settings_to_schema3(source, legacy_normalizer=lambda value: pytest.fail("must reject first"))
    assert source == before


@pytest.mark.parametrize("field,value", [("texts", ["x"] * 51), ("paths", "not a list"),
                                         ("volumes", None), ("per_row", ["2", 0, 0, 0, 0]),
                                         ("per_row", [12, 0, 0, 0, 0]), ("per_row", [0] * 5),
                                         ("extra", "unknown")])
def test_legacy_no_truncation_coercion_or_silent_repair(field, value):
    source = schema2()
    source.pop("schema_version")
    source["buttons"][field] = value
    with pytest.raises(presets.PresetValidationError):
        presets.migrate_settings_to_schema3(source, legacy_normalizer=lambda value: pytest.fail("must reject first"))


@pytest.mark.parametrize("version", [None, True, False, -1, 0, 2.0, "2", 4, 99])
def test_unsupported_versions_rejected(version):
    source = schema2()
    source["schema_version"] = version
    with pytest.raises(presets.PresetValidationError):
        presets.migrate_settings_to_schema3(source)


@pytest.mark.parametrize("change", ["unknown_root", "unknown_button", "short", "missing_global"])
def test_schema2_must_be_complete_and_unknowns_never_dropped(change):
    source = schema2()
    if change == "unknown_root":
        source["extension"] = {"keep": True}
    elif change == "unknown_button":
        source["buttons"]["extension"] = "keep"
    elif change == "short":
        source["buttons"]["paths"] = ["a.wav"]
    else:
        source.pop("last_folder")
    with pytest.raises(presets.PresetValidationError):
        presets.migrate_settings_to_schema3(source)


def test_callback_cannot_mutate_input_or_change_supplied_values():
    legacy = schema2()
    legacy.pop("schema_version")
    before = deepcopy(legacy)

    def dishonest(value):
        value["schema_version"] = 2
        value["buttons"]["paths"][49] = "changed.wav"
        return value

    with pytest.raises(presets.PresetValidationError) as caught:
        presets.migrate_settings_to_schema3(legacy, legacy_normalizer=dishonest)
    assert caught.value.code == "legacy_conflict"
    assert legacy == before


def test_failed_callback_reported_and_never_called_for_modern_schemas():
    def fail(value):
        raise RuntimeError("legacy failure")

    with pytest.raises(presets.PresetValidationError) as caught:
        presets.migrate_settings_to_schema3({}, legacy_normalizer=fail)
    assert caught.value.code == "legacy_normalization"
    modern = presets.migrate_settings_to_schema3(schema2(), legacy_normalizer=fail)
    assert presets.migrate_settings_to_schema3(modern, legacy_normalizer=fail) == modern


def test_boundaries_and_case_insensitive_active_uuid():
    value = schema3()
    value["volume"] = 0
    active = value["presets"][0]
    active.update(button_height=10, fadeout_duration=2147483647)
    active["buttons"]["per_row"] = [0, 10, 0, 0, 0]
    value["active_preset_id"] = value["active_preset_id"].upper()
    assert presets.extract_active_board(value)["button_height"] == 10


def test_import_isolated_without_gui_audio_or_application_imports(tmp_path):
    code = """
import sys
import jingleplayer_presets
assert not any(name.startswith(('PySide6', 'pygame', 'jingleplayer_logic', 'jingleplayer_packages')) for name in sys.modules)
"""
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(Path(presets.__file__).parent), PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=environment,
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
