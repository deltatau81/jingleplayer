"""Version-3 ZIP media packages. Legacy directory packages remain independent.

No application state or data-directory discovery: the caller supplies the active
settings path. Private staging, bounded streamed copies, verified hashes and the
existing settings lock/token protocol are reused. Trusted stable parent folders
are required; this is not a sandbox against hostile concurrent directory swaps.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
from uuid import uuid4
import zipfile
import zlib

import jingleplayer_packages as legacy
import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage
from jingleplayer_audio_pools import pool_file_path

PACKAGE_VERSION = 3
MANIFEST_NAME = "manifest.json"
MAX_ENTRIES = 4096
MAX_JSON_BYTES = 1024 * 1024
MAX_ASSET_BYTES = 1024 ** 3
MAX_TOTAL_BYTES = 5 * 1024 ** 3
MAX_IMAGE_BYTES = 32 * 1024 ** 2
MAX_COMPRESSION_RATIO = 200
CHUNK = 64 * 1024
PackageValidationError = legacy.PackageValidationError
require = legacy._require


@dataclass(frozen=True)
class MediaAsset:
    path: str
    size: int
    sha256: str
    kind: str


@dataclass(frozen=True)
class MediaPackage:
    name: str
    settings: dict
    assets: tuple
    archive_sha256: str


class _OwnedTree:
    def __init__(self, parent, prefix):
        legacy._check_directory_chain(parent)
        self.root = Path(tempfile.mkdtemp(dir=parent, prefix=prefix))
        self.owner = legacy._directory_identity(self.root)
        self.created = {}

    def record(self, path):
        info = path.lstat()
        self.created[path.relative_to(self.root).as_posix()] = (
            info.st_dev, info.st_ino, stat.S_ISDIR(info.st_mode))

    def directory(self, name):
        path = self.root / name
        path.mkdir(mode=0o700)
        self.record(path)

    def open(self, relative):
        legacy._check_preparation_owner(self.root, self.owner)
        path = self.root / relative
        stream = path.open("xb")
        self.record(path)
        return stream

    def clean(self):
        legacy._cleanup_preparation(self.root, self.owner, self.created)


def _absolute(value):
    path = legacy._native_path(value)
    require(path.is_absolute() and ".." not in path.parts, "path", str(path),
            "explicit absolute native path without traversal required")
    return path


def _json(raw):
    require(len(raw) <= MAX_JSON_BYTES, "limit", MANIFEST_NAME, "manifest too large")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "json", key, "duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise PackageValidationError("json", MANIFEST_NAME, "nonfinite number")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _encoded(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
    require(len(raw) <= MAX_JSON_BYTES, "limit", MANIFEST_NAME, "manifest too large")
    return raw


def _component(name):
    require(type(name) is str and name not in ("", ".", "..") and len(name) <= 180,
            "path", str(name), "invalid component")
    require(not name.endswith((".", " ")) and not any(
        c in '/\\<>:"|?*' or unicodedata.category(c).startswith("C") for c in name),
        "path", name, "unsafe filename")
    require(not re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]",
                             name.split(".")[0].rstrip(" ").upper()),
            "path", name, "reserved Windows filename")
    return name


def _asset_path(path, kind):
    require(type(path) is str, "path", "asset", "expected path string")
    parts = path.split("/")
    folder = "audio" if kind == "audio" else "backgrounds"
    require(len(parts) == 2 and parts[0] == folder, "path", path, "invalid media root or nesting")
    _component(parts[1])
    extensions = (".mp3", ".wav") if kind == "audio" else (".png", ".jpg", ".jpeg")
    require(Path(parts[1]).suffix.lower() in extensions, "extension", path, "unsupported media extension")
    return path


def _refs(document):
    for preset in document["presets"]:
        for path in preset["buttons"]["paths"]:
            if path:
                yield path, "audio"
        for pool in preset.get("audio_pools", {}).values():
            for path in pool["audio_pool"]:
                yield path, "audio"
            yield pool["selected_audio"], "audio"
        if preset.get("background_image"):
            yield preset["background_image"], "background"


def _map(document, transform):
    result = deepcopy(document)
    for preset in result["presets"]:
        preset["buttons"]["paths"] = [transform(p, "audio") if p else "" for p in preset["buttons"]["paths"]]
        for pool in preset.get("audio_pools", {}).values():
            pool["audio_pool"] = [transform(p, "audio") for p in pool["audio_pool"]]
            pool["selected_audio"] = transform(pool["selected_audio"], "audio")
        if preset.get("background_image"):
            preset["background_image"] = transform(preset["background_image"], "background")
    return result


def validate_manifest(value):
    legacy._keys(value, {"package_version", "name", "settings", "assets"}, set(), "manifest")
    require(type(value["package_version"]) is int and value["package_version"] == PACKAGE_VERSION,
            "version", "package_version", "expected package version 3")
    presets.validate_preset_name(value["name"])
    document = presets.validate_schema3_settings(value["settings"])
    require(document["last_folder"] == "", "path", "last_folder", "portable global folder must be empty")
    entries = value["assets"]
    require(type(entries) is list and len(entries) + 1 <= MAX_ENTRIES, "limit", "assets", "too many assets")
    assets, names, total = [], set(), 0
    for entry in entries:
        legacy._keys(entry, {"path", "kind", "size", "sha256"}, set(), "asset")
        require(type(entry["kind"]) is str and entry["kind"] in ("audio", "background"), "type", "kind", "invalid media kind")
        path = _asset_path(entry["path"], entry["kind"])
        key = legacy._collision_key(path)
        require(key not in names, "collision", path, "duplicate or Unicode/case-equivalent asset")
        names.add(key)
        limit = MAX_IMAGE_BYTES if entry["kind"] == "background" else MAX_ASSET_BYTES
        legacy._integer(entry["size"], 0, limit, path)
        require(type(entry["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]),
                "hash", path, "invalid SHA256")
        total += entry["size"]
        require(total <= MAX_TOTAL_BYTES, "limit", "assets", "total media limit exceeded")
        assets.append(MediaAsset(**entry))
    referenced = set(_refs(document))
    require(referenced == {(a.path, a.kind) for a in assets}, "reference", "settings", "missing/unreferenced/wrong-kind media")
    for path, kind in referenced:
        _asset_path(path, kind)
    return document, tuple(assets)


def _image(path):
    # In-memory reader cannot retain a Windows file handle in an error traceback.
    _image_bytes(legacy._read_file(path, MAX_IMAGE_BYTES))


def _filename(raw, used):
    suffix = Path(raw).suffix.lower()
    stem = unicodedata.normalize("NFC", Path(raw).stem)
    stem = "".join("_" if c in '/\\<>:"|?*' or unicodedata.category(c).startswith("C") else c for c in stem).strip(" .")[:90] or "media"
    while len(stem.encode("utf-8")) > 160:
        stem = stem[:-1]
    try:
        _component(stem + suffix)
    except PackageValidationError:
        stem = "media"
    name, number = stem + suffix, 2
    while legacy._collision_key(name) in used:
        name = f"{stem}-{number}{suffix}"
        number += 1
    used.add(legacy._collision_key(name))
    return name


def export_archive(document, destination, *, source_base, name="Soundboard"):
    """Export every preset to a new ZIP, publishing atomically without overwrite."""
    tree = None
    try:
        destination, base = _absolute(destination), _absolute(source_base)
        legacy._check_directory_chain(destination.parent)
        require(not os.path.lexists(destination), "destination", str(destination), "destination exists")
        snapshot = presets.validate_schema3_settings(document)
        presets.validate_preset_name(name)
        tree = _OwnedTree(destination.parent, ".jingleplayer-export3-")
        tree.directory("audio")
        tree.directory("backgrounds")
        mapping, names, assets, total = {}, {"audio": set(), "background": set()}, [], 0
        # Duplicate references are copied once; distinct paths retain their names.
        for raw, kind in dict.fromkeys(_refs(snapshot)):
            source = pool_file_path(raw, base)
            require(".." not in source.parts, "path", raw, "source traversal is ambiguous")
            legacy._check_directory_chain(source.parent)
            before = legacy._safe_stat(source)
            limit = MAX_IMAGE_BYTES if kind == "background" else MAX_ASSET_BYTES
            require(before.st_size <= limit and total + before.st_size <= MAX_TOTAL_BYTES,
                    "limit", raw, "media size limit exceeded")
            folder = "audio" if kind == "audio" else "backgrounds"
            relative = folder + "/" + _filename(str(source), names[kind])
            _asset_path(relative, kind)
            count, digest = legacy._copy_asset(source, tree.root / relative, before, MAX_TOTAL_BYTES - total,
                                               on_created=lambda path, info: tree.record(path))
            if kind == "background":
                _image(tree.root / relative)
            assets.append(MediaAsset(relative, count, digest, kind))
            require(len(assets) + 1 <= MAX_ENTRIES, "limit", "assets", "too many media files")
            mapping[(raw, kind)] = relative
            total += count
        portable = _map(snapshot, lambda raw, kind: mapping[(raw, kind)])
        portable["last_folder"] = ""
        manifest = {"package_version": PACKAGE_VERSION, "name": name, "settings": portable,
                    "assets": [vars(asset) for asset in assets]}
        validate_manifest(manifest)
        with tree.open(MANIFEST_NAME) as stream:
            stream.write(_encoded(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        with tree.open("output.zip") as outgoing:
            # Media is already compressed; STORED also avoids self-created ratio bombs.
            with zipfile.ZipFile(outgoing, "w", compression=zipfile.ZIP_STORED) as archive:
                for relative in [MANIFEST_NAME] + [a.path for a in assets]:
                    archive.write(tree.root / relative, relative)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        result = validate_archive(tree.root / "output.zip")
        archive_identity = legacy._identity(legacy._safe_stat(tree.root / "output.zip"))
        try:
            legacy._publish_directory(tree.root / "output.zip", destination)
        except OSError:
            # Exceptional native rename may already have published our own file.
            if not os.path.lexists(tree.root / "output.zip") and os.path.lexists(destination):
                legacy._check_directory_chain(destination.parent)
                if legacy._identity(legacy._safe_stat(destination)) == archive_identity:
                    destination.unlink()
            raise
        return result
    except (OSError, ValueError, TypeError, RecursionError, zipfile.BadZipFile) as error:
        if isinstance(error, PackageValidationError):
            raise
        raise PackageValidationError("export", str(destination), str(error)) from error
    finally:
        if tree is not None:
            try:
                tree.clean()
            except (OSError, ValueError) as cleanup_error:
                raise PackageValidationError("cleanup", str(tree.root),
                                             f"Export-Staging konnte nicht sicher bereinigt werden: {cleanup_error}") from cleanup_error


def _read_member(archive, info, limit, outgoing=None, *, collect=False):
    digest, count, data = hashlib.sha256(), 0, bytearray()
    with archive.open(info) as incoming:
        while True:
            chunk = incoming.read(CHUNK)
            if not chunk:
                break
            count += len(chunk)
            require(count <= limit and count <= info.file_size, "limit", info.filename, "extraction limit exceeded")
            digest.update(chunk)
            if outgoing is not None:
                outgoing.write(chunk)
            elif info.filename == MANIFEST_NAME or collect:
                data.extend(chunk)
    require(count == info.file_size, "size", info.filename, "member size mismatch")
    return count, digest.hexdigest(), bytes(data)


def _validate_archive(source, tree=None):
    source = _absolute(source)
    legacy._check_directory_chain(source.parent)
    before = legacy._safe_stat(source)
    require(before.st_size <= MAX_TOTAL_BYTES + MAX_JSON_BYTES + MAX_ENTRIES * 1024,
            "limit", str(source), "archive too large")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as raw:
        require(legacy._identity(os.fstat(raw.fileno())) == legacy._identity(before), "changed", str(source), "archive replaced")
        archive_digest = hashlib.sha256()
        hashed = 0
        for chunk in iter(lambda: raw.read(CHUNK), b""):
            hashed += len(chunk)
            require(hashed <= before.st_size, "changed", str(source), "archive grew while hashing")
            archive_digest.update(chunk)
        raw.seek(0)
        # Check the central-directory budget before ZipFile allocates its index.
        end = zipfile._EndRecData(raw)
        require(end is not None and end[zipfile._ECD_ENTRIES_TOTAL] <= MAX_ENTRIES
                and end[zipfile._ECD_SIZE] <= MAX_ENTRIES * 1024
                and end[zipfile._ECD_DISK_NUMBER] == 0 and end[zipfile._ECD_DISK_START] == 0,
                "limit", str(source), "invalid/oversized or multidisk ZIP index")
        raw.seek(0)
        with zipfile.ZipFile(raw) as archive:
            infos = archive.infolist()
            require(len(infos) <= MAX_ENTRIES, "limit", str(source), "too many ZIP entries")
            names, total = {}, 0
            for info in infos:
                require(info.orig_filename == info.filename, "path", info.orig_filename, "NUL in ZIP filename")
                if info.filename != MANIFEST_NAME:
                    parts = info.filename.split("/")
                    require(len(parts) == 2 and parts[0] in ("audio", "backgrounds"), "path", info.filename, "unexpected ZIP path")
                    _asset_path(info.filename, "audio" if parts[0] == "audio" else "background")
                key = legacy._collision_key(info.filename)
                require(key not in names, "collision", info.filename, "duplicate ZIP path")
                names[key] = info
                mode = info.external_attr >> 16
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not info.is_dir()
                        and not info.external_attr & (0x10 | 0x400),
                        "file_type", info.filename, "links/directories/devices forbidden")
                require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        "zip", info.filename, "encrypted or unsupported ZIP member")
                limit = MAX_JSON_BYTES if info.filename == MANIFEST_NAME else (
                    MAX_IMAGE_BYTES if info.filename.startswith("backgrounds/") else MAX_ASSET_BYTES)
                require(0 <= info.file_size <= limit and info.file_size <= max(1, info.compress_size) * MAX_COMPRESSION_RATIO,
                        "limit", info.filename, "size/compression ratio limit exceeded")
                total += info.file_size
                require(total <= MAX_TOTAL_BYTES + MAX_JSON_BYTES, "limit", str(source), "ZIP total too large")
            require(MANIFEST_NAME in {i.filename for i in infos}, "manifest", str(source), "missing manifest")
            manifest_info = archive.getinfo(MANIFEST_NAME)
            manifest = _json(_read_member(archive, manifest_info, MAX_JSON_BYTES)[2])
            document, assets = validate_manifest(manifest)
            require({i.filename for i in infos} == {MANIFEST_NAME} | {a.path for a in assets},
                    "reference", str(source), "unexpected or missing ZIP members")
            if tree:
                tree.directory("audio")
                tree.directory("backgrounds")
                with tree.open(MANIFEST_NAME) as output:
                    output.write(_encoded(manifest))
                    output.flush()
                    os.fsync(output.fileno())
            for asset in assets:
                info = archive.getinfo(asset.path)
                require(info.file_size == asset.size, "size", asset.path, "manifest size mismatch")
                if tree:
                    with tree.open(asset.path) as output:
                        size, digest, _ = _read_member(archive, info, asset.size, output)
                        output.flush()
                        os.fsync(output.fileno())
                else:
                    size, digest, image_data = _read_member(archive, info, asset.size, collect=asset.kind == "background")
                    if asset.kind == "background":
                        _image_bytes(image_data)
                require(digest == asset.sha256, "hash", asset.path, "SHA256 mismatch")
            require(legacy._identity(os.fstat(raw.fileno())) == legacy._identity(before)
                    and legacy._identity(legacy._safe_stat(source)) == legacy._identity(before),
                    "changed", str(source), "archive changed while reading")
    result = MediaPackage(manifest["name"], document, assets, archive_digest.hexdigest())
    if tree:
        _verify_tree(tree, result)
    return result


def _image_bytes(data):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImageReader
    require(len(data) <= MAX_IMAGE_BYTES and
            (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")),
            "image", "background", "expected bounded PNG/JPEG bytes")
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    try:
        reader.setDecideFormatFromContent(True)
        reader.setAutoTransform(True)
        require(bytes(reader.format()).lower() in (b"png", b"jpeg", b"jpg"),
                "image", "background", "unsupported image decoder")
        size = reader.size()
        require(size.isValid() and not size.isEmpty() and max(size.width(), size.height()) <= 16384
                and size.width() * size.height() <= 40_000_000 and not reader.read().isNull(),
                "image", "background", "invalid, corrupt or oversized PNG/JPEG")
    finally:
        # Tracebacks cross from package workers to the GUI. Destroy decoder and
        # its QObject device here, in their creating thread, even on rejection.
        del reader
        buffer.close()
        del buffer


def validate_archive(source):
    """Read-only validation, including decompressed bytes, hashes and image decode."""
    try:
        return _validate_archive(source)
    except (OSError, ValueError, TypeError, RecursionError, zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error) as error:
        if isinstance(error, PackageValidationError):
            raise
        raise PackageValidationError("archive", str(source), str(error)) from error


def _verify_tree(tree, package):
    legacy._check_preparation_owner(tree.root, tree.owner)
    expected = {MANIFEST_NAME} | {a.path for a in package.assets}
    seen = set()
    for folder in tree.root.iterdir():
        if folder.name in ("audio", "backgrounds"):
            legacy._safe_stat(folder, directory=True)
            for path in folder.iterdir():
                legacy._safe_stat(path)
                seen.add(path.relative_to(tree.root).as_posix())
        else:
            legacy._safe_stat(folder)
            seen.add(folder.name)
    require(seen == expected, "integrity", str(tree.root), "installed inventory changed")
    manifest = legacy._json_file(tree.root / MANIFEST_NAME)
    document, assets = validate_manifest(manifest)
    require(document == package.settings and assets == package.assets and manifest["name"] == package.name,
            "integrity", MANIFEST_NAME, "installed manifest changed")
    for asset in package.assets:
        path = tree.root / asset.path
        require(legacy._read_file(path, asset.size, digest=True) == (asset.size, asset.sha256),
                "hash", asset.path, "installed media changed")
        if asset.kind == "background":
            _image(path)


def import_archive(source, settings_path, *, expected=None, confirmed=None, legacy_normalizer=None):
    """Append all presets with fresh IDs/names; retain local global settings.

    Known precommit failures clean owned media. Unknown/committed outcomes retain
    media and report ActivationError rather than deleting possibly live files.
    Recovery snapshots are retained deliberately; no automatic restoration.
    """
    tree = recovery = installed = None
    attempted = False
    try:
        settings_path = _absolute(settings_path)
        legacy._check_directory_chain(settings_path.parent)
        token = expected or storage.load_preset_settings(settings_path, legacy_normalizer=legacy_normalizer)
        require(isinstance(token, storage.LoadedPresetSettings) and token.path == settings_path and token.original_bytes is not None,
                "settings", str(settings_path), "existing settings token required")
        roots = [settings_path.parent / name for name in ("import-staging", "imported_soundboards", "import-recovery")]
        for root in roots:
            if not os.path.lexists(root):
                root.mkdir(mode=0o700)
            legacy._check_directory_chain(root)
        tree = _OwnedTree(roots[0], "media3-")
        package = _validate_archive(source, tree)
        require(confirmed is None or package == confirmed, "changed", str(source), "package differs from confirmed preview")
        slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", package.name).encode("ascii", "ignore").decode().lower()).strip("-")[:48] or "soundboard"
        installed = roots[1] / (slug + "-" + uuid4().hex)
        incoming = _map(package.settings, lambda path, kind: str(installed.joinpath(*path.split("/"))))
        receiver = presets.validate_schema3_settings(token.data)
        id_map = {}
        for preset in incoming["presets"]:
            name, number = preset["name"], 2
            used = {presets._name_key(p["name"]) for p in receiver["presets"]}
            while presets._name_key(name) in used:
                name = f"{preset['name']} ({number})"
                number += 1
            identity = presets._fresh_preset_id(receiver)
            id_map[preset["id"].lower()] = identity
            receiver["presets"].append({**preset, "id": identity, "name": name})
        receiver["active_preset_id"] = id_map[incoming["active_preset_id"].lower()]
        receiver = presets.validate_schema3_settings(receiver)
        recovery = roots[2] / ("media3-" + uuid4().hex)
        recovery.mkdir(mode=0o700)
        recovery_owner = legacy._directory_identity(recovery)
        legacy._write_recovery_bytes(recovery / legacy.SETTINGS_NAME, token.original_bytes)
        metadata = {"recovery_version": 1, "settings_path": str(settings_path),
                    "settings_size": len(token.original_bytes),
                    "settings_sha256": hashlib.sha256(token.original_bytes).hexdigest(),
                    "proposed_settings_sha256": hashlib.sha256(json.dumps(receiver, ensure_ascii=False, indent=4, allow_nan=False).encode("utf-8")).hexdigest(),
                    "library_directory": str(installed)}
        legacy._write_export_json(recovery / "recovery.json", metadata)
        try:
            legacy._publish_directory(tree.root, installed)
        except OSError:
            if not os.path.lexists(tree.root) and os.path.lexists(installed):
                if legacy._directory_identity(installed) == tree.owner:
                    tree.root = installed
            raise
        tree.root = installed

        def verify():
            _verify_tree(tree, package)
            legacy._check_preparation_owner(recovery, recovery_owner)
            require(legacy._read_file(recovery / legacy.SETTINGS_NAME, storage.MAX_SETTINGS_BYTES) == token.original_bytes
                    and legacy._json_file(recovery / "recovery.json") == metadata,
                    "recovery", str(recovery), "recovery changed")

        attempted = True
        saved = storage.save_preset_settings(settings_path, receiver, expected=token, before_commit=verify)
        tree = None  # Published and referenced; ownership transfers to the app.
        return legacy.ActivationResult(settings_path, installed, recovery,
                                       metadata["settings_sha256"], hashlib.sha256(saved.original_bytes).hexdigest(), receiver)
    except (OSError, ValueError, TypeError, RecursionError, zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error) as error:
        outcome = "not_committed"
        if isinstance(error, storage.PresetStorageError):
            outcome = {"not_saved": "not_committed", "saved": "committed"}.get(error.outcome, "indeterminate")
        elif attempted:
            outcome = "indeterminate"
        retained = [recovery] if recovery else []
        if tree is not None:
            if outcome == "not_committed":
                try:
                    tree.clean()
                    installed = None
                except (OSError, ValueError) as cleanup_error:
                    retained.append(tree.root)
                    error = RuntimeError(f"{error}; eigene Mediendaten konnten nicht sicher bereinigt werden: {cleanup_error}")
            else:
                retained.append(tree.root)
        raise legacy.ActivationError(str(error), outcome=outcome, recovery_directory=recovery,
                                     installed_directory=installed, retained_paths=retained) from error
