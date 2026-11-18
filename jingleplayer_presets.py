"""Isolated schema-3 preset model; no runtime activation, imports or filesystem I/O.

Global fields are schema_version=3, window_size, volume, last_folder,
active_preset_id and presets. Each preset has id/name/buttons/fadeout_duration/
button_height. Button arrays have exactly 50 entries; per_row has five integers
0..10 with positive sum. GUI/package ranges are retained: dB -10..10, height
1..10, fadeout 0..2147483647, global volume 0..100, positive window dimensions.
Colors are nonempty strings, not interpreted by Qt. Audio paths are strings;
absolute, relative, Windows and POSIX spellings remain untouched. No file check,
extension restriction or package-relative-path rule applies to local settings.

UUID strings must use the hyphenated UUID representation (case is preserved).
Names must be nonempty without surrounding whitespace/control characters;
NFC+casefold-equivalent names and equivalent UUIDs are duplicates. Display names
are never paths. All results are detached copies; unknown fields fail explicitly
at every level, including legacy background_image, rather than being discarded.

Complete schema-2 settings migrate directly. Unversioned/schema-1 inputs need an
explicit pure legacy_normalizer callback, intended for the existing
jingleplayer_logic._normalize_settings_data supplied by a future integration
layer. This module never imports that module (it initializes pygame on import).
The caller supplies any environment-dependent defaults via that callback.
Legacy prevalidation permits missing fields and short lists, but rejects wrong
types, oversized lists and invalid provided values that the existing normalizer
would repair/coerce/discard. Callback output must be complete valid schema 2 and
must preserve every supplied field/list prefix. The callback receives a copy.

This deliberately supports only unversioned, version 1, version 2 and validated
version 3. Explicit null/boolean/negative versions are not guessed to be legacy.
Migration UUIDv5 uses a fixed namespace and canonical source JSON, independent of
mapping order and filesystem paths. Existing schema-3 IDs are never regenerated.
Nothing here changes CURRENT_SCHEMA_VERSION in the running application.
"""

from copy import deepcopy
import json
import unicodedata
from uuid import UUID, uuid5


PRESET_SCHEMA_VERSION = 3
_MIGRATION_NAMESPACE = UUID("f5661352-f594-41e3-9950-45cf8ac4689e")
_GLOBALS = {"window_size", "volume", "last_folder"}
_BOARD = {"buttons", "fadeout_duration", "button_height"}
_BUTTON_FIELDS = {"texts", "colors", "paths", "volumes", "per_row"}


class PresetValidationError(ValueError):
    """Invalid data or unsupported migration, with code and location attributes."""

    def __init__(self, code, location, message):
        self.code = code
        self.location = location
        super().__init__(f"{location}: {message}")


def _require(condition, code, location, message):
    if not condition:
        raise PresetValidationError(code, location, message)


def _object(value, fields, location, *, partial=False):
    _require(type(value) is dict, "type", location, "expected JSON object")
    unknown = set(value) - fields
    _require(not unknown, "unknown_fields", location, f"unknown fields: {sorted(map(str, unknown))}")
    if not partial:
        _require(set(value) == fields, "missing_fields", location, "required fields missing")


def _integer(value, low, high, location):
    _require(type(value) is int and value >= low and (high is None or value <= high),
             "range", location, f"expected integer in {low}..{high}")


def _string(value, location, *, nonempty=False):
    _require(type(value) is str, "type", location, "expected string")
    _require(not nonempty or bool(value), "value", location, "must not be empty")
    _require(not any(c == "\0" or 0xD800 <= ord(c) <= 0xDFFF for c in value),
             "value", location, "NUL and surrogate characters forbidden")


def validate_preset_id(value):
    """Return the unchanged UUID string, rejecting non-hyphenated UUID syntax."""
    _string(value, "preset.id")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise PresetValidationError("id", "preset.id", "expected UUID") from error
    _require(str(parsed) == value.lower(), "id", "preset.id", "expected hyphenated UUID")
    return value


def _name_key(value):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).casefold())


def validate_preset_name(value):
    """Return unchanged display name; uniqueness is checked at document level."""
    _string(value, "preset.name", nonempty=True)
    _require(value == value.strip() and not any(unicodedata.category(c).startswith("C") for c in value),
             "name", "preset.name", "surrounding whitespace and control characters forbidden")
    return value


def _validate_fields(data, *, partial=False):
    if "window_size" in data:
        size = data["window_size"]
        _require(type(size) is list and len(size) == 2, "type", "window_size", "expected two dimensions")
        for value in size:
            _integer(value, 1, None, "window_size")
    if "volume" in data:
        _integer(data["volume"], 0, 100, "volume")
    if "last_folder" in data:
        _string(data["last_folder"], "last_folder")
    for key, low, high in (("fadeout_duration", 0, 2147483647), ("button_height", 1, 10)):
        if key in data:
            _integer(data[key], low, high, key)
    if "buttons" not in data:
        return
    buttons = data["buttons"]
    _object(buttons, _BUTTON_FIELDS, "buttons", partial=partial)
    for key in ("texts", "colors", "paths", "volumes"):
        if key not in buttons:
            continue
        values = buttons[key]
        _require(type(values) is list and (len(values) <= 50 if partial else len(values) == 50),
                 "slots", f"buttons.{key}", "expected 50 slots (legacy may have fewer)")
        for index, value in enumerate(values):
            location = f"buttons.{key}[{index}]"
            if key == "volumes":
                _integer(value, -10, 10, location)
            else:
                _string(value, location, nonempty=key == "colors")
    if "per_row" in buttons:
        rows = buttons["per_row"]
        _require(type(rows) is list and len(rows) == 5, "layout", "buttons.per_row", "expected five rows")
        for value in rows:
            _integer(value, 0, 10, "buttons.per_row")
        _require(sum(rows) > 0, "layout", "buttons.per_row", "at least one visible button required")


def validate_schema3_settings(data):
    """Validate a complete schema-3 document and return a detached copy."""
    _object(data, _GLOBALS | {"schema_version", "active_preset_id", "presets"}, "settings")
    _integer(data["schema_version"], 3, 3, "schema_version")
    _validate_fields(data)
    presets = data["presets"]
    _require(type(presets) is list and bool(presets), "presets", "presets", "expected nonempty preset list")
    ids, names = set(), set()
    for index, preset in enumerate(presets):
        _object(preset, _BOARD | {"id", "name"}, f"presets[{index}]")
        identity = UUID(validate_preset_id(preset["id"]))
        name = _name_key(validate_preset_name(preset["name"]))
        _require(identity not in ids, "duplicate_id", f"presets[{index}].id", "duplicate UUID")
        _require(name not in names, "duplicate_name", f"presets[{index}].name", "duplicate preset name")
        ids.add(identity)
        names.add(name)
        _validate_fields(preset)
    active = UUID(validate_preset_id(data["active_preset_id"]))
    _require(active in ids, "active_id", "active_preset_id", "active preset does not exist")
    return deepcopy(data)


def _validate_schema2(data):
    _object(data, _GLOBALS | _BOARD | {"schema_version"}, "schema2")
    _integer(data["schema_version"], 2, 2, "schema_version")
    _validate_fields(data)


def migrate_settings_to_schema3(data, *, legacy_normalizer=None):
    """Return schema 3 without mutation; legacy needs an explicitly supplied adapter.

    Passing valid schema 3 is idempotent. Unknown data/repair conflicts raise
    PresetValidationError; a failing normalizer is reported as legacy_normalization.
    No callback is called for schema 2 or 3, and malformed legacy is rejected first.
    """
    _require(type(data) is dict, "type", "settings", "expected JSON object")
    version = data.get("schema_version")
    if version == 3 and type(version) is int:
        return validate_schema3_settings(data)
    _require("schema_version" not in data or (type(version) is int and version in (1, 2)),
             "version", "schema_version", "unsupported schema version")
    source = deepcopy(data)
    if version == 2:
        _validate_schema2(source)
        normalized = deepcopy(source)
    else:
        _object(source, _GLOBALS | _BOARD | {"schema_version"}, "legacy", partial=True)
        _validate_fields(source, partial=True)
        _require(callable(legacy_normalizer), "legacy_adapter", "legacy",
                 "explicit existing legacy_normalizer required; no implicit home/default lookup")
        try:
            normalized = deepcopy(legacy_normalizer(deepcopy(source)))
        except Exception as error:
            raise PresetValidationError("legacy_normalization", "legacy", str(error)) from error
        _validate_schema2(normalized)
        for key, value in source.items():
            if key == "schema_version":
                continue
            if key == "buttons":
                for name, values in value.items():
                    actual = normalized["buttons"][name]
                    _require(actual[:len(values)] == values, "legacy_conflict", f"buttons.{name}",
                             "normalization changed supplied values")
            else:
                _require(normalized[key] == value, "legacy_conflict", key, "normalization changed supplied value")
    canonical = json.dumps(source, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    identity = str(uuid5(_MIGRATION_NAMESPACE, canonical))
    preset = {key: deepcopy(normalized[key]) for key in _BOARD}
    preset.update(id=identity, name="Standard")
    result = {key: deepcopy(normalized[key]) for key in _GLOBALS}
    result.update(schema_version=3, active_preset_id=identity, presets=[preset])
    return validate_schema3_settings(result)


def extract_active_board(data):
    """Return detached flat schema-2 board/settings snapshot, without preset ID/name.

    Includes unchanged global window_size/volume/last_folder. This is data only,
    not persistence or activation, and does not switch the application's schema.
    """
    snapshot = validate_schema3_settings(data)
    active = UUID(snapshot["active_preset_id"])
    preset = next(p for p in snapshot["presets"] if UUID(p["id"]) == active)
    return {"schema_version": 2, **{key: snapshot[key] for key in _GLOBALS},
            **{key: preset[key] for key in _BOARD}}
