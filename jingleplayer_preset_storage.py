"""Explicit schema-3 storage shared by application settings and package activation.

All paths are absolute native paths; their parents must already exist and be free
of symlinks/reparse points. No home/CWD lookup, audio, GUI or package dependency.
Loading never writes or locks. Schema 2 migrates in memory; legacy requires the
explicit normalizer accepted by jingleplayer_presets. Missing files require both
initialize=True and caller-supplied initial_settings (no implicit home defaults).

Saving uses a persistent sibling '<filename>.presets.lock' OS advisory lock:
nonblocking flock on POSIX, msvcrt byte-range locking on Windows. Do not unlink or
replace this coordination file: doing so would split the lock domain. Its empty
contents are not settings or a second source of truth. A crashed process releases
the OS lock; a leftover lock file is normal. A busy lock raises code 'locked'.
Cooperating writers serialize read/compare/backup/write/replace. Noncooperating
writers (including older schema-2 application versions) do not honor this lock:
fingerprints detect observed changes only, not a full compare-and-swap. Ancestors
must remain trusted/stable; path checks are not a hostile-process sandbox.

Fingerprints include existence, file ID, size, mtime/ctime/birthtime and SHA-256.
Deletion/recreation/replacement normally changes identity or timestamps even for
identical bytes. An unobserved edit restored to identical metadata/identity cannot
be detected without filesystem history. No complete concurrency guarantee is made.

Before replacing any schema-2/legacy source, exact original bytes are exclusively
written to '<filename>.pre-presets.<original-sha256>.json', flushed, fsynced and
verified. Identical existing backups are reused; different contents or unsafe
entries block the save. Never touch pre-pyside6 backups. Partial backups are kept
and reported, not silently discarded or overwritten.

Restore protocol: stop all writers; separately preserve current settings/library;
verify snapshot SHA-256 against its filename and the load/save result; explicitly
restore the chosen snapshot to the verified settings path, then reload. This is
settings recovery only, not an audio backup. No automatic restoration exists.

Temporary settings files live beside the target; flush/fsync precede os.replace.
Pre-commit failures preserve the original file and backups. Cleanup only unlinks
the same operation-created temporary file ID, never a replacement/link. Failures
around/after replace report saved/not_saved/indeterminate; never blindly roll back.
Power-loss durability/multi-file transactions are not guaranteed. JSON input/output
is bounded at 16 MiB, UTF-8 without BOM, duplicate keys or nonfinite numbers.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from jingleplayer_presets import migrate_settings_to_schema3, validate_schema3_settings


MAX_SETTINGS_BYTES = 16 * 1024 * 1024


class PresetStorageError(ValueError):
    """Storage failure with code/location, outcome and retained recovery paths."""

    def __init__(self, code, location, message, *, outcome="not_saved", backup_path=None, temporary_path=None):
        self.code = code
        self.location = str(location)
        self.outcome = outcome
        self.backup_path = backup_path
        self.temporary_path = temporary_path
        super().__init__(f"{location}: {message}")


@dataclass(frozen=True)
class FileFingerprint:
    exists: bool
    identity: tuple = ()
    sha256: str | None = None


@dataclass(frozen=True)
class LoadedPresetSettings:
    """Detached data plus immutable optimistic-concurrency token/original bytes."""

    path: Path
    data: dict
    fingerprint: FileFingerprint
    original_bytes: bytes | None
    source_schema_version: int | None
    backup_path: Path | None = None


def _path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\0" in str(path):
        raise PresetStorageError("path", str(path), "absolute path without NUL/traversal required")
    return path


def _stat(path, *, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise PresetStorageError("unsafe_path", path, "links/reparse points forbidden")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise PresetStorageError("unsafe_path", path, "regular directory/file required")
    return info


def _parents(path):
    for parent in reversed(path.parents):
        _stat(parent, directory=True)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            getattr(info, "st_birthtime_ns", None))


def _read(path):
    _parents(path)
    try:
        before = _stat(path)
    except FileNotFoundError:
        return FileFingerprint(False), None
    if before.st_size > MAX_SETTINGS_BYTES:
        raise PresetStorageError("limit", path, "settings exceed byte limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise PresetStorageError("conflict", path, "file replaced during read")
        raw = stream.read(MAX_SETTINGS_BYTES + 1)
        after_open = os.fstat(stream.fileno())
    after = _stat(path)
    if (len(raw) > MAX_SETTINGS_BYTES or _identity(before) != _identity(after) or
            (opened.st_size, opened.st_mtime_ns) != (after_open.st_size, after_open.st_mtime_ns)):
        raise PresetStorageError("conflict", path, "file changed during read")
    return FileFingerprint(True, _identity(after), hashlib.sha256(raw).hexdigest()), raw


def _decode(raw, path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite number: {value}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PresetStorageError("json", path, str(error)) from error


def load_preset_settings(path, *, initialize=False, initial_settings=None, legacy_normalizer=None):
    """Read-only load -> LoadedPresetSettings; explicit initialization stays in RAM.

    initial_settings may be a complete schema-2 template or valid schema 3. It is
    used only if absent and initialize=True. Existing corrupt files never fall
    back to initial_settings. Legacy defaults are solely the caller's adapter.
    """
    path = _path(path)
    if type(initialize) is not bool:
        raise PresetStorageError("initialization", path, "initialize must be boolean")
    try:
        fingerprint, raw = _read(path)
    except OSError as error:
        raise PresetStorageError("read", path, str(error)) from error
    if raw is None:
        if not initialize or initial_settings is None:
            raise PresetStorageError("missing", path, "explicit initialization with initial_settings required")
        data = migrate_settings_to_schema3(initial_settings, legacy_normalizer=legacy_normalizer)
        return LoadedPresetSettings(path, data, fingerprint, None, None)
    decoded = _decode(raw, path)
    data = migrate_settings_to_schema3(decoded, legacy_normalizer=legacy_normalizer)
    return LoadedPresetSettings(path, data, fingerprint, raw, decoded.get("schema_version"))


@contextmanager
def _write_lock(path):
    _parents(path)
    lock_path = path.with_name(path.name + ".presets.lock")
    if os.path.lexists(lock_path):
        _stat(lock_path)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    locked = False
    try:
        opened = os.fstat(descriptor)
        info = _stat(lock_path)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise PresetStorageError("unsafe_path", lock_path, "lock file replaced")
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as error:
            raise PresetStorageError("locked", path, "another preset writer holds the lock") from error
        yield
    finally:
        try:
            if locked:
                if os.name == "nt":
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _check_expected(path, expected):
    fingerprint, raw = _read(path)
    if fingerprint != expected.fingerprint or raw != expected.original_bytes:
        raise PresetStorageError("conflict", path, "settings changed, removed or replaced since load")


def _migration_backup(path, raw):
    digest = hashlib.sha256(raw).hexdigest()
    backup = path.with_name(f"{path.name}.pre-presets.{digest}.json")
    if not os.path.lexists(backup):
        try:
            with backup.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        except OSError as error:
            raise PresetStorageError("backup", backup, str(error), backup_path=backup) from error
    try:
        _, copied = _read(backup)
        if copied != raw:
            raise PresetStorageError("backup_collision", backup, "existing backup differs", backup_path=backup)
    except (OSError, PresetStorageError) as error:
        raise PresetStorageError("backup", backup, str(error), backup_path=backup) from error
    return backup


def _cleanup_temp(path, identity):
    if path is None:
        return None
    try:
        _parents(path)
        info = _stat(path)
        if (info.st_dev, info.st_ino) != identity:
            return path
        path.unlink()
        return None
    except FileNotFoundError:
        return None
    except (OSError, PresetStorageError):
        return path


def save_preset_settings(path, data, *, expected, before_commit=None):
    """Explicit save -> new LoadedPresetSettings token; never a blind overwrite.

    expected must come from a load/save of this path. On failure, old tokens may
    be retried only if the file is unchanged; after success use the returned token.
    before_commit is an optional trusted integrity callback, run after temporary
    writing under the lock, immediately before the final fingerprint check/replace.
    A rejecting callback aborts with temporary cleanup and no settings replacement.
    Validation errors remain PresetValidationError; I/O/conflict/locking errors
    use PresetStorageError, with retained backup/temp paths and commit outcome.
    """
    path = _path(path)
    if not isinstance(expected, LoadedPresetSettings) or expected.path != path:
        raise PresetStorageError("token", path, "expected load token for this exact settings path")
    validated = validate_schema3_settings(data)
    encoded = json.dumps(validated, ensure_ascii=False, indent=4, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_SETTINGS_BYTES:
        raise PresetStorageError("limit", path, "settings exceed byte limit")
    temporary, temporary_id, backup = None, None, expected.backup_path
    attempted = committed = False
    try:
        with _write_lock(path):
            _check_expected(path, expected)
            if expected.original_bytes is not None and expected.source_schema_version != 3:
                backup = _migration_backup(path, expected.original_bytes)
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                             prefix=f".{path.name}.presets-", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                info = os.fstat(stream.fileno())
                temporary_id = (info.st_dev, info.st_ino)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            _, staged = _read(temporary)
            if staged != encoded:
                raise PresetStorageError("write", temporary, "temporary bytes differ")
            if before_commit is not None:
                before_commit()
            _check_expected(path, expected)
            attempted = True
            os.replace(temporary, path)
            committed = True
            temporary = None
            fingerprint, raw = _read(path)
            if raw != encoded:
                raise PresetStorageError("conflict", path, "settings changed after commit", outcome="saved")
            return LoadedPresetSettings(path, validated, fingerprint, raw, 3, backup)
    except (OSError, ValueError) as error:
        outcome = "saved" if committed else "not_saved"
        if attempted and not committed:
            try:
                _, observed = _read(path)
                outcome = "saved" if observed == encoded else (
                    "not_saved" if observed == expected.original_bytes else "indeterminate")
            except (OSError, PresetStorageError):
                outcome = "indeterminate"
        retained = _cleanup_temp(temporary, temporary_id)
        if isinstance(error, PresetStorageError):
            code = error.code
            backup = error.backup_path or backup
        else:
            code = "write"
        raise PresetStorageError(code, path, str(error), outcome=outcome,
                                 backup_path=backup, temporary_path=retained) from error
