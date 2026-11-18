"""Portable directory package validation, export and preparation (stdlib only).

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
Validators never write. Export writes only its own staging directory and publishes
it to a new destination. Import preparation retains an isolated verified copy for
later activation; it never installs into a library or updates application state.
No logic/GUI modules or application state are accessed.
"""

from copy import deepcopy
from dataclasses import dataclass
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import shutil
import sys
import tempfile
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


@dataclass(frozen=True)
class PreparedImport:
    """Non-activated import result, with detached (caller-mutable) snapshots.

    source_package contains manifest Asset records and package-relative settings.
    preparation_directory is an operation-owned, still-valid directory package.
    settings has all 50 slots with native absolute paths to those verified files;
    audio_paths maps each original portable reference to its prepared Path.
    source_directory is provenance only, never needed for later playback.

    Phase 17E must revalidate preparation_directory with
    validate_package_directory, compare against source_package, and rebuild its
    paths if assets move. Neither these dictionaries nor on-disk files constitute
    an authorization to activate. Window size/global volume remain package values.
    """

    source_directory: Path
    source_package: ValidatedPackage
    preparation_directory: Path
    settings: dict
    audio_paths: dict[str, Path]


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


def _check_directory_chain(path):
    for parent in reversed((path, *path.parents)):
        _safe_stat(parent, directory=True)


def _source_path(value, base):
    _require(type(value) is str and bool(value) and "\0" not in value,
             "source", "buttons.paths", "expected nonempty source path string")
    path = Path(value)
    _require(".." not in path.parts, "source", value, "parent traversal forbidden")
    if not path.is_absolute():
        _require(base is not None and not path.drive and not path.root,
                 "source", value, "relative sources require explicit source_base")
        path = base / path
    _check_directory_chain(path.parent)
    info = _safe_stat(path)
    _require(path.suffix.lower() in (".mp3", ".wav"),
             "extension", str(path), "expected MP3 or WAV source")
    return path.resolve(), info


def _copy_asset(source, target, before, remaining, *, on_created=None):
    """Exclusive streamed copy, detecting source replacement/growth/modification."""
    _check_directory_chain(source.parent)
    _require(_identity(_safe_stat(source)) == _identity(before),
             "changed", str(source), "source changed before copying")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    digest, count = hashlib.sha256(), 0
    with os.fdopen(os.open(source, flags), "rb") as incoming, target.open("xb") as outgoing:
        if on_created is not None:
            on_created(target, os.fstat(outgoing.fileno()))
        _require(_identity(os.fstat(incoming.fileno())) == _identity(before),
                 "changed", str(source), "source replaced before copying")
        while True:
            chunk = incoming.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            count += len(chunk)
            _require(count <= min(MAX_ASSET_BYTES, remaining, before.st_size),
                     "limit", str(source), "source grew or byte limit exceeded")
            outgoing.write(chunk)
            digest.update(chunk)
        outgoing.flush()
        os.fsync(outgoing.fileno())
        _require(count == before.st_size and
                 _identity(os.fstat(incoming.fileno())) == _identity(before) and
                 _identity(_safe_stat(source)) == _identity(before),
                 "changed", str(source), "source changed during copying")
    # Independent source reread also detects mutations that preserve size/mtime.
    _check_directory_chain(source.parent)
    verified_size, verified_digest = _read_file(source, before.st_size, digest=True)
    _require(verified_size == count and verified_digest == digest.hexdigest(),
             "changed", str(source), "source verification failed")
    return count, digest.hexdigest()


def _publish_directory(staging, destination):
    """Atomic no-replace rename. Fail closed on unsupported OS/filesystem APIs."""
    if os.name == "nt":
        # Windows rename fails when any destination entry already exists.
        os.rename(staging, destination)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(staging), os.fsencode(destination), 4)  # RENAME_EXCL
    else:
        raise PackageValidationError("publication", str(destination), "atomic no-replace rename unavailable")
    if result:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), str(destination))


def _write_export_json(path, value, *, on_created=None):
    encoded = (json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, indent=2) + "\n").encode("utf-8")
    _require(len(encoded) <= MAX_JSON_BYTES, "limit", path.name, "JSON byte limit exceeded")
    with path.open("xb") as stream:
        if on_created is not None:
            on_created(path, os.fstat(stream.fileno()))
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def export_package_directory(settings, destination, *, source_base=None):
    """Export a supplied snapshot; return its detached ValidatedPackage.

    Destination and optional source_base must be absolute native paths with no
    parent-traversal components. Destination's parent must already exist. Relative
    audio paths require source_base (explicitly pass the playback CWD to preserve
    legacy playback semantics). Never reads active settings or changes CWD.

    All source ancestry must be free of symlinks/reparse points. Canonical paths
    and hard-link identities deduplicate sources; asset-001.wav etc. are assigned
    by first slot occurrence, not source basename. Short ASCII names avoid case,
    Unicode, reserved-name and component-length collisions without leaking paths.
    The caller controls the full destination path length; OS path-limit failures
    roll back staging. last_folder is omitted after checking it is a string.
    All other Phase 17B settings checks apply unchanged, including unknown keys.

    Raises PackageValidationError for validation or filesystem failures. A unique
    sibling staging directory is validated and atomically renamed without replace
    (Windows rename, Linux renameat2, macOS renamex_np). Unsupported publication
    APIs/filesystems fail closed. Existing/racing destinations are never merged or
    removed. Only this operation's staging is cleaned on failure. Parent directories
    must be stable/trusted: path-based checks are not a sandbox against concurrent
    hostile parent replacement. Atomic visibility does not promise crash durability.
    """
    staging = None
    try:
        destination = Path(destination)
        _require(destination.is_absolute() and ".." not in destination.parts and
                 destination.name not in ("", ".", ".."),
                 "destination", str(destination), "expected absolute destination without traversal")
        _check_directory_chain(destination.parent)
        _require(not os.path.lexists(destination), "destination", str(destination), "destination already exists")
        base = None
        if source_base is not None:
            base = Path(source_base)
            _require(base.is_absolute() and ".." not in base.parts,
                     "source", str(base), "expected absolute source_base without traversal")
            _check_directory_chain(base)
        snapshot = deepcopy(settings)
        _require(type(snapshot) is dict, "type", "settings", "expected JSON object")
        if "last_folder" in snapshot:
            _require(type(snapshot["last_folder"]) is str, "type", "last_folder", "expected string")
            snapshot.pop("last_folder")
        buttons = snapshot.get("buttons")
        _require(type(buttons) is dict and type(buttons.get("paths")) is list and
                 len(buttons["paths"]) == 50, "slots", "buttons.paths", "expected exactly 50 paths")
        original_paths = buttons["paths"]
        _require(all(type(p) is str for p in original_paths), "type", "buttons.paths", "expected strings")
        buttons["paths"] = [""] * 50
        # Validate all non-path settings before reading source files or staging.
        validate_package_data({"package_version": PACKAGE_VERSION, "assets": []}, snapshot)
        sources, identities, declared_total = [], {}, 0
        for index, value in enumerate(original_paths):
            if not value:
                continue
            source, info = _source_path(value, base)
            identity = (info.st_dev, info.st_ino) if info.st_ino else os.path.normcase(str(source))
            if identity not in identities:
                _require(len(sources) < MAX_ASSETS, "limit", "assets", "asset count exceeded")
                _require(info.st_size <= MAX_ASSET_BYTES, "limit", str(source), "asset byte limit exceeded")
                declared_total += info.st_size
                _require(declared_total <= MAX_TOTAL_BYTES, "limit", "assets", "total byte limit exceeded")
                name = validate_asset_path(f"Musik/asset-{len(sources) + 1:03d}{source.suffix.lower()}")
                identities[identity] = name
                sources.append((source, info, name))
            buttons["paths"][index] = identities[identity]
        staging = Path(tempfile.mkdtemp(prefix=".jingleplayer-export-", dir=destination.parent))
        (staging / "Musik").mkdir()
        entries, copied_total = [], 0
        for source, info, name in sources:
            count, digest = _copy_asset(source, staging.joinpath(*name.split("/")), info,
                                        MAX_TOTAL_BYTES - copied_total)
            copied_total += count
            entries.append({"path": name, "size": count, "sha256": digest})
        manifest = {"package_version": PACKAGE_VERSION, "assets": entries}
        validate_package_data(manifest, snapshot)
        _write_export_json(staging / MANIFEST_NAME, manifest)
        _write_export_json(staging / SETTINGS_NAME, snapshot)
        validated = validate_package_directory(staging)
        _check_directory_chain(destination.parent)
        _publish_directory(staging, destination)
        staging = None
        return validated
    except PackageValidationError:
        raise
    except (OSError, TypeError, ValueError, RecursionError) as error:
        raise PackageValidationError("export", str(destination), str(error)) from error
    finally:
        if staging is not None:
            shutil.rmtree(staging)


def _preparation_path(value, location):
    path = Path(value)
    _require(path.is_absolute() and ".." not in path.parts,
             "path", location, "expected absolute native path without parent traversal")
    _check_directory_chain(path)
    return path


def _directory_identity(path):
    info = _safe_stat(path, directory=True)
    return info.st_dev, info.st_ino


def _check_preparation_owner(root, owner):
    _check_directory_chain(root)
    _require(_directory_identity(root) == owner, "ownership", str(root),
             "preparation directory replaced; refusing access or cleanup")


def _cleanup_preparation(root, owner, created):
    """Fail closed on replacement, links, or unexpected content; no broad rmtree."""
    _check_preparation_owner(root, owner)
    files, directories = [], []

    def inspect(directory):
        for child in directory.iterdir():
            relative = child.relative_to(root).as_posix()
            info = child.lstat()
            is_directory = stat.S_ISDIR(info.st_mode)
            info = _safe_stat(child, directory=is_directory)
            _require(created.get(relative) == (info.st_dev, info.st_ino, is_directory),
                     "ownership", str(child), "unexpected entry; refusing cleanup")
            if is_directory:
                inspect(child)
                directories.append(child)
            else:
                files.append(child)

    inspect(root)
    for path in files:
        _check_preparation_owner(root, owner)
        _check_directory_chain(path.parent)
        info = _safe_stat(path)
        _require(created.get(path.relative_to(root).as_posix()) == (info.st_dev, info.st_ino, False),
                 "ownership", str(path), "file replaced; refusing cleanup")
        path.unlink()
    for path in directories:
        _check_preparation_owner(root, owner)
        _check_directory_chain(path)
        info = _safe_stat(path, directory=True)
        _require(created.get(path.relative_to(root).as_posix()) == (info.st_dev, info.st_ino, True),
                 "ownership", str(path), "directory replaced; refusing cleanup")
        path.rmdir()
    _check_preparation_owner(root, owner)
    root.rmdir()


def prepare_package_import(package_directory, staging_root):
    """Validate/copy a package into isolation; return PreparedImport, never activate.

    Both arguments must be explicit absolute existing directories without '..',
    symlinks or reparse points anywhere in their ancestry. staging_root must not
    equal or lie inside the source package. No CWD/home/settings are consulted.
    A unique private .jingleplayer-import-* directory (mkdtemp) is retained on
    success. Existing staging content is never merged, overwritten or removed.

    The entire source is validated before any creation. Copies reuse streamed
    size/hash/mutation checks, additionally compare against the initial manifest,
    then revalidate both the prepared package and source snapshot before return.
    Original relative metadata is retained on disk for subsequent revalidation;
    only the returned settings copy maps assignments to native absolute files.

    Failure raises PackageValidationError and cleans only the operation's known
    paths after verifying its root identity and checking for unexpected entries.
    Unsafe replacement/content or a cleanup I/O error fails closed, leaves the
    directory for inspection and reports its location with code 'cleanup'.
    No marker is inserted, preserving the exact version-1 package contract.

    This is preparation, not atomic activation or crash-durable installation.
    Restrictive creation permissions and repeated no-link/identity/hash checks
    detect ordinary races. As with the existing validators/exporter, callers must
    control staging_root and keep ancestors stable: path-based stdlib checks are
    not an OS sandbox against a hostile same-user process swapping directories
    between a check and an open/unlink. Concurrent source edits cause failure if
    observed; edits after the final check cannot invalidate the independent copy.
    Phase 17E must revalidate the retained directory immediately before use.
    """
    prepared, owner = None, None
    created, allowed_dirs = {}, {"Musik"}
    try:
        source = _preparation_path(package_directory, "package_directory")
        staging = _preparation_path(staging_root, "staging_root")
        _require(not staging.resolve().is_relative_to(source.resolve()),
                 "layout", str(staging), "staging_root must be outside source package")
        validated = validate_package_directory(source)
        # Respect configured limits even if they are tightened by a caller/test.
        _require(len(validated.assets) <= MAX_ASSETS, "limit", "assets", "asset count exceeded")
        _require(sum(a.size for a in validated.assets) <= MAX_TOTAL_BYTES,
                 "limit", "assets", "total byte limit exceeded")
        for asset in validated.assets:
            parts = asset.path.split("/")
            allowed_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
        staging_owner = _directory_identity(staging)
        _check_directory_chain(staging)
        prepared = Path(tempfile.mkdtemp(prefix=".jingleplayer-import-", dir=staging))
        owner = _directory_identity(prepared)

        def record_creation(path, info):
            created[path.relative_to(prepared).as_posix()] = (
                info.st_dev, info.st_ino, stat.S_ISDIR(info.st_mode))

        _require(_directory_identity(staging) == staging_owner,
                 "ownership", str(staging), "staging_root changed during creation")
        for relative in sorted(allowed_dirs, key=lambda p: (p.count("/"), p)):
            _check_preparation_owner(prepared, owner)
            target = prepared.joinpath(*relative.split("/"))
            _check_directory_chain(target.parent)
            target.mkdir()  # Exclusive creation; no merging with a racing entry.
            record_creation(target, _safe_stat(target, directory=True))
        total, mapping = 0, {}
        for asset in validated.assets:
            _check_preparation_owner(prepared, owner)
            incoming = source.joinpath(*asset.path.split("/"))
            target = prepared.joinpath(*asset.path.split("/"))
            _check_directory_chain(incoming.parent)
            _check_directory_chain(target.parent)
            before = _safe_stat(incoming)
            _require(before.st_size == asset.size and before.st_size <= MAX_ASSET_BYTES,
                     "size", asset.path, "source size changed or limit exceeded")
            size, digest = _copy_asset(incoming, target, before, MAX_TOTAL_BYTES - total,
                                       on_created=record_creation)
            _require(size == asset.size and digest == asset.sha256,
                     "integrity", asset.path, "copied bytes differ from validated manifest")
            total += size
            mapping[asset.path] = target
        manifest = {"package_version": PACKAGE_VERSION, "assets": [
            {"path": a.path, "size": a.size, "sha256": a.sha256} for a in validated.assets]}
        for name, contents in ((MANIFEST_NAME, manifest), (SETTINGS_NAME, validated.settings)):
            _check_preparation_owner(prepared, owner)
            _write_export_json(prepared / name, contents, on_created=record_creation)
        _check_preparation_owner(prepared, owner)
        _require(validate_package_directory(prepared) == validated,
                 "integrity", str(prepared), "prepared snapshot differs from source")
        _require(validate_package_directory(source) == validated,
                 "changed", str(source), "source package changed during preparation")
        _check_preparation_owner(prepared, owner)
        settings = deepcopy(validated.settings)
        settings["buttons"]["paths"] = [str(mapping[p]) if p else ""
                                            for p in settings["buttons"]["paths"]]
        result = PreparedImport(source, validated, prepared, settings, mapping)
        prepared = None  # Transfer ownership to the caller; no activation.
        return result
    except (OSError, TypeError, ValueError, RecursionError) as error:
        if prepared is not None:
            try:
                _cleanup_preparation(prepared, owner, created)
            except (OSError, ValueError) as cleanup_error:
                raise PackageValidationError("cleanup", str(prepared),
                                             f"preparation failed ({error}); cleanup refused/failed: {cleanup_error}") from error
        if isinstance(error, PackageValidationError):
            raise
        raise PackageValidationError("preparation", str(package_directory), str(error)) from error
