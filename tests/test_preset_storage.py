"""Storage tests exclusively use caller-supplied temporary paths."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage


def schema2():
    return {"schema_version": 2, "window_size": [1200, 700], "volume": 37,
            "last_folder": "C:/Audio", "fadeout_duration": 500, "button_height": 3,
            "buttons": {"texts": [f"Slot {i}" for i in range(50)],
                        "colors": ["#123456"] * 50, "paths": [f"../audio/{i}.wav" for i in range(50)],
                        "volumes": [-10, 0, 10, 3, -4] * 10, "per_row": [2, 0, 0, 0, 0]}}


def source(tmp_path, version=2):
    path = tmp_path / "settings.json"
    data = schema2()
    if version == 3:
        data = presets.migrate_settings_to_schema3(data)
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(raw)
    return path, raw


def changed(loaded):
    return presets.rename_preset(loaded.data, loaded.data["active_preset_id"], "Changed")


def backup_for(path, raw):
    return path.with_name(f"{path.name}.pre-presets.{hashlib.sha256(raw).hexdigest()}.json")


@pytest.mark.parametrize("version", [2, 3])
def test_load_read_only_and_preserves_all_hidden_slots(tmp_path, version):
    path, raw = source(tmp_path, version)
    info = path.stat()
    loaded = storage.load_preset_settings(path)
    assert loaded.fingerprint.exists and loaded.fingerprint.sha256 == hashlib.sha256(raw).hexdigest()
    assert loaded.original_bytes == raw and loaded.source_schema_version == version
    board = presets.extract_active_board(loaded.data)
    assert board == schema2()
    assert len(board["buttons"]["paths"]) == 50
    assert board["buttons"]["paths"][49] == "../audio/49.wav"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == info.st_mtime_ns
    assert set(tmp_path.iterdir()) == {path}
    assert storage.load_preset_settings(path).data == loaded.data


def test_missing_initialization_explicit_and_schreibfrei(tmp_path):
    path = tmp_path / "new.json"
    for kwargs in ({}, {"initialize": True}, {"initial_settings": schema2()}):
        with pytest.raises(storage.PresetStorageError) as caught:
            storage.load_preset_settings(path, **kwargs)
        assert caught.value.code == "missing"
    initial = schema2()
    before = deepcopy(initial)
    loaded = storage.load_preset_settings(path, initialize=True, initial_settings=initial)
    assert loaded.original_bytes is None and not loaded.fingerprint.exists
    assert not list(tmp_path.iterdir()) and initial == before
    saved = storage.save_preset_settings(path, loaded.data, expected=loaded)
    assert saved.source_schema_version == 3 and saved.backup_path is None
    assert storage.load_preset_settings(path).data == loaded.data


@pytest.mark.parametrize("raw", [b"{", b"\xff", b'\xef\xbb\xbf{}', b'{"a":1,"a":2}',
                                      b'{"volume":NaN}', b"[]", b'{"schema_version":99}'])
def test_invalid_future_json_never_reinitialized(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises((storage.PresetStorageError, presets.PresetValidationError)):
        storage.load_preset_settings(path, initialize=True, initial_settings=schema2())
    assert path.read_bytes() == raw and set(tmp_path.iterdir()) == {path}


def test_legacy_uses_explicit_existing_normalizer(tmp_path, monkeypatch):
    import jingleplayer_logic as logic

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "fake-home"))
    path = tmp_path / "legacy.json"
    raw = b'{"buttons":{"texts":["Old"],"per_row":[1,0,0,0,0]}}'
    path.write_bytes(raw)
    with pytest.raises(presets.PresetValidationError):
        storage.load_preset_settings(path)
    loaded = storage.load_preset_settings(path, legacy_normalizer=logic._normalize_settings_data)
    assert loaded.data["presets"][0]["buttons"]["texts"][:2] == ["Old", "Jingle 2"]
    assert path.read_bytes() == raw
    saved = storage.save_preset_settings(path, loaded.data, expected=loaded)
    assert saved.backup_path.read_bytes() == raw


def test_atomic_save_backup_and_repeated_saves_without_duplicate_presets(tmp_path, monkeypatch):
    path, raw = source(tmp_path)
    old_backup = tmp_path / "jingleplayer_settings.pre-pyside6.json"
    old_backup.write_bytes(b"unrelated migration backup")
    loaded = storage.load_preset_settings(path)
    data = changed(loaded)
    before = deepcopy(data)
    replace = storage.os.replace
    calls = []

    def tracked(temp, target):
        assert temp.parent == target.parent
        assert backup_for(path, raw).read_bytes() == raw
        assert path.read_bytes() == raw
        calls.append((temp, target))
        replace(temp, target)

    monkeypatch.setattr(storage.os, "replace", tracked)
    saved = storage.save_preset_settings(path, data, expected=loaded)
    assert len(calls) == 1 and not calls[0][0].exists()
    assert saved.backup_path == backup_for(path, raw)
    assert saved.backup_path.read_bytes() == raw
    assert old_backup.read_bytes() == b"unrelated migration backup"
    assert data == before and loaded.original_bytes == raw
    monkeypatch.setattr(storage.os, "replace", replace)
    again = storage.save_preset_settings(path, saved.data, expected=saved)
    assert len(again.data["presets"]) == 1
    assert again.data["active_preset_id"] == loaded.data["active_preset_id"]
    assert list(tmp_path.glob("*.pre-presets.*.json")) == [saved.backup_path]


@pytest.mark.parametrize("same", [False, True])
def test_existing_backup_never_overwritten(tmp_path, same):
    path, raw = source(tmp_path)
    backup = backup_for(path, raw)
    existing = raw if same else b"wrong backup"
    backup.write_bytes(existing)
    loaded = storage.load_preset_settings(path)
    if same:
        assert storage.save_preset_settings(path, changed(loaded), expected=loaded).backup_path == backup
    else:
        with pytest.raises(storage.PresetStorageError) as caught:
            storage.save_preset_settings(path, changed(loaded), expected=loaded)
        assert caught.value.code == "backup" and path.read_bytes() == raw
    assert backup.read_bytes() == existing


def test_backup_creation_failure_blocks_activation(tmp_path, monkeypatch):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    original_open = Path.open

    def denied(self, *args, **kwargs):
        if self == backup_for(path, raw):
            raise PermissionError("backup denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.code == "backup" and path.read_bytes() == raw


def test_failed_backup_fsync_keeps_snapshot_and_original(tmp_path, monkeypatch):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    monkeypatch.setattr(storage.os, "fsync", lambda *a: (_ for _ in ()).throw(OSError("backup fsync failed")))
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.code == "backup" and caught.value.outcome == "not_saved"
    assert caught.value.backup_path == backup_for(path, raw)
    assert caught.value.backup_path.read_bytes() == raw and path.read_bytes() == raw
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("failure", ["temp_write", "temp_fsync", "replace"])
def test_save_failure_preserves_original_and_backup_and_cleans_temp(tmp_path, monkeypatch, failure):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    # Existing exact backup separates backup fsync from the settings fsync test.
    backup = backup_for(path, raw)
    backup.write_bytes(raw)
    if failure == "temp_write":
        factory = storage.tempfile.NamedTemporaryFile

        class BrokenWrite:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def __getattr__(self, name):
                return getattr(self.stream, name)
            def write(self, data):
                self.stream.write(data[:7])
                raise OSError("partial write failure")

        monkeypatch.setattr(storage.tempfile, "NamedTemporaryFile", lambda **kwargs: BrokenWrite(factory(**kwargs)))
    elif failure == "temp_fsync":
        monkeypatch.setattr(storage.os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("fsync failure")))
    else:
        monkeypatch.setattr(storage.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("replace failure")))
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.outcome == "not_saved" and caught.value.temporary_path is None
    assert path.read_bytes() == raw and backup.read_bytes() == raw
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("change", ["modify", "delete", "recreate", "replace_same_bytes"])
def test_conflicts_after_load(tmp_path, change):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    if change == "modify":
        path.write_bytes(b"other writer")
    elif change == "delete":
        path.unlink()
    elif change == "recreate":
        path.unlink()
        path.write_bytes(raw)
    else:
        new = tmp_path / "replacement.json"
        new.write_bytes(raw)
        os.replace(new, path)
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.code == "conflict"
    assert (path.read_bytes() if path.exists() else None) == before
    assert not list(tmp_path.glob("*.pre-presets.*.json"))


def test_initialized_missing_file_conflicts_with_external_creation(tmp_path):
    path = tmp_path / "new.json"
    loaded = storage.load_preset_settings(path, initialize=True, initial_settings=schema2())
    path.write_bytes(b"external creation")
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, loaded.data, expected=loaded)
    assert caught.value.code == "conflict" and path.read_bytes() == b"external creation"


def test_two_concurrent_writers_are_serialized_and_stale_retry_rejected(tmp_path, monkeypatch):
    path, raw = source(tmp_path)
    first = storage.load_preset_settings(path)
    second = storage.load_preset_settings(path)
    reached, release = threading.Event(), threading.Event()
    replace = storage.os.replace
    outcomes = []

    def held_replace(temp, target):
        reached.set()
        if not release.wait(10):
            raise OSError("test timeout")
        replace(temp, target)

    monkeypatch.setattr(storage.os, "replace", held_replace)

    def writer():
        try:
            outcomes.append(storage.save_preset_settings(path, changed(first), expected=first))
        except Exception as error:
            outcomes.append(error)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert reached.wait(10)
        with pytest.raises(storage.PresetStorageError) as caught:
            storage.save_preset_settings(path, second.data, expected=second)
        assert caught.value.code == "locked"
        assert path.read_bytes() == raw
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and isinstance(outcomes[0], storage.LoadedPresetSettings)
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, second.data, expected=second)
    assert caught.value.code == "conflict"
    assert storage.load_preset_settings(path).data["presets"][0]["name"] == "Changed"


def test_os_lock_coordinates_separate_processes_and_releases_on_exit(tmp_path):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(Path(storage.__file__).parent), PYTHONDONTWRITEBYTECODE="1")
    # Readiness is a file only inside this test directory, not storage metadata.
    ready = tmp_path / "ready"
    code = """
from pathlib import Path
import sys
import jingleplayer_preset_storage as storage
with storage._write_lock(Path(sys.argv[1])):
    Path(sys.argv[2]).write_text('locked')
    sys.stdin.readline()
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(path), str(ready)],
                             cwd=tmp_path, env=environment, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import time
        deadline = time.monotonic() + 10
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "child did not acquire the OS lock"
        with pytest.raises(storage.PresetStorageError) as caught:
            storage.save_preset_settings(path, changed(loaded), expected=loaded)
        assert caught.value.code == "locked" and path.read_bytes() == raw
    finally:
        try:
            stdout, stderr = child.communicate("release\n", timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            stdout, stderr = child.communicate()
    assert child.returncode == 0, stderr
    saved = storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert saved.data["presets"][0]["name"] == "Changed"
    assert path.with_name(path.name + ".presets.lock").is_file()


def test_noncooperating_write_before_final_check_detected(tmp_path, monkeypatch):
    path, _ = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    fsync = storage.os.fsync

    def concurrent(fd):
        fsync(fd)
        path.write_bytes(b"other process")

    monkeypatch.setattr(storage.os, "fsync", concurrent)
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.code == "conflict" and path.read_bytes() == b"other process"


def test_post_replace_exception_reports_saved_without_restore(tmp_path, monkeypatch):
    path, _ = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    replace = storage.os.replace

    def replace_then_fail(temp, target):
        replace(temp, target)
        raise OSError("exception after replace")

    monkeypatch.setattr(storage.os, "replace", replace_then_fail)
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.outcome == "saved"
    assert storage.load_preset_settings(path).data["presets"][0]["name"] == "Changed"


def test_temporary_file_replacement_not_deleted(tmp_path, monkeypatch):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)

    def replace_temp(temp, target):
        temp.rename(tmp_path / "moved-owned-temp")
        temp.write_bytes(b"unrelated replacement")
        raise OSError("racing temp replacement")

    monkeypatch.setattr(storage.os, "replace", replace_temp)
    with pytest.raises(storage.PresetStorageError) as caught:
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert caught.value.temporary_path.read_bytes() == b"unrelated replacement"
    assert path.read_bytes() == raw


def test_invalid_data_and_wrong_token_do_not_write(tmp_path):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    damaged = deepcopy(loaded.data)
    damaged["presets"][0]["buttons"]["paths"].pop()
    with pytest.raises(presets.PresetValidationError):
        storage.save_preset_settings(path, damaged, expected=loaded)
    with pytest.raises(storage.PresetStorageError):
        storage.save_preset_settings(tmp_path / "other.json", loaded.data, expected=loaded)
    assert path.read_bytes() == raw and set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("path", ["relative.json", "/absolute\0.json", "/a/../settings.json"])
def test_unsafe_native_path_arguments(path):
    with pytest.raises(storage.PresetStorageError):
        storage.load_preset_settings(path)


def test_symlink_rejected_for_target_and_lock(tmp_path):
    path, raw = source(tmp_path)
    loaded = storage.load_preset_settings(path)
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(path)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(storage.PresetStorageError):
        storage.load_preset_settings(link)
    lock = path.with_name(path.name + ".presets.lock")
    lock.symlink_to(path)
    with pytest.raises(storage.PresetStorageError):
        storage.save_preset_settings(path, changed(loaded), expected=loaded)
    assert path.read_bytes() == raw


def test_isolated_import_has_no_application_dependencies(tmp_path):
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(Path(storage.__file__).parent), PYTHONDONTWRITEBYTECODE="1")
    code = "import sys; import jingleplayer_preset_storage; assert not any(n.startswith(('PySide6','pygame','jingleplayer_logic','jingleplayer_packages')) for n in sys.modules)"
    child = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=environment,
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
