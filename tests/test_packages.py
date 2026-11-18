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
