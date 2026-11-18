"""Read-only portable directory package contract, version 1 (stdlib only).

Root contains exactly jingleplayer_package.json, jingleplayer_settings.json and
optionally Musik/ (required by nonempty assignments). No unrelated files or
unreferenced asset directories are accepted, except an empty Musik/ directory.
Manifest JSON is exactly::

    {"package_version": 1, "assets": [
        {"path": "Musik/example.wav", "size": 123, "sha256": "<64 hex digits>"}
    ]}

Settings use schema_version 2 and exactly the application fields documented in
validate_settings. Unknown fields are rejected, including unknown button fields.
last_folder may be absent or the empty string only. A later importer must retain
local window_size and global volume; validation does not activate anything.
Every manifest asset must be referenced, every nonempty assignment must match an
asset exactly; repeated slot references are allowed, including hidden slots.

Paths are unchanged Unicode strings using forward slashes, rooted at Musik/.
Both composed and decomposed Unicode are accepted, but NFC/casefold-equivalent
paths (including intermediate directories) collide. Windows-invalid names,
controls, surrogates and format characters are rejected on every host. Only
MP3/WAV extensions, case-insensitively, are allowed. No unsafe path is repaired.

Limits are package policy, not application settings limits: each JSON file <=
1 MiB, <=50 assets, <=1 GiB per asset, <=5 GiB declared total. Hashes are SHA-256.
JSON must be UTF-8 without BOM, duplicate keys or nonfinite numbers. Settings
ranges mirror PySide6 controls: height 1..10, fadeout 0..2147483647 ms, global
volume 0..100 and button dB -10..10; five rows of 0..10 with positive total.
The repository has no explicit window-size range: positive integer dimensions
are required here, with no invented upper bound. Colors are nonempty strings;
their platform-specific rendering is deliberately not interpreted without Qt.

Filesystem inspection rejects links/reparse points in root ancestry, metadata,
assets and intermediate directories; only regular files/directories are read.
It hashes in chunks and checks file identity/size/timestamps around reads.
This is not an OS sandbox against a concurrent hostile process replacing parent
directories; callers must inspect a stable package, not concurrently mutate it.
No logic/GUI modules are imported and no settings, files or global state written.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata

PACKAGE_VERSION = 1
MANIFEST_NAME = "jingleplayer_package.json"
SETTINGS_NAME = "jingleplayer_settings.json"
MAX_JSON_BYTES = 1024 * 1024
MAX_ASSETS = 50
MAX_ASSET_BYTES = 1024 ** 3
MAX_TOTAL_BYTES = 5 * 1024 ** 3
HASH_CHUNK_BYTES = 64 * 1024


class PackageValidationError(ValueError):
    """Invalid package; code and location are stable machine-readable context."""

    def __init__(self, code, location, message):
        self.code = code
        self.location = location
        super().__init__(f"{location}: {message}")


@dataclass(frozen=True)
class Asset:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ValidatedPackage:
    """Validated snapshot; settings is a detached JSON dictionary."""

    assets: tuple[Asset, ...]
    settings: dict


def _require(condition, code, location, message):
    if not condition:
        raise PackageValidationError(code, location, message)


def _integer(value, low, high, location):
    _require(type(value) is int and value >= low and (high is None or value <= high),
             "range", location, f"expected integer in {low}..{high}")


def _keys(value, required, optional, location):
    _require(type(value) is dict, "type", location, "expected JSON object")
    _require(set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
             "fields", location, "missing or unknown fields")


def _collision_key(path):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", path).casefold())


def validate_asset_path(path):
    """Validate portable MP3/WAV syntax without host-dependent path parsing."""
    _require(type(path) is str and bool(path), "path", "asset path", "expected nonempty string")
    _require("\\" not in path, "path", path, "backslashes forbidden")
    parts = path.split("/")
    _require(len(parts) >= 2 and parts[0] == "Musik", "path", path, "must begin Musik/")
    for part in parts:
        _require(part not in ("", ".", "..") and not part.endswith((".", " ")),
                 "path", path, "empty, dot or trailing dot/space component")
        _require(not any(c in '<>:"|?*' or unicodedata.category(c).startswith("C") for c in part),
                 "path", path, "invalid or control character")
        stem = part.split(".")[0].rstrip(" ").upper()
        _require(not re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]", stem),
                 "path", path, "reserved Windows device name")
    _require(parts[-1].rsplit(".", 1)[-1].lower() in ("mp3", "wav") and "." in parts[-1],
             "extension", path, "expected MP3 or WAV")
    return path


def validate_manifest(manifest):
    """Return immutable assets after strict version/type/size/collision checks."""
    _keys(manifest, {"package_version", "assets"}, set(), "manifest")
    _integer(manifest["package_version"], PACKAGE_VERSION, PACKAGE_VERSION, "package_version")
    entries = manifest["assets"]
    _require(type(entries) is list and len(entries) <= MAX_ASSETS,
             "limit", "assets", "expected list with at most 50 assets")
    assets, names, total = [], {}, 0
    for entry in entries:
        _keys(entry, {"path", "size", "sha256"}, set(), "asset")
        path = validate_asset_path(entry["path"])
        _integer(entry["size"], 0, MAX_ASSET_BYTES, path)
        digest = entry["sha256"]
        _require(type(digest) is str and re.fullmatch(r"[0-9a-fA-F]{64}", digest) is not None,
                 "hash", path, "expected 64 hexadecimal SHA-256 characters")
        # Include directory prefixes to catch aliases and file/directory conflicts.
        parts = path.split("/")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = _collision_key(prefix)
            kind = "file" if index == len(parts) else "directory"
            previous = names.get(key)
            _require(previous is None or (kind == "directory" and previous == (prefix, kind)),
                     "collision", path, "duplicate or ambiguous asset/directory path")
            names[key] = (prefix, kind)
        total += entry["size"]
        _require(total <= MAX_TOTAL_BYTES, "limit", "assets", "total declared bytes exceeded")
        assets.append(Asset(path, entry["size"], digest.lower()))
    return tuple(assets)


def validate_settings(settings, assets):
    """Validate schema-2 package settings and return a detached JSON snapshot.

    Required top-level fields: schema_version, buttons, button_height,
    fadeout_duration, window_size, volume. Optional last_folder must be empty.
    Buttons has exactly texts/colors/paths/volumes (50 each) and per_row (5).
    """
    _keys(settings, {"schema_version", "buttons", "button_height", "fadeout_duration",
                     "window_size", "volume"}, {"last_folder"}, "settings")
    _integer(settings["schema_version"], 2, 2, "schema_version")
    _require("last_folder" not in settings or settings["last_folder"] == "",
             "local_metadata", "last_folder", "must be absent or empty")
    buttons = settings["buttons"]
    _keys(buttons, {"texts", "colors", "paths", "volumes", "per_row"}, set(), "buttons")
    for name in ("texts", "colors", "paths", "volumes"):
        values = buttons[name]
        _require(type(values) is list and len(values) == 50, "slots", name, "expected exactly 50 entries")
        for index, value in enumerate(values):
            location = f"buttons.{name}[{index}]"
            if name == "volumes":
                _integer(value, -10, 10, location)
            else:
                _require(type(value) is str and not any(0xD800 <= ord(c) <= 0xDFFF or c == "\0" for c in value),
                         "type", location, "expected Unicode string without NUL/surrogates")
                if name == "colors":
                    _require(bool(value), "type", location, "color must not be empty")
    rows = buttons["per_row"]
    _require(type(rows) is list and len(rows) == 5, "layout", "per_row", "expected five rows")
    for value in rows:
        _integer(value, 0, 10, "per_row")
    _require(sum(rows) > 0, "layout", "per_row", "at least one visible button required")
    for name, low, high in (("button_height", 1, 10), ("fadeout_duration", 0, 2147483647),
                            ("volume", 0, 100)):
        _integer(settings[name], low, high, name)
    size = settings["window_size"]
    _require(type(size) is list and len(size) == 2, "type", "window_size", "expected two dimensions")
    for value in size:
        _integer(value, 1, None, "window_size")
    references = set()
    for path in buttons["paths"]:
        if path:
            references.add(validate_asset_path(path))
    _require(references == {asset.path for asset in assets}, "references", "buttons.paths",
             "manifest assets and nonempty assignments must match exactly")
    return json.loads(json.dumps(settings, ensure_ascii=False))


def validate_package_data(manifest, settings):
    """Pure validation; accepts decoded JSON values and enforces JSON byte limits."""
    for name, value in ((MANIFEST_NAME, manifest), (SETTINGS_NAME, settings)):
        try:
            size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError, RecursionError) as error:
            raise PackageValidationError("json", name, "not valid JSON data") from error
        _require(size <= MAX_JSON_BYTES, "limit", name, "JSON byte limit exceeded")
    assets = validate_manifest(manifest)
    return ValidatedPackage(assets, validate_settings(settings, assets))


def _safe_stat(path, directory=False):
    info = path.lstat()
    _require(not stat.S_ISLNK(info.st_mode) and not
             (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)),
             "link", str(path), "symlinks/reparse points forbidden")
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
             "file_type", str(path), "expected directory" if directory else "expected regular file")
    return info


def _identity(info):
    # Windows lstat/fstat creation-time reporting differs on some Python builds.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read_file(path, limit, digest=False):
    before = _safe_stat(path)
    _require(before.st_size <= limit, "limit", str(path), "file size limit exceeded")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        _require(_identity(os.fstat(stream.fileno())) == _identity(before),
                 "changed", str(path), "file changed before reading")
        result = hashlib.sha256() if digest else bytearray()
        count = 0
        while True:
            chunk = stream.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            count += len(chunk)
            _require(count <= limit, "limit", str(path), "file grew beyond limit")
            if digest:
                result.update(chunk)
            else:
                result.extend(chunk)
        _require(_identity(os.fstat(stream.fileno())) == _identity(before)
                 and _identity(_safe_stat(path)) == _identity(before),
                 "changed", str(path), "file changed while reading")
    return (count, result.hexdigest()) if digest else bytes(result)


def _json_file(path):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "json", str(path), "duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise PackageValidationError("json", str(path), f"nonfinite JSON number: {value}")

    try:
        return json.loads(_read_file(path, MAX_JSON_BYTES).decode("utf-8"),
                          object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, PackageValidationError):
            raise
        raise PackageValidationError("json", str(path), "malformed UTF-8 JSON") from error


def validate_package_directory(root):
    """Read and hash a stable existing directory, without writing or activating it."""
    root = Path(os.path.abspath(os.fspath(root)))
    try:
        for parent in reversed((root, *root.parents)):
            _safe_stat(parent, directory=True)
        manifest = _json_file(root / MANIFEST_NAME)
        settings = _json_file(root / SETTINGS_NAME)
        package = validate_package_data(manifest, settings)
        expected_files = {MANIFEST_NAME, SETTINGS_NAME} | {a.path for a in package.assets}
        expected_dirs = {"Musik"}  # Empty Musik is permitted for an empty board.
        for asset in package.assets:
            parts = asset.path.split("/")
            expected_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
        seen_files = set()

        def inspect(directory):
            for child in sorted(directory.iterdir(), key=lambda p: p.name):
                relative = child.relative_to(root).as_posix()
                info = child.lstat()
                is_directory = stat.S_ISDIR(info.st_mode)
                _safe_stat(child, directory=is_directory)
                _require(child.resolve().is_relative_to(root.resolve()),
                         "containment", relative, "entry escapes root")
                if is_directory:
                    _require(relative in expected_dirs, "extra", relative, "unexpected directory")
                    inspect(child)
                else:
                    _require(relative in expected_files, "extra", relative, "unexpected file")
                    seen_files.add(relative)

        inspect(root)
        _require(seen_files == expected_files, "missing", str(root), "missing package files")
        for asset in package.assets:
            path = root.joinpath(*asset.path.split("/"))
            for parent in path.parents:
                _safe_stat(parent, directory=True)
                if parent == root:
                    break
            size, digest = _read_file(path, asset.size, digest=True)
            _require(size == asset.size, "size", asset.path, "incorrect asset byte count")
            _require(digest == asset.sha256, "hash", asset.path, "SHA-256 mismatch")
        return package
    except OSError as error:
        raise PackageValidationError("filesystem", str(root), str(error)) from error
