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
Each preset may additionally contain background_image, a local path string.
Absent or empty means disabled; validation never checks/resolves files or adds
the field to old documents. Schema-2 extraction deliberately omits it; new presets
start without an image, duplicates copy the string, deletion never touches files.
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

Management operations validate input first and return a detached validated schema-3
document. They never save or activate runtime state. Create/duplicate append at the
end and optionally change only the document's active_preset_id. Rename preserves
ID/order/selection. Delete protects the last preset and requires an explicit other
successor for the active preset. A supplied successor is always validated, even
for inactive deletion, but never changes selection in that case. Audio paths are
data only; duplication/deletion performs no file operations.
"""

from copy import deepcopy
import json
import unicodedata
from uuid import UUID, uuid4, uuid5


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
        optional = {"background_image"} if isinstance(preset, dict) and "background_image" in preset else set()
        _object(preset, _BOARD | {"id", "name"} | optional, f"presets[{index}]")
        if optional:
            _string(preset["background_image"], f"presets[{index}].background_image")
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


def _preset_index(data, preset_id, *, location="preset.id"):
    try:
        identity = UUID(validate_preset_id(preset_id))
    except PresetValidationError as error:
        raise PresetValidationError(error.code, location, str(error)) from error
    for index, preset in enumerate(data["presets"]):
        if UUID(preset["id"]) == identity:
            return index
    raise PresetValidationError("unknown_id", location, "preset does not exist")


def _available_name(data, name, *, exclude_index=None):
    key = _name_key(validate_preset_name(name))
    _require(not any(index != exclude_index and _name_key(preset["name"]) == key
                     for index, preset in enumerate(data["presets"])),
             "duplicate_name", "preset.name", "duplicate preset name")
    return name


def _fresh_preset_id(data):
    used = {UUID(preset["id"]) for preset in data["presets"]}
    # Collision retry is bounded so faulty randomness cannot cause an endless loop.
    for _ in range(32):
        try:
            identity = uuid4()
        except OSError as error:
            raise PresetValidationError("id_generation", "preset.id", "UUID generation failed") from error
        if identity not in used:
            return str(identity)
    raise PresetValidationError("id_generation", "preset.id", "could not generate unique UUID")


def create_preset(data, name, *, activate=False):
    """Append a blank preset with UUIDv4; optionally select it in returned data.

    Defaults match jingleplayer_logic._default_settings without importing it:
    50 Jingle 1..50 labels, SystemButtonFace, empty paths, 0 dB, five rows of
    ten buttons, 1000 ms fadeout and button_height=2. Globals remain untouched.
    activate must be bool. No runtime activation or persistence occurs.
    """
    result = validate_schema3_settings(data)
    _require(type(activate) is bool, "type", "activate", "expected boolean")
    name = _available_name(result, name)
    preset = {"id": _fresh_preset_id(result), "name": name,
              "buttons": {"texts": [f"Jingle {i}" for i in range(1, 51)],
                          "colors": ["SystemButtonFace"] * 50,
                          "paths": [""] * 50, "volumes": [0] * 50,
                          "per_row": [10] * 5},
              "fadeout_duration": 1000, "button_height": 2}
    result["presets"].append(preset)
    if activate:
        result["active_preset_id"] = preset["id"]
    return validate_schema3_settings(result)


def duplicate_preset(data, preset_id, name, *, activate=False):
    """Append independent copy of all source fields, with new UUIDv4 and name."""
    result = validate_schema3_settings(data)
    _require(type(activate) is bool, "type", "activate", "expected boolean")
    index = _preset_index(result, preset_id)
    name = _available_name(result, name)
    duplicate = deepcopy(result["presets"][index])
    duplicate.update(id=_fresh_preset_id(result), name=name)
    result["presets"].append(duplicate)
    if activate:
        result["active_preset_id"] = duplicate["id"]
    return validate_schema3_settings(result)


def rename_preset(data, preset_id, name):
    """Change only the requested display name; no-op/self-case rename is allowed."""
    result = validate_schema3_settings(data)
    index = _preset_index(result, preset_id)
    result["presets"][index]["name"] = _available_name(result, name, exclude_index=index)
    return validate_schema3_settings(result)


def delete_preset(data, preset_id, *, successor_id=None):
    """Remove one preset in memory; last preset protected, active needs successor.

    Any successor must identify a different existing preset. Inactive deletion
    preserves the exact active ID string; active deletion selects the successor's
    stored ID. UUID lookup is case-insensitive, consistently with validation.
    Never removes source audio, prepared packages, libraries or directories.
    """
    result = validate_schema3_settings(data)
    index = _preset_index(result, preset_id)
    _require(len(result["presets"]) > 1, "last_preset", "presets", "cannot delete last preset")
    active = UUID(result["active_preset_id"]) == UUID(result["presets"][index]["id"])
    _require(not active or successor_id is not None, "successor_required", "successor_id",
             "deleting active preset requires an explicit successor")
    if successor_id is not None:
        successor = _preset_index(result, successor_id, location="successor_id")
        _require(successor != index, "invalid_successor", "successor_id", "successor must be another preset")
        if active:
            result["active_preset_id"] = result["presets"][successor]["id"]
    del result["presets"][index]
    return validate_schema3_settings(result)
