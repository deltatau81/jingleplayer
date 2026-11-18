"""Contract and read-only filesystem checks; no application imports required."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

import jingleplayer_packages as packages


def board():
    return {
        "schema_version": 2,
        "buttons": {"texts": [f"Jingle {i}" for i in range(50)],
                    "colors": ["SystemButtonFace"] * 50, "paths": [""] * 50,
                    "volumes": [0] * 50, "per_row": [1, 0, 0, 0, 0]},
        "button_height": 2, "fadeout_duration": 1000,
        "window_size": [800, 600], "volume": 100,
    }


def data(paths=("Musik/example.wav",)):
    settings = board()
    entries = []
    for index, path in enumerate(paths):
        settings["buttons"]["paths"][49 - index] = path  # Hidden assignments.
        entries.append({"path": path, "size": 3,
                        "sha256": hashlib.sha256(b"abc").hexdigest()})
    return {"package_version": 1, "assets": entries}, settings


def write_package(root, manifest=None, settings=None):
    if manifest is None:
        manifest, settings = data()
    root.mkdir()
    for entry in manifest["assets"]:
        path = root.joinpath(*entry["path"].split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"abc")
    (root / packages.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    (root / packages.SETTINGS_NAME).write_text(json.dumps(settings), encoding="utf-8")
    return root


def test_valid_hidden_duplicate_references_and_detached_snapshot():
    manifest, settings = data(("Musik/nested/Grüße.MP3", "Musik/音楽.WAV"))
    settings["buttons"]["paths"][0] = settings["buttons"]["paths"][49]
    original = deepcopy((manifest, settings))
    result = packages.validate_package_data(manifest, settings)
    assert len(result.settings["buttons"]["paths"]) == 50
    assert result.settings["buttons"]["paths"][49] == "Musik/nested/Grüße.MP3"
    result.settings["buttons"]["texts"][0] = "detached"
    assert (manifest, settings) == original


def test_empty_board_and_optional_empty_local_metadata(tmp_path):
    manifest, settings = data(())
    settings["last_folder"] = ""
    root = write_package(tmp_path / "empty", manifest, settings)
    assert packages.validate_package_directory(root).assets == ()
    (root / "Musik").mkdir()
    assert packages.validate_package_directory(root).assets == ()


@pytest.mark.parametrize("path", [
    "", None, 42, "/Musik/a.wav", "C:/Musik/a.wav", "C:Musik/a.wav",
    "//server/share/a.wav", "\\\\server\\share\\a.wav", "\\\\?\\C:\\a.wav",
    "Musik\\a.wav", "Other/a.wav", "musik/a.wav", "Musik//a.wav",
    "Musik/./a.wav", "Musik/../a.wav", "Musik/a/../../a.wav",
    "Musik/a.wav/", "Musik/a\0.wav", "Musik/a\n.wav", "Musik/a\x7f.wav",
    "Musik/a\u0085.wav", "Musik/a\u202e.wav", "Musik/a\ud800.wav",
    "Musik/CON.wav", "Musik/CON .wav", "Musik/nul.MP3", "Musik/COM1/a.wav", "Musik/LPT².wav",
    "Musik/AUX.foo.wav", "Musik/a./a.wav", "Musik/a /a.wav",
    "Musik/a?.wav", "Musik/a*.wav", "Musik/a:b.wav", 'Musik/a".wav',
    "Musik/a<.wav", "Musik/a>.wav", "Musik/a|.wav", "Musik/a.ogg", "Musik/wav",
])
def test_unsafe_paths(path):
    with pytest.raises(packages.PackageValidationError):
        packages.validate_asset_path(path)


@pytest.mark.parametrize("path", ["Musik/Grüße.mp3", "Musik/e\u0301.WAV",
                                       "Musik/é.wav", "Musik/嵐/a.MP3"])
def test_unicode_paths_preserved(path):
    assert packages.validate_asset_path(path) == path


@pytest.mark.parametrize("paths", [
    ("Musik/a.wav", "Musik/a.wav"), ("Musik/A.wav", "Musik/a.WAV"),
    ("Musik/é.wav", "Musik/e\u0301.wav"), ("Musik/Straße.wav", "Musik/STRASSE.wav"),
    ("Musik/Dir/a.wav", "Musik/dir/b.wav"),
    ("Musik/a.wav", "Musik/a.wav/b.mp3"),
])
def test_ambiguous_paths(paths):
    manifest, _ = data(paths)
    with pytest.raises(packages.PackageValidationError, match="ambiguous"):
        packages.validate_manifest(manifest)


@pytest.mark.parametrize("field,value", [
    ("package_version", 2), ("package_version", True), ("package_version", "1"),
    ("assets", {}), ("assets", None),
])
def test_manifest_types_and_versions(field, value):
    manifest, settings = data()
    manifest[field] = value
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_data(manifest, settings)


@pytest.mark.parametrize("field,value", [
    ("size", -1), ("size", True), ("size", 1.5), ("size", "3"),
    ("size", packages.MAX_ASSET_BYTES + 1),
    ("sha256", "a" * 63), ("sha256", "g" * 64), ("sha256", 123),
])
def test_bad_asset_fields(field, value):
    manifest, _ = data()
    manifest["assets"][0][field] = value
    with pytest.raises(packages.PackageValidationError):
        packages.validate_manifest(manifest)


def test_asset_limits_and_uppercase_hash():
    manifest, _ = data()
    manifest["assets"][0]["sha256"] = "A" * 64
    assert packages.validate_manifest(manifest)[0].sha256 == "a" * 64
    manifest["assets"] *= 51
    with pytest.raises(packages.PackageValidationError):
        packages.validate_manifest(manifest)
    manifest, _ = data(tuple(f"Musik/{i}.wav" for i in range(6)))
    for entry in manifest["assets"]:
        entry["size"] = packages.MAX_ASSET_BYTES
    with pytest.raises(packages.PackageValidationError, match="total"):
        packages.validate_manifest(manifest)


@pytest.mark.parametrize("field,value", [
    ("schema_version", 1), ("schema_version", 3), ("schema_version", True),
    ("buttons", []), ("button_height", 0), ("button_height", 11),
    ("button_height", True), ("fadeout_duration", -1),
    ("fadeout_duration", 2147483648), ("fadeout_duration", 1.0),
    ("window_size", [0, 600]), ("window_size", [True, 600]),
    ("window_size", [800]), ("window_size", "800x600"),
    ("volume", -1), ("volume", 101), ("last_folder", "/Users/someone"),
    ("last_folder", None), ("unknown_path", "/etc/passwd"),
])
def test_invalid_settings_fields(field, value):
    manifest, settings = data()
    settings[field] = value
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_data(manifest, settings)


@pytest.mark.parametrize("field,value", [
    ("texts", [""] * 49), ("colors", [""] * 50), ("paths", [None] * 50),
    ("volumes", [11] * 50), ("volumes", [-11] * 50), ("volumes", [True] * 50),
    ("per_row", [0] * 5), ("per_row", [11, 0, 0, 0, 0]),
    ("per_row", [1] * 4), ("per_row", [True] * 5), ("per_row", [1.0] * 5),
    ("extra", "bad"),
])
def test_invalid_button_fields(field, value):
    manifest, settings = data()
    settings["buttons"][field] = value
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_data(manifest, settings)


def test_boundaries_and_required_exact_keys():
    manifest, settings = data(())
    settings.update(button_height=10, fadeout_duration=2147483647, volume=0)
    settings["buttons"]["volumes"] = [-10, 10] * 25
    settings["buttons"]["per_row"] = [0, 10, 0, 10, 0]
    packages.validate_package_data(manifest, settings)
    for target in (manifest, settings, settings["buttons"]):
        copied = deepcopy(target)
        copied.pop(next(iter(copied)))
        with pytest.raises(packages.PackageValidationError):
            if target is manifest:
                packages.validate_manifest(copied)
            elif target is settings:
                packages.validate_settings(copied, ())
            else:
                altered = deepcopy(settings)
                altered["buttons"] = copied
                packages.validate_settings(altered, ())
    for target in (manifest, {"package_version": 1, "assets": [{"extra": 1}]}):
        altered = deepcopy(target)
        altered["extra"] = 1
        with pytest.raises(packages.PackageValidationError):
            packages.validate_manifest(altered)


@pytest.mark.parametrize("missing_manifest", [True, False])
def test_manifest_references_must_match(missing_manifest):
    manifest, settings = data()
    if missing_manifest:
        manifest["assets"] = []
    else:
        settings["buttons"]["paths"][49] = ""
    with pytest.raises(packages.PackageValidationError, match="match exactly"):
        packages.validate_package_data(manifest, settings)


def test_json_data_limits():
    manifest, settings = data()
    settings["buttons"]["texts"][0] = "a" * packages.MAX_JSON_BYTES
    with pytest.raises(packages.PackageValidationError, match="limit"):
        packages.validate_package_data(manifest, settings)
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_data(float("nan"), {})


@pytest.mark.parametrize("raw", [b"{", b"[]", b"\xff", b'\xef\xbb\xbf{}',
                                        b'{"package_version":1,"package_version":1,"assets":[]}',
                                        b'{"package_version":NaN,"assets":[]}'])
def test_malformed_metadata(tmp_path, raw):
    root = write_package(tmp_path / "board")
    (root / packages.MANIFEST_NAME).write_bytes(raw)
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_directory(root)


@pytest.mark.parametrize("name", [packages.MANIFEST_NAME, packages.SETTINGS_NAME])
def test_oversized_and_missing_metadata(tmp_path, name):
    root = write_package(tmp_path / "board")
    target = root / name
    target.write_bytes(b" " * (packages.MAX_JSON_BYTES + 1))
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_directory(root)
    target.unlink()
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_directory(root)


@pytest.mark.parametrize("change", ["missing", "short", "long", "hash", "directory", "extra", "extra_dir"])
def test_invalid_filesystem_assets(tmp_path, change):
    root = write_package(tmp_path / "board")
    asset = root / "Musik/example.wav"
    if change == "missing":
        asset.unlink()
    elif change in ("short", "long", "hash"):
        asset.write_bytes({"short": b"a", "long": b"abcd", "hash": b"xyz"}[change])
    elif change == "directory":
        asset.unlink()
        asset.mkdir()
    elif change == "extra":
        (root / "extra.wav").write_bytes(b"abc")
    else:
        (root / "unused").mkdir()
    with pytest.raises(packages.PackageValidationError):
        packages.validate_package_directory(root)


def symlink_or_skip(link, target, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")


@pytest.mark.parametrize("kind", ["root", "ancestor", "metadata", "asset", "intermediate"])
def test_symlinks_and_escapes(tmp_path, kind):
    root = write_package(tmp_path / "board")
    if kind == "root":
        link = tmp_path / "link"
        symlink_or_skip(link, root, True)
        root = link
    elif kind == "ancestor":
        link = tmp_path / "link"
        symlink_or_skip(link, tmp_path, True)
        root = link / "board"
    else:
        target = root / ({"metadata": packages.SETTINGS_NAME,
                          "asset": "Musik/example.wav", "intermediate": "Musik"}[kind])
        outside = tmp_path / "outside"
        target.rename(outside)
        symlink_or_skip(target, outside, kind == "intermediate")
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.validate_package_directory(root)
    assert caught.value.code == "link"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction API")
def test_windows_junction_escape(tmp_path):
    root = write_package(tmp_path / "board")
    target = root / "Musik"
    outside = tmp_path / "outside"
    target.rename(outside)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)],
                            capture_output=True, text=True)
    if result.returncode:
        pytest.skip(f"junction creation unavailable: {result.stderr}")
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.validate_package_directory(root)
    assert caught.value.code == "link"


def test_read_only_unrelated_cwd_and_streamed_hashing(tmp_path, monkeypatch):
    root = write_package(tmp_path / "board")
    active = tmp_path / "active_settings.json"
    active.write_bytes(b"do not change")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(packages, "HASH_CHUNK_BYTES", 1)
    assert packages.validate_package_directory(root).assets[0].size == 3
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
    assert set(p for p in tmp_path.rglob("*") if p.is_file()) == set(before)


def test_zero_byte_asset(tmp_path):
    manifest, settings = data()
    manifest["assets"][0].update(size=0, sha256=hashlib.sha256(b"").hexdigest())
    root = write_package(tmp_path / "board", manifest, settings)
    (root / "Musik/example.wav").write_bytes(b"")
    assert packages.validate_package_directory(root).assets[0].size == 0


def test_nested_unicode_uppercase_assets_on_filesystem(tmp_path):
    manifest, settings = data(("Musik/嵐/Grüße.MP3", "Musik/é.WAV"))
    root = write_package(tmp_path / "board", manifest, settings)
    assert len(packages.validate_package_directory(root).assets) == 2


def test_failed_validation_preserves_files(tmp_path):
    root = write_package(tmp_path / "board")
    (root / "Musik/example.wav").write_bytes(b"bad")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.validate_package_directory(root)
    assert caught.value.code == "hash"
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_reparse_flag_check_on_any_host(tmp_path, monkeypatch):
    path = tmp_path / "asset.wav"
    path.write_bytes(b"abc")
    from types import SimpleNamespace
    monkeypatch.setattr(Path, "lstat", lambda self: SimpleNamespace(
        st_mode=0o100644, st_file_attributes=0x400))
    with pytest.raises(packages.PackageValidationError) as caught:
        packages._safe_stat(path)
    assert caught.value.code == "link"


def export_board(tmp_path, names=("source.wav",)):
    settings = board()
    sources = []
    for index, name in enumerate(names):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"audio-" + str(index).encode())
        settings["buttons"]["paths"][49 - index] = str(source)
        sources.append(source)
    return settings, sources, tmp_path / "exported"


def assert_no_staging(parent):
    assert not list(parent.glob(".jingleplayer-export-*"))


def test_export_success_preserves_all_slots_sources_and_local_settings(tmp_path, monkeypatch):
    settings, sources, destination = export_board(tmp_path, ("audio with spaces.WAV", "嵐.MP3"))
    settings["last_folder"] = str(tmp_path / "private-folder")
    settings["buttons"]["paths"][0] = str(sources[0])
    settings["buttons"]["texts"] = [f"slot {i}" for i in range(50)]
    settings["buttons"]["volumes"] = [-10, 10] * 25
    settings["buttons"]["colors"] = ["#123456"] * 50
    snapshot = deepcopy(settings)
    # Redirect the home of any accidental active-settings access to a sentinel.
    fake_home = tmp_path / "home"
    active = fake_home / ".jingleplayer/jingleplayer_settings.json"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"active settings must remain untouched")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (*sources, active)}
    elsewhere = tmp_path / "unrelated"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = packages.export_package_directory(settings, destination)
    assert result == packages.validate_package_directory(destination)
    assert settings == snapshot
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
    assert "last_folder" not in result.settings
    for key in ("window_size", "volume", "fadeout_duration", "button_height", "schema_version"):
        assert result.settings[key] == snapshot[key]
    for key in ("texts", "colors", "volumes", "per_row"):
        assert result.settings["buttons"][key] == snapshot["buttons"][key]
    paths = result.settings["buttons"]["paths"]
    assert paths[0] == paths[49] and paths[48] != paths[49]
    assert len(result.assets) == 2 and len(paths) == 50
    assert all(not paths[i] for i in range(1, 48))
    assert_no_staging(tmp_path)


def test_export_empty_board(tmp_path):
    destination = tmp_path / "empty"
    result = packages.export_package_directory(board(), destination)
    assert result.assets == ()
    assert (destination / "Musik").is_dir()
    assert packages.validate_package_directory(destination) == result


def test_export_fifty_distinct_hidden_and_visible_assets(tmp_path):
    settings, _, destination = export_board(tmp_path, tuple(f"{i}.wav" for i in range(50)))
    result = packages.export_package_directory(settings, destination)
    assert len(result.assets) == 50
    assert len(set(result.settings["buttons"]["paths"])) == 50


def test_export_names_portable_collision_free_and_deterministic(tmp_path):
    # Separate folders allow these sources on case-insensitive/normalizing hosts.
    settings, _, destination = export_board(tmp_path, (
        "a/same.wav", "b/same.wav", "c/SAME.WAV", "d/é.wav", "e/e\u0301.wav"))
    first = packages.export_package_directory(settings, destination)
    second_destination = tmp_path / "second"
    second = packages.export_package_directory(settings, second_destination)
    assert first == second
    assert len({packages._collision_key(a.path) for a in first.assets}) == 5
    for name in (packages.MANIFEST_NAME, packages.SETTINGS_NAME):
        assert (destination / name).read_bytes() == (second_destination / name).read_bytes()
    for asset in first.assets:
        assert packages.validate_asset_path(asset.path) == asset.path
        assert len(asset.path) < 40


@pytest.mark.parametrize("basename", ["CON.wav", "NUL.mp3", "a?.wav", "a:b.wav", "trailing .wav"])
def test_unsafe_source_basenames_generate_safe_names(tmp_path, monkeypatch, basename):
    settings, sources, destination = export_board(tmp_path)
    # Such names cannot be created on Windows; simulate only canonical naming.
    source_path = packages._source_path

    def unsafe_name(value, base):
        source, info = source_path(value, base)
        return source.with_name(basename), info

    copy_asset = packages._copy_asset

    def copy_original(source, target, before, remaining):
        return copy_asset(sources[0], target, before, remaining)

    monkeypatch.setattr(packages, "_source_path", unsafe_name)
    monkeypatch.setattr(packages, "_copy_asset", copy_original)
    result = packages.export_package_directory(settings, destination)
    assert result.assets[0].path == "Musik/asset-001" + Path(basename).suffix.lower()


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot create these source basenames")
def test_actual_unsafe_source_basenames_on_posix(tmp_path):
    settings, _, destination = export_board(tmp_path, ("CON.wav", "bad?.mp3", "a:b.wav"))
    assert len(packages.export_package_directory(settings, destination).assets) == 3


def test_explicit_relative_base_and_no_cwd_dependency(tmp_path, monkeypatch):
    settings, sources, destination = export_board(tmp_path)
    settings["buttons"]["paths"][49] = sources[0].name
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(packages.PackageValidationError, match="source_base"):
        packages.export_package_directory(settings, destination)
    result = packages.export_package_directory(settings, destination, source_base=tmp_path)
    assert len(result.assets) == 1
    assert Path.cwd() == elsewhere


@pytest.mark.parametrize("kind", ["missing", "directory", "unsupported", "unreadable", "traversal"])
def test_export_invalid_source_rolls_back(tmp_path, monkeypatch, kind):
    settings, sources, destination = export_board(tmp_path)
    source = sources[0]
    if kind == "missing":
        source.unlink()
    elif kind == "directory":
        source.unlink()
        source.mkdir()
    elif kind == "unsupported":
        new = source.with_suffix(".ogg")
        source.rename(new)
        settings["buttons"]["paths"][49] = str(new)
    elif kind == "traversal":
        settings["buttons"]["paths"][49] = str(tmp_path / "other" / ".." / source.name)
    else:
        original_open = packages.os.open

        def denied(path, flags, *args, **kwargs):
            if Path(path) == source:
                raise PermissionError("source unreadable")
            return original_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(packages.os, "open", denied)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("field,value", [("volume", 101), ("schema_version", 3),
                                         ("last_folder", None), ("unknown_path", "secret")])
def test_export_invalid_settings_rejected_before_copy(tmp_path, monkeypatch, field, value):
    settings, _, destination = export_board(tmp_path)
    settings[field] = value
    monkeypatch.setattr(packages, "_copy_asset", lambda *args: pytest.fail("must not copy"))
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("limit,value", [("MAX_ASSET_BYTES", 1), ("MAX_TOTAL_BYTES", 1), ("MAX_ASSETS", 0),
                                       ("MAX_JSON_BYTES", 10)])
def test_export_limits_before_copy(tmp_path, monkeypatch, limit, value):
    settings, _, destination = export_board(tmp_path)
    monkeypatch.setattr(packages, limit, value)
    monkeypatch.setattr(packages, "_copy_asset", lambda *args: pytest.fail("must not copy"))
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("kind", ["empty_directory", "file", "populated_directory"])
def test_export_existing_destination_never_overwritten(tmp_path, kind):
    settings, _, destination = export_board(tmp_path)
    if kind == "file":
        destination.write_bytes(b"unrelated")
    else:
        destination.mkdir()
        if kind == "populated_directory":
            (destination / "keep").write_bytes(b"unrelated")
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert destination.exists()
    if kind == "file":
        assert destination.read_bytes() == b"unrelated"
    elif kind == "populated_directory":
        assert (destination / "keep").read_bytes() == b"unrelated"
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("kind", ["directory", "file"])
def test_export_destination_race_no_replace(tmp_path, monkeypatch, kind):
    settings, _, destination = export_board(tmp_path)
    publish = packages._publish_directory

    def race(staging, target):
        if kind == "directory":
            target.mkdir()  # Even empty directories must never be overwritten.
        else:
            target.write_bytes(b"racing writer")
        return publish(staging, target)

    monkeypatch.setattr(packages, "_publish_directory", race)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert destination.exists()
    if kind == "directory":
        assert not list(destination.iterdir())
    else:
        assert destination.read_bytes() == b"racing writer"
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("stage", ["copy", "write_json", "validation", "publication"])
def test_export_failures_cleanup_only_owned_staging(tmp_path, monkeypatch, stage):
    settings, sources, destination = export_board(tmp_path, ("a.wav", "b.mp3"))
    unrelated = tmp_path / ".jingleplayer-export-unrelated"
    unrelated.mkdir()
    (unrelated / "keep").write_bytes(b"unrelated")
    original = {p: p.read_bytes() for p in sources}
    if stage == "copy":
        copy_asset = packages._copy_asset

        def fail_copy(source, target, *args):
            if source == sources[0]:
                raise OSError("copy failure")
            return copy_asset(source, target, *args)

        monkeypatch.setattr(packages, "_copy_asset", fail_copy)
    else:
        function = {"write_json": "_write_export_json", "validation": "validate_package_directory",
                    "publication": "_publish_directory"}[stage]

        def fail(*args):
            raise OSError("injected failure")

        monkeypatch.setattr(packages, function, fail)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert {p: p.read_bytes() for p in sources} == original
    assert list(tmp_path.glob(".jingleplayer-export-*")) == [unrelated]
    assert (unrelated / "keep").read_bytes() == b"unrelated"


def test_export_source_mutation_during_streaming(tmp_path, monkeypatch):
    settings, sources, destination = export_board(tmp_path)
    original_fsync = packages.os.fsync

    def mutate(fd):
        original_fsync(fd)
        sources[0].write_bytes(b"changed during copy")

    monkeypatch.setattr(packages.os, "fsync", mutate)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert_no_staging(tmp_path)


def test_export_changed_copied_bytes_fail_staging_verification(tmp_path, monkeypatch):
    settings, _, destination = export_board(tmp_path)
    copy_asset = packages._copy_asset

    def corrupt(source, target, before, remaining):
        result = copy_asset(source, target, before, remaining)
        target.write_bytes(b"x" * result[0])
        return result

    monkeypatch.setattr(packages, "_copy_asset", corrupt)
    with pytest.raises(packages.PackageValidationError, match="SHA-256"):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("kind", ["source", "ancestor", "destination"])
def test_export_rejects_symlinks(tmp_path, kind):
    settings, sources, destination = export_board(tmp_path)
    if kind == "source":
        link = tmp_path / "linked.wav"
        symlink_or_skip(link, sources[0])
        settings["buttons"]["paths"][49] = str(link)
    elif kind == "ancestor":
        link = tmp_path / "linked"
        symlink_or_skip(link, tmp_path, True)
        settings["buttons"]["paths"][49] = str(link / sources[0].name)
    else:
        symlink_or_skip(destination, tmp_path / "nonexistent", True)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert_no_staging(tmp_path)


def test_export_deduplicates_hardlinks(tmp_path):
    settings, sources, destination = export_board(tmp_path)
    alias = tmp_path / "alias.wav"
    try:
        os.link(sources[0], alias)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")
    settings["buttons"]["paths"][0] = str(alias)
    assert len(packages.export_package_directory(settings, destination).assets) == 1


def test_export_module_has_no_application_imports():
    import ast
    tree = ast.parse(Path(packages.__file__).read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module)
    assert not any(name.startswith(("PySide6", "pygame", "jingleplayer_logic", "jingleplayer_gui"))
                   for name in modules)


def test_export_staging_validated_before_atomic_publication(tmp_path, monkeypatch):
    settings, _, destination = export_board(tmp_path)
    publish = packages._publish_directory

    def inspect_publication(staging, target):
        assert staging.parent == target.parent
        assert not target.exists()
        assert len(packages.validate_package_directory(staging).assets) == 1
        publish(staging, target)

    monkeypatch.setattr(packages, "_publish_directory", inspect_publication)
    packages.export_package_directory(settings, destination)


def test_export_detects_same_size_mutation_with_restored_mtime(tmp_path, monkeypatch):
    settings, sources, destination = export_board(tmp_path)
    source = sources[0]
    before = source.stat()
    original_fsync = packages.os.fsync

    def mutate(fd):
        original_fsync(fd)
        source.write_bytes(b"x" * before.st_size)
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))

    monkeypatch.setattr(packages.os, "fsync", mutate)
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination)
    assert not destination.exists()
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("kind", ["relative_destination", "relative_base", "invalid_destination"])
def test_export_rejects_ambiguous_or_invalid_api_paths(tmp_path, kind):
    settings, _, destination = export_board(tmp_path)
    kwargs = {}
    if kind == "relative_destination":
        destination = "relative-export"
    elif kind == "relative_base":
        kwargs["source_base"] = "relative-base"
    else:
        destination = str(destination) + "\0"
    with pytest.raises(packages.PackageValidationError):
        packages.export_package_directory(settings, destination, **kwargs)
    assert_no_staging(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction API")
@pytest.mark.parametrize("kind", ["source", "destination_parent"])
def test_export_rejects_windows_junctions(tmp_path, kind):
    settings, sources, destination = export_board(tmp_path)
    link = tmp_path / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(tmp_path)],
                            capture_output=True, text=True)
    if result.returncode:
        pytest.skip(f"junction creation unavailable: {result.stderr}")
    if kind == "source":
        settings["buttons"]["paths"][49] = str(link / sources[0].name)
    else:
        destination = link / "exported"
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.export_package_directory(settings, destination)
    assert caught.value.code == "link"
    assert not destination.exists()
    assert_no_staging(tmp_path)


def import_fixture(tmp_path):
    root = write_package(tmp_path / "package")
    staging = tmp_path / "staging"
    staging.mkdir()
    return root, staging


def test_prepare_export_preserves_all_slots_and_application_state(tmp_path, monkeypatch):
    settings, sources, package = export_board(tmp_path, ("Grüße.MP3", "music.WAV"))
    settings["buttons"]["paths"][0] = str(sources[0])
    exported = packages.export_package_directory(settings, package)
    staging = tmp_path / "staging"
    staging.mkdir()
    fake_home = tmp_path / "home"
    active = fake_home / ".jingleplayer/jingleplayer_settings.json"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"keep active settings")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: pytest.fail("must not access home")))
    originals = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in (*package.rglob("*"), active, *sources) if p.is_file()}
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    prepared = packages.prepare_package_import(package, staging)
    assert isinstance(prepared, packages.PreparedImport)
    assert prepared.source_directory == package
    assert prepared.preparation_directory.parent == staging
    assert prepared.source_package == exported
    assert packages.validate_package_directory(prepared.preparation_directory) == exported
    assert len(prepared.settings["buttons"]["paths"]) == 50
    paths = prepared.settings["buttons"]["paths"]
    assert paths[0] == paths[49] and paths[48] != paths[49]
    assert len(prepared.audio_paths) == 2
    for asset in exported.assets:
        target = prepared.audio_paths[asset.path]
        assert target.is_absolute() and target.is_relative_to(prepared.preparation_directory)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == asset.sha256
        assert target.stat().st_size == asset.size
    for field in ("window_size", "volume", "fadeout_duration", "button_height"):
        assert prepared.settings[field] == exported.settings[field]
    for field in ("texts", "colors", "volumes", "per_row"):
        assert prepared.settings["buttons"][field] == exported.settings["buttons"][field]
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in originals} == originals
    prepared.settings["buttons"]["texts"][0] = "detached"
    assert prepared.source_package.settings["buttons"]["texts"][0] != "detached"
    assert Path.cwd() == elsewhere


def test_prepare_all_fifty_slots(tmp_path):
    settings, _, root = export_board(tmp_path, tuple(f"{i}.wav" for i in range(50)))
    packages.export_package_directory(settings, root)
    staging = tmp_path / "staging"
    staging.mkdir()
    prepared = packages.prepare_package_import(root, staging)
    assert len(prepared.audio_paths) == 50
    assert len(set(prepared.settings["buttons"]["paths"])) == 50


def test_prepare_empty_board_and_successive_isolation(tmp_path):
    manifest, settings = data(())
    root = write_package(tmp_path / "package", manifest, settings)
    staging = tmp_path / "staging"
    staging.mkdir()
    sentinel = staging / "unrelated"
    sentinel.mkdir()
    (sentinel / "keep").write_bytes(b"keep")
    first = packages.prepare_package_import(root, staging)
    second = packages.prepare_package_import(root, staging)
    assert first.preparation_directory != second.preparation_directory
    assert first.audio_paths == second.audio_paths == {}
    assert first.settings["buttons"]["paths"] == [""] * 50
    assert packages.validate_package_directory(first.preparation_directory).assets == ()
    assert (sentinel / "keep").read_bytes() == b"keep"


def test_prepare_nested_unicode_and_case_extensions(tmp_path):
    manifest, settings = data(("Musik/嵐/é.MP3", "Musik/音楽.WAV"))
    root = write_package(tmp_path / "package", manifest, settings)
    staging = tmp_path / "staging"
    staging.mkdir()
    prepared = packages.prepare_package_import(root, staging)
    assert set(prepared.audio_paths) == {a["path"] for a in manifest["assets"]}
    assert packages.validate_package_directory(prepared.preparation_directory) == prepared.source_package


@pytest.mark.parametrize("kind", ["manifest", "settings", "version", "traversal", "missing", "hash", "size"])
def test_prepare_rejects_invalid_packages_before_creation(tmp_path, kind):
    root, staging = import_fixture(tmp_path)
    if kind in ("manifest", "version", "traversal"):
        path = root / packages.MANIFEST_NAME
        value = json.loads(path.read_text())
        if kind == "manifest":
            path.write_text("{")
        else:
            if kind == "version":
                value["package_version"] = 2
            else:
                value["assets"][0]["path"] = "Musik/../escape.wav"
            path.write_text(json.dumps(value))
    elif kind == "settings":
        path = root / packages.SETTINGS_NAME
        value = json.loads(path.read_text())
        value["buttons"]["paths"] = []
        path.write_text(json.dumps(value))
    else:
        asset = root / "Musik/example.wav"
        if kind == "missing":
            asset.unlink()
        else:
            asset.write_bytes(b"bad" if kind == "hash" else b"longer")
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(root, staging)
    assert not list(staging.iterdir())


@pytest.mark.parametrize("kind", ["relative_source", "relative_staging", "traversal", "inside_source", "same_root", "file"])
def test_prepare_rejects_unsafe_layouts(tmp_path, kind):
    root, staging = import_fixture(tmp_path)
    source_arg, staging_arg = root, staging
    if kind == "relative_source":
        source_arg = "package"
    elif kind == "relative_staging":
        staging_arg = "staging"
    elif kind == "traversal":
        staging_arg = staging / ".." / "staging"
    elif kind == "inside_source":
        staging_arg = root / "Musik"
    elif kind == "same_root":
        staging_arg = root
    else:
        staging_arg = tmp_path / "file"
        staging_arg.write_bytes(b"keep")
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(source_arg, staging_arg)
    assert not list(staging.iterdir())


@pytest.mark.parametrize("point", ["copy", "partial_copy", "metadata", "prepared_validation"])
def test_prepare_failure_cleans_only_owned_files(tmp_path, monkeypatch, point):
    root, staging = import_fixture(tmp_path)
    sentinel = staging / ".jingleplayer-import-unrelated"
    sentinel.mkdir()
    (sentinel / "keep").write_bytes(b"keep")
    original = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    if point == "copy":
        monkeypatch.setattr(packages, "_copy_asset", lambda *a, **k: (_ for _ in ()).throw(OSError("copy failed")))
    elif point == "partial_copy":
        monkeypatch.setattr(packages.os, "fsync", lambda *a: (_ for _ in ()).throw(OSError("write failed")))
    elif point == "metadata":
        write_json = packages._write_export_json

        def fail_metadata(path, contents, **kwargs):
            write_json(path, contents, **kwargs)
            raise OSError("metadata failure")

        monkeypatch.setattr(packages, "_write_export_json", fail_metadata)
    else:
        validate = packages.validate_package_directory

        def fail_prepared(path):
            if Path(path).parent == staging:
                raise packages.PackageValidationError("integrity", str(path), "injected corruption")
            return validate(path)

        monkeypatch.setattr(packages, "validate_package_directory", fail_prepared)
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(root, staging)
    assert list(staging.iterdir()) == [sentinel]
    assert (sentinel / "keep").read_bytes() == b"keep"
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == original


@pytest.mark.parametrize("kind", ["before_copy", "during_copy", "copied_file", "metadata_after_copy"])
def test_prepare_detects_source_and_copy_changes(tmp_path, monkeypatch, kind):
    root, staging = import_fixture(tmp_path)
    copy_asset = packages._copy_asset
    source_file = root / "Musik/example.wav"

    def changed_copy(source, target, before, remaining, **kwargs):
        if kind == "before_copy":
            source_file.write_bytes(b"xyz")  # Same size, new manifest mismatch.
            before = source_file.stat()
        result = copy_asset(source, target, before, remaining, **kwargs)
        if kind == "copied_file":
            target.write_bytes(b"xyz")
        elif kind == "metadata_after_copy":
            path = root / packages.SETTINGS_NAME
            value = json.loads(path.read_text())
            value["volume"] = 42
            path.write_text(json.dumps(value))
        return result

    if kind == "during_copy":
        fsync = packages.os.fsync

        def mutate(fd):
            fsync(fd)
            source_file.write_bytes(b"changed during copy")

        monkeypatch.setattr(packages.os, "fsync", mutate)
    else:
        monkeypatch.setattr(packages, "_copy_asset", changed_copy)
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(root, staging)
    assert not list(staging.iterdir())


@pytest.mark.parametrize("limit,value", [("MAX_ASSET_BYTES", 1), ("MAX_TOTAL_BYTES", 1), ("MAX_ASSETS", 0)])
def test_prepare_enforces_limits(tmp_path, monkeypatch, limit, value):
    root, staging = import_fixture(tmp_path)
    monkeypatch.setattr(packages, limit, value)
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(root, staging)
    assert not list(staging.iterdir())


def test_prepare_detects_future_tampering_by_revalidation(tmp_path):
    root, staging = import_fixture(tmp_path)
    prepared = packages.prepare_package_import(root, staging)
    next(iter(prepared.audio_paths.values())).write_bytes(b"bad")
    with pytest.raises(packages.PackageValidationError, match="SHA-256"):
        packages.validate_package_directory(prepared.preparation_directory)


@pytest.mark.parametrize("kind", ["expected_file", "unexpected_file", "replaced_root"])
def test_prepare_races_fail_closed_without_deleting_intruder_content(tmp_path, monkeypatch, kind):
    root, staging = import_fixture(tmp_path)
    copy_asset = packages._copy_asset
    saved_root = None

    def racing_copy(source, target, before, remaining, **kwargs):
        nonlocal saved_root
        prepared = target.parent.parent
        if kind == "expected_file":
            target.write_bytes(b"racing file")
        elif kind == "unexpected_file":
            (prepared / "unrelated").write_bytes(b"racing file")
            raise OSError("injected failure")
        else:
            saved_root = staging / "moved-owned-root"
            prepared.rename(saved_root)
            prepared.mkdir()
            (prepared / "unrelated").write_bytes(b"racing file")
            raise OSError("injected failure")
        return copy_asset(source, target, before, remaining, **kwargs)

    monkeypatch.setattr(packages, "_copy_asset", racing_copy)
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.prepare_package_import(root, staging)
    assert caught.value.code == "cleanup"
    assert any(p.read_bytes() == b"racing file" for p in staging.rglob("*") if p.is_file())


@pytest.mark.parametrize("kind", ["source_root", "source_asset", "source_directory", "staging"])
def test_prepare_rejects_symlinks(tmp_path, kind):
    root, staging = import_fixture(tmp_path)
    if kind == "source_root":
        link = tmp_path / "linked-package"
        symlink_or_skip(link, root, True)
        root = link
    elif kind == "staging":
        link = tmp_path / "linked-staging"
        symlink_or_skip(link, staging, True)
        staging = link
    else:
        target = root / ("Musik/example.wav" if kind == "source_asset" else "Musik")
        outside = tmp_path / "outside"
        target.rename(outside)
        symlink_or_skip(target, outside, kind == "source_directory")
    with pytest.raises(packages.PackageValidationError):
        packages.prepare_package_import(root, staging)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction API")
@pytest.mark.parametrize("kind", ["source", "staging"])
def test_prepare_rejects_windows_junctions(tmp_path, kind):
    root, staging = import_fixture(tmp_path)
    link = tmp_path / "junction"
    original = root if kind == "source" else staging
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(original)],
                            capture_output=True, text=True)
    if result.returncode:
        pytest.skip(f"junction creation unavailable: {result.stderr}")
    with pytest.raises(packages.PackageValidationError) as caught:
        packages.prepare_package_import(link if kind == "source" else root,
                                        link if kind == "staging" else staging)
    assert caught.value.code == "link"
    assert not list(staging.iterdir())


def activation_fixture(tmp_path):
    source_settings, _, package = export_board(tmp_path, ("a.MP3", "b.WAV"))
    source_settings["buttons"]["paths"][0] = source_settings["buttons"]["paths"][49]
    packages.export_package_directory(source_settings, package)
    staging = tmp_path / "staging"
    staging.mkdir()
    prepared = packages.prepare_package_import(package, staging)
    settings_path = tmp_path / "active.json"
    receiver = board()
    receiver.update(window_size=[1234, 777], volume=37, last_folder=str(tmp_path / "local audio"),
                    local_extension={"keep": True})
    receiver["buttons"]["texts"][0] = "old board"
    receiver["buttons"]["paths"][49] = str(tmp_path / "old.wav")
    settings_path.write_bytes(json.dumps(receiver, indent=4, ensure_ascii=False).encode("utf-8"))
    library, recovery = tmp_path / "library", tmp_path / "recovery"
    library.mkdir()
    recovery.mkdir()
    return prepared, settings_path, library, recovery


def activate(args):
    return packages.activate_prepared_import(*args)


def test_activate_end_to_end_preserves_receiver_and_all_slots(tmp_path, monkeypatch):
    args = activation_fixture(tmp_path)
    prepared, settings_path, library, recoveries = args
    caller_snapshot = deepcopy(prepared)
    prior = settings_path.read_bytes()
    originals = {p: p.read_bytes() for root in (prepared.source_directory, prepared.preparation_directory)
                 for p in root.rglob("*") if p.is_file()}
    (library / "unrelated.wav").write_bytes(b"keep")
    (recoveries / "existing.json").write_bytes(b"keep")
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: pytest.fail("no home lookup")))
    result = activate(args)
    assert isinstance(result, packages.ActivationResult) and result.outcome == "committed"
    assert result.installed_directory.parent == library
    assert result.recovery_directory.parent == recoveries
    current = json.loads(settings_path.read_bytes())
    assert current == result.settings
    assert current["window_size"] == [1234, 777] and current["volume"] == 37
    assert current["last_folder"] == str(tmp_path / "local audio")
    assert current["local_extension"] == {"keep": True}
    assert len(current["buttons"]["paths"]) == 50
    assert current["buttons"]["paths"][0] == current["buttons"]["paths"][49]
    for key in ("texts", "colors", "volumes", "per_row"):
        assert current["buttons"][key] == prepared.source_package.settings["buttons"][key]
    for path in current["buttons"]["paths"]:
        if path:
            assert Path(path).is_absolute() and Path(path).is_relative_to(result.installed_directory)
            assert Path(path).is_file() and not Path(path).is_relative_to(prepared.preparation_directory)
    assert packages.validate_package_directory(result.installed_directory) == prepared.source_package
    snapshot = result.recovery_directory / packages.SETTINGS_NAME
    assert snapshot.read_bytes() == prior
    meta = json.loads((result.recovery_directory / "recovery.json").read_text())
    assert meta["settings_sha256"] == hashlib.sha256(prior).hexdigest() == result.previous_sha256
    assert meta["settings_size"] == len(prior)
    assert meta["proposed_settings_sha256"] == hashlib.sha256(settings_path.read_bytes()).hexdigest()
    assert prepared == caller_snapshot
    assert {p: p.read_bytes() for p in originals} == originals
    assert (library / "unrelated.wav").read_bytes() == b"keep"
    assert (recoveries / "existing.json").read_bytes() == b"keep"
    assert not (settings_path.parent / "jingleplayer_settings.pre-pyside6.json").exists()
    assert Path.cwd() == unrelated


def test_activate_repeated_unique_operations(tmp_path):
    args = activation_fixture(tmp_path)
    first = activate(args)
    first_bytes = args[1].read_bytes()
    second = activate(args)
    assert first.installed_directory != second.installed_directory
    assert first.recovery_directory != second.recovery_directory
    assert (second.recovery_directory / packages.SETTINGS_NAME).read_bytes() == first_bytes
    assert packages.validate_package_directory(first.installed_directory) == args[0].source_package


def test_activate_fifty_distinct_assets_including_hidden_slots(tmp_path):
    args = list(activation_fixture(tmp_path))
    asset_root = tmp_path / "fifty-sources"
    asset_root.mkdir()
    settings, _, package = export_board(asset_root, tuple(f"{i}.wav" for i in range(50)))
    packages.export_package_directory(settings, package)
    args[0] = packages.prepare_package_import(package, tmp_path / "staging")
    result = activate(args)
    assert len(set(result.settings["buttons"]["paths"])) == 50
    assert len(packages.validate_package_directory(result.installed_directory).assets) == 50


@pytest.mark.parametrize("kind", ["recovery", "installed"])
def test_activate_final_revalidation_blocks_late_corruption(tmp_path, monkeypatch, kind):
    args = activation_fixture(tmp_path)
    original = args[1].read_bytes()
    temp_factory = packages.tempfile.NamedTemporaryFile

    def corrupt_before_commit(*a, **kw):
        if kind == "recovery":
            next(args[3].glob("*/jingleplayer_settings.json")).write_bytes(b"changed")
        else:
            next(args[2].glob("import-*/Musik/*")).write_bytes(b"changed")
        return temp_factory(*a, **kw)

    monkeypatch.setattr(packages.tempfile, "NamedTemporaryFile", corrupt_before_commit)
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert args[1].read_bytes() == original
    assert caught.value.outcome == "not_committed"


def test_activate_detects_same_byte_settings_file_replacement(tmp_path, monkeypatch):
    args = activation_fixture(tmp_path)
    original = args[1].read_bytes()
    publish = packages._publish_directory

    def replace_receiver(staged, installed):
        publish(staged, installed)
        replacement = args[1].with_name("concurrent.json")
        replacement.write_bytes(original)
        packages.os.replace(replacement, args[1])

    monkeypatch.setattr(packages, "_publish_directory", replace_receiver)
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert caught.value.outcome == "not_committed"
    assert args[1].read_bytes() == original


@pytest.mark.parametrize("kind", ["missing", "hash", "metadata", "extra", "caller_snapshot"])
def test_activate_rejects_invalid_preparation_without_settings_change(tmp_path, kind):
    args = activation_fixture(tmp_path)
    prepared, active, library, recovery = args
    original = active.read_bytes()
    asset = next(iter(prepared.audio_paths.values()))
    if kind == "missing":
        asset.unlink()
    elif kind == "hash":
        asset.write_bytes(b"corrupted")
    elif kind == "metadata":
        (prepared.preparation_directory / packages.MANIFEST_NAME).write_bytes(b"{")
    elif kind == "extra":
        (prepared.preparation_directory / "extra").write_bytes(b"bad")
    else:
        prepared.source_package.settings["volume"] = 32
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert caught.value.outcome == "not_committed"
    assert active.read_bytes() == original
    assert not list(library.iterdir()) and not list(recovery.iterdir())


def test_activate_ignores_mutable_mapped_paths_and_settings(tmp_path):
    args = activation_fixture(tmp_path)
    args[0].settings["buttons"]["paths"][0] = "unsafe mapping"
    args[0].audio_paths.clear()
    result = activate(args)
    assert result.settings["buttons"]["paths"][0].startswith(str(result.installed_directory))


@pytest.mark.parametrize("raw", [b"{", b"[]", b'{"schema_version":99}', b'{"buttons":[]}',
                                      b'{"volume":true}', b'{"window_size":[0,5]}'])
def test_activate_rejects_invalid_receiver(tmp_path, raw):
    args = activation_fixture(tmp_path)
    args[1].write_bytes(raw)
    with pytest.raises(packages.ActivationError):
        activate(args)
    assert args[1].read_bytes() == raw
    assert not list(args[2].iterdir()) and not list(args[3].iterdir())


@pytest.mark.parametrize("version", [None, 1])
def test_activate_legacy_receiver_backup_and_defaults(tmp_path, version):
    args = activation_fixture(tmp_path)
    old = {"buttons": {"texts": ["legacy"]}}
    if version is not None:
        old["schema_version"] = version
    original = json.dumps(old).encode()
    args[1].write_bytes(original)
    result = activate(args)
    backup = args[1].with_name("jingleplayer_settings.pre-pyside6.json")
    assert backup.read_bytes() == original
    assert result.settings["schema_version"] == 2
    assert result.settings["window_size"] == [800, 600] and result.settings["volume"] == 100
    assert "last_folder" not in result.settings
    assert (result.recovery_directory / packages.SETTINGS_NAME).read_bytes() == original


def test_activate_conflicting_legacy_backup_blocks_commit(tmp_path):
    args = activation_fixture(tmp_path)
    original = b'{"schema_version":1}'
    args[1].write_bytes(original)
    backup = args[1].with_name("jingleplayer_settings.pre-pyside6.json")
    backup.write_bytes(b"existing backup")
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert args[1].read_bytes() == original
    assert backup.read_bytes() == b"existing backup"
    assert caught.value.recovery_directory.is_dir()


@pytest.mark.parametrize("point", ["copy", "installed_hash", "recovery", "settings_write", "replace"])
def test_activate_failures_preserve_active_and_report_recovery(tmp_path, monkeypatch, point):
    args = activation_fixture(tmp_path)
    original = args[1].read_bytes()
    if point == "copy":
        monkeypatch.setattr(packages, "_copy_asset", lambda *a, **k: (_ for _ in ()).throw(OSError("copy failure")))
    elif point == "installed_hash":
        publish = packages._publish_directory

        def corrupt(staged, installed):
            publish(staged, installed)
            next((installed / "Musik").iterdir()).write_bytes(b"corrupted installed asset")

        monkeypatch.setattr(packages, "_publish_directory", corrupt)
    elif point == "recovery":
        monkeypatch.setattr(packages, "_write_recovery_bytes", lambda *a: (_ for _ in ()).throw(OSError("recovery failure")))
    elif point == "settings_write":
        named = packages.tempfile.NamedTemporaryFile

        def fail_temp(*a, **k):
            raise OSError("settings write failed")

        monkeypatch.setattr(packages.tempfile, "NamedTemporaryFile", fail_temp)
    else:
        monkeypatch.setattr(packages.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert args[1].read_bytes() == original
    assert caught.value.outcome == "not_committed"
    assert caught.value.recovery_directory.is_dir()
    assert caught.value.recovery_directory in caught.value.retained_paths
    if point != "recovery":
        assert (caught.value.recovery_directory / packages.SETTINGS_NAME).read_bytes() == original
        assert (caught.value.recovery_directory / "recovery.json").is_file()


def test_activate_detects_concurrent_settings_change(tmp_path, monkeypatch):
    args = activation_fixture(tmp_path)
    publish = packages._publish_directory
    concurrent = b'{"schema_version":2,"concurrent":"keep"}'

    def race(staged, installed):
        publish(staged, installed)
        args[1].write_bytes(concurrent)

    monkeypatch.setattr(packages, "_publish_directory", race)
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert caught.value.outcome == "not_committed"
    assert args[1].read_bytes() == concurrent
    assert caught.value.installed_directory in caught.value.retained_paths


@pytest.mark.parametrize("changed_after", [False, True])
def test_activate_exception_after_replace_never_restores(tmp_path, monkeypatch, changed_after):
    args = activation_fixture(tmp_path)
    replace = packages.os.replace
    concurrent = b'{"another":"writer"}'

    def replace_then_fail(source, target):
        replace(source, target)
        if changed_after:
            args[1].write_bytes(concurrent)
        raise OSError("exception after commit")

    monkeypatch.setattr(packages.os, "replace", replace_then_fail)
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert caught.value.outcome == ("indeterminate" if changed_after else "committed")
    if changed_after:
        assert args[1].read_bytes() == concurrent
    else:
        assert len(json.loads(args[1].read_bytes())["buttons"]["paths"]) == 50
    assert caught.value.recovery_directory.is_dir()


@pytest.mark.parametrize("kind", ["library_inside_package", "recovery_in_library", "settings_in_library", "relative"])
def test_activate_unsafe_layout_rejected(tmp_path, kind):
    args = list(activation_fixture(tmp_path))
    original = args[1].read_bytes()
    original_path = args[1]
    if kind == "library_inside_package":
        args[2] = args[0].preparation_directory / "Musik"
    elif kind == "recovery_in_library":
        args[3] = args[2]
    elif kind == "settings_in_library":
        args[1] = args[2] / "settings.json"
        args[1].write_bytes(original)
    else:
        args[1] = "active.json"
    with pytest.raises(packages.ActivationError):
        activate(args)
    assert original_path.read_bytes() == original


@pytest.mark.parametrize("kind", ["prepared_asset", "library", "recovery", "active"])
def test_activate_rejects_symlinks(tmp_path, kind):
    args = list(activation_fixture(tmp_path))
    if kind == "prepared_asset":
        target = next(iter(args[0].audio_paths.values()))
        outside = tmp_path / "outside.wav"
        target.rename(outside)
        symlink_or_skip(target, outside)
    else:
        index = {"library": 2, "recovery": 3, "active": 1}[kind]
        link = tmp_path / "linked"
        symlink_or_skip(link, args[index], kind != "active")
        args[index] = link
    with pytest.raises(packages.ActivationError):
        activate(args)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction API")
@pytest.mark.parametrize("kind", ["prepared", "library", "recovery"])
def test_activate_rejects_junctions(tmp_path, kind):
    args = list(activation_fixture(tmp_path))
    target = args[0].preparation_directory / "Musik" if kind == "prepared" else args[2 if kind == "library" else 3]
    outside = tmp_path / "outside"
    target.rename(outside)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)],
                            capture_output=True, text=True)
    if result.returncode:
        pytest.skip(f"junction creation unavailable: {result.stderr}")
    original = args[1].read_bytes()
    with pytest.raises(packages.ActivationError):
        activate(args)
    assert args[1].read_bytes() == original


def test_activate_library_destination_race_preserves_unrelated(tmp_path, monkeypatch):
    args = activation_fixture(tmp_path)
    publish = packages._publish_directory
    original = args[1].read_bytes()

    def race(staged, installed):
        installed.mkdir()
        (installed / "unrelated").write_bytes(b"keep")
        publish(staged, installed)

    monkeypatch.setattr(packages, "_publish_directory", race)
    with pytest.raises(packages.ActivationError) as caught:
        activate(args)
    assert (caught.value.installed_directory / "unrelated").read_bytes() == b"keep"
    assert args[1].read_bytes() == original
    assert caught.value.installed_directory in caught.value.retained_paths
