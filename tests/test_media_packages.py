from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import wave
import zipfile

import pytest
from PySide6.QtGui import QImage, QColor

import jingleplayer_media_packages as media
import jingleplayer_packages as legacy
import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage
from test_presets import schema2


def blank():
    data = schema2()
    data["buttons"]["paths"] = [""] * 50
    return presets.migrate_settings_to_schema3(data)


def wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(44100)
        stream.writeframes(b"\0\0" * 100)
    return str(path)


@pytest.fixture
def bundle(tmp_path):
    first = wav(tmp_path / "source/one/same.wav")
    second = wav(tmp_path / "source/two/same.wav")
    image = QImage(60, 30, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    background = tmp_path / "source/Grüße 音楽.png"
    assert image.save(str(background))
    document = blank()
    source_id = document["active_preset_id"]
    document = presets.duplicate_preset(document, source_id, "Second")
    document = presets.duplicate_preset(document, source_id, "Third", activate=True)
    for preset, mode in zip(document["presets"], ("sequential", "random", "manual")):
        preset["buttons"]["paths"][49] = first
        preset["buttons"]["paths"][0] = second
        preset["audio_pools"] = {"50": {"audio_pool": [first, second], "audio_pool_mode": mode, "selected_audio": second}}
        preset["background_image"] = str(background)
    archive = tmp_path / "Bundle.zip"
    validated = media.export_archive(document, archive, source_base=tmp_path, name="Crashers 音楽")
    directory = tmp_path / "data"
    directory.mkdir()
    settings = directory / "jingleplayer_settings.json"
    receiver = blank()
    receiver.update(window_size=[999, 777], volume=17, last_folder="local-folder")
    settings.write_text(json.dumps(receiver), encoding="utf-8")
    return document, archive, validated, settings


def rewrite(source, destination, transform_manifest=None, transform_entry=None, extra=None):
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(destination, "w") as outgoing:
        for info in incoming.infolist():
            raw = incoming.read(info)
            if info.filename == "manifest.json" and transform_manifest:
                value = json.loads(raw)
                transform_manifest(value)
                raw = json.dumps(value).encode("utf-8")
            if transform_entry:
                info, raw = transform_entry(info, raw)
            outgoing.writestr(info, raw)
        if extra:
            outgoing.writestr(*extra)


def test_complete_roundtrip_references_names_hidden_slots_restart_and_sources_removed(bundle):
    document, archive, package, settings = bundle
    assert len(package.settings["presets"]) == 3 and len(package.assets) == 3
    assert {a.path for a in package.assets if a.kind == "audio"} == {"audio/same.wav", "audio/same-2.wav"}
    assert package.settings["last_folder"] == ""
    assert all(not Path(path).is_absolute() and "\\" not in path for path, _ in media._refs(package.settings))
    before = settings.read_bytes()
    result = media.import_archive(archive, settings, confirmed=package)
    assert result.outcome == "committed"
    assert result.installed_directory.parent == settings.parent / "imported_soundboards"
    assert result.installed_directory.name.startswith("crashers-")
    assert (result.installed_directory / "manifest.json").is_file()
    assert (result.recovery_directory / legacy.SETTINGS_NAME).read_bytes() == before
    saved = storage.load_preset_settings(settings).data
    assert len(saved["presets"]) == 4 and saved["window_size"] == [999, 777] and saved["volume"] == 17
    assert saved["last_folder"] == "local-folder"
    assert len({p["id"] for p in saved["presets"]}) == 4
    for original, imported in zip(document["presets"], saved["presets"][1:]):
        assert original["id"] != imported["id"]
        config = imported["audio_pools"]["50"]
        assert config["audio_pool_mode"] == original["audio_pools"]["50"]["audio_pool_mode"]
        assert [Path(p).name for p in config["audio_pool"]] == ["same-2.wav", "same.wav"]
        assert config["selected_audio"] == config["audio_pool"][1]
        assert imported["buttons"]["paths"][49] == config["audio_pool"][0]
        assert imported["buttons"]["colors"] == original["buttons"]["colors"]
        for key in ("texts", "volumes", "per_row"):
            assert imported["buttons"][key] == original["buttons"][key]
        for key in ("button_height", "fadeout_duration"):
            assert imported[key] == original[key]
    for path, _ in set(media._refs(document)):
        Path(path).unlink()
    archive.unlink()
    restarted = storage.load_preset_settings(settings).data
    for path, kind in media._refs({**restarted, "presets": restarted["presets"][1:]}):
        assert Path(path).is_file() and Path(path).is_relative_to(result.installed_directory)
        assert "import-staging" not in path
        if kind == "audio":
            with wave.open(path) as sound:
                assert sound.getnframes() == 100
        else:
            media._image(Path(path))


def test_repeated_import_has_unique_directories_ids_and_names(bundle):
    _, archive, _, settings = bundle
    a = media.import_archive(archive, settings)
    b = media.import_archive(archive, settings)
    assert a.installed_directory != b.installed_directory
    value = storage.load_preset_settings(settings).data
    assert len(value["presets"]) == 7
    assert len({p["id"] for p in value["presets"]}) == 7
    assert len({presets._name_key(p["name"]) for p in value["presets"]}) == 7


@pytest.mark.parametrize("name", ["../evil.wav", "/tmp/evil.wav", "C:/evil.wav", "audio/../evil.wav",
                                 "audio\\evil.wav", "audio/CON.wav", "audio/a?.wav", "audio/nested/x.wav"])
def test_unsafe_zip_paths_rejected_before_extraction(bundle, tmp_path, name):
    _, archive, _, settings = bundle
    unsafe = tmp_path / "unsafe.zip"
    rewrite(archive, unsafe, extra=(name, b"bad"))
    before = settings.read_bytes()
    with pytest.raises(legacy.ActivationError):
        media.import_archive(unsafe, settings)
    assert settings.read_bytes() == before
    assert not list((settings.parent / "imported_soundboards").iterdir())
    assert not list((settings.parent / "import-staging").iterdir())


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFDIR])
def test_nonregular_zip_members_rejected(bundle, tmp_path, mode):
    _, archive, _, _ = bundle
    path = tmp_path / "link.zip"

    def change(info, raw):
        if info.filename.startswith("audio/"):
            info.create_system = 3
            info.external_attr = (mode | 0o777) << 16
        return info, raw

    rewrite(archive, path, transform_entry=change)
    with pytest.raises(legacy.PackageValidationError, match="forbidden"):
        media.validate_archive(path)


@pytest.mark.parametrize("mutation", ["hash", "pool", "image", "version", "duplicate", "absolute", "selected", "unreferenced"])
def test_invalid_manifest_is_rejected(bundle, tmp_path, mutation):
    _, archive, _, _ = bundle
    path = tmp_path / "bad.zip"

    def change(value):
        preset = value["settings"]["presets"][0]
        if mutation == "hash":
            value["assets"][0]["sha256"] = "0" * 64
        elif mutation == "pool":
            preset["audio_pools"]["50"]["audio_pool_mode"] = "unknown"
        elif mutation == "image":
            preset["background_image"] = "backgrounds/missing.png"
        elif mutation == "version":
            value["package_version"] = 99
        elif mutation == "duplicate":
            value["assets"].append(deepcopy(value["assets"][0]))
        elif mutation == "absolute":
            preset["buttons"]["paths"][0] = "C:/original.wav"
        elif mutation == "selected":
            preset["audio_pools"]["50"]["selected_audio"] = "C:/old.wav"
        else:
            value["assets"].pop()

    rewrite(archive, path, transform_manifest=change)
    with pytest.raises((legacy.PackageValidationError, presets.PresetValidationError)):
        media.validate_archive(path)


def test_duplicate_archive_and_unicode_case_collision_rejected(bundle, tmp_path):
    _, archive, _, _ = bundle
    for name in ("audio/same.wav", "audio/SAME.WAV"):
        path = tmp_path / ("duplicate-" + name.rsplit("/", 1)[1] + ".zip")
        if name == "audio/same.wav":
            with pytest.warns(UserWarning, match="Duplicate name"):
                rewrite(archive, path, extra=(name, b"duplicate"))
        else:
            rewrite(archive, path, extra=(name, b"duplicate"))
        with pytest.raises(legacy.PackageValidationError, match="duplicate"):
            media.validate_archive(path)


def test_zip_bomb_and_entry_budgets_checked_before_extraction(bundle, tmp_path, monkeypatch):
    _, archive, _, _ = bundle
    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as out:
        out.writestr("audio/bomb.wav", b"\0" * 1000000)
    with pytest.raises(legacy.PackageValidationError, match="ratio"):
        media.validate_archive(bomb)
    monkeypatch.setattr(media, "MAX_ENTRIES", 2)
    with pytest.raises(legacy.PackageValidationError, match="index"):
        media.validate_archive(archive)


def test_corrupt_zip_and_crc_rejected(bundle, tmp_path):
    _, archive, _, _ = bundle
    path = tmp_path / "truncated.zip"
    path.write_bytes(archive.read_bytes()[:80])
    with pytest.raises(legacy.PackageValidationError):
        media.validate_archive(path)
    raw = bytearray(archive.read_bytes())
    at = raw.index(b"RIFF")
    raw[at] ^= 1
    path.write_bytes(raw)
    with pytest.raises(legacy.PackageValidationError):
        media.validate_archive(path)


@pytest.mark.parametrize("failure", ["extract", "save", "conflict"])
def test_failure_rolls_back_media_without_changing_settings(bundle, monkeypatch, failure):
    _, archive, _, settings = bundle
    before = settings.read_bytes()
    token = storage.load_preset_settings(settings)
    if failure == "extract":
        original = media._read_member

        def broken(*args, **kwargs):
            if args[1].filename.startswith("audio/"):
                raise OSError("disk full")
            return original(*args, **kwargs)

        monkeypatch.setattr(media, "_read_member", broken)
    elif failure == "save":
        monkeypatch.setattr(storage.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("save denied")))
    else:
        settings.write_bytes(before + b" ")
        before = settings.read_bytes()
    with pytest.raises(legacy.ActivationError) as error:
        media.import_archive(archive, settings, expected=token)
    assert error.value.outcome == "not_committed"
    assert settings.read_bytes() == before
    assert not list((settings.parent / "imported_soundboards").iterdir())
    assert not list((settings.parent / "import-staging").iterdir())


def test_indeterminate_save_retains_media_and_reports_it(bundle, monkeypatch):
    _, archive, _, settings = bundle

    def unknown(*a, **kw):
        raise storage.PresetStorageError("write", settings, "unknown", outcome="indeterminate")

    monkeypatch.setattr(storage, "save_preset_settings", unknown)
    with pytest.raises(legacy.ActivationError) as error:
        media.import_archive(archive, settings)
    assert error.value.outcome == "indeterminate"
    assert error.value.installed_directory in error.value.retained_paths
    assert error.value.installed_directory.is_dir()


@pytest.mark.parametrize("failure", ["missing", "image", "copy", "publish"])
def test_export_failure_leaves_no_destination_and_preserves_source(bundle, tmp_path, monkeypatch, failure):
    document, _, _, _ = bundle
    before = deepcopy(document)
    target = tmp_path / "failed.zip"
    if failure == "missing":
        Path(document["presets"][0]["audio_pools"]["50"]["audio_pool"][0]).unlink()
    elif failure == "image":
        Path(document["presets"][0]["background_image"]).write_bytes(b"bad image")
    elif failure == "copy":
        monkeypatch.setattr(legacy, "_copy_asset", lambda *a, **kw: (_ for _ in ()).throw(OSError("copy failed")))
    else:
        monkeypatch.setattr(legacy, "_publish_directory", lambda *a: (_ for _ in ()).throw(OSError("publish failed")))
    with pytest.raises(legacy.PackageValidationError):
        media.export_archive(document, target, source_base=tmp_path)
    assert not target.exists() and document == before
    assert not list(tmp_path.glob(".jingleplayer-export3-*"))


def test_export_refuses_overwrite_and_symlink_sources(bundle, tmp_path):
    document, archive, _, _ = bundle
    original = archive.read_bytes()
    with pytest.raises(legacy.PackageValidationError):
        media.export_archive(document, archive, source_base=tmp_path)
    assert archive.read_bytes() == original
    link = tmp_path / "link.wav"
    try:
        link.symlink_to(next(iter(media._refs(document)))[0])
    except OSError:
        pytest.skip("Symlink creation requires host permissions")
    document["presets"][0]["buttons"]["paths"][1] = str(link)
    with pytest.raises(legacy.PackageValidationError):
        media.export_archive(document, tmp_path / "symlink.zip", source_base=tmp_path)


def test_corrupt_image_with_valid_crc_and_hash_is_rejected_and_rolled_back(bundle, tmp_path):
    _, archive, _, settings = bundle
    bad = b"not a PNG or JPEG"
    target = tmp_path / "bad-image.zip"

    def manifest(value):
        image = next(a for a in value["assets"] if a["kind"] == "background")
        image.update(size=len(bad), sha256=hashlib.sha256(bad).hexdigest())

    rewrite(archive, target, transform_manifest=manifest,
            transform_entry=lambda info, raw: (info, bad if info.filename.startswith("backgrounds/") else raw))
    before = settings.read_bytes()
    with pytest.raises(legacy.ActivationError) as error:
        media.import_archive(target, settings)
    assert error.value.outcome == "not_committed" and settings.read_bytes() == before
    assert not list((settings.parent / "imported_soundboards").iterdir())
    assert not list((settings.parent / "import-staging").iterdir())


@pytest.mark.parametrize("limit", ["MAX_ASSET_BYTES", "MAX_TOTAL_BYTES", "MAX_IMAGE_BYTES", "MAX_JSON_BYTES"])
def test_archive_byte_budgets_are_enforced(bundle, monkeypatch, limit):
    _, archive, _, _ = bundle
    monkeypatch.setattr(media, limit, 10)
    with pytest.raises(legacy.PackageValidationError):
        media.validate_archive(archive)


def test_unicode_normalization_collision_and_duplicate_json_keys(bundle, tmp_path):
    import unicodedata
    _, archive, package, _ = bundle
    background = next(a.path for a in package.assets if a.kind == "background")
    target = tmp_path / "unicode.zip"
    rewrite(archive, target, extra=(unicodedata.normalize("NFD", background), b"duplicate"))
    with pytest.raises(legacy.PackageValidationError, match="duplicate"):
        media.validate_archive(target)
    rewrite(archive, target, transform_entry=lambda info, raw: (
        info, b'{"package_version":3,"package_version":3}' if info.filename == "manifest.json" else raw))
    with pytest.raises(legacy.PackageValidationError, match="duplicate JSON"):
        media.validate_archive(target)


def test_case_variant_active_uuid_and_preview_change_detection(bundle, tmp_path):
    _, archive, package, settings = bundle
    variant = tmp_path / "variant.zip"
    rewrite(archive, variant, transform_manifest=lambda value:
            value["settings"].update(active_preset_id=value["settings"]["active_preset_id"].upper()))
    result = media.import_archive(variant, settings)
    assert result.settings["active_preset_id"] == result.settings["presets"][-1]["id"]
    before = settings.read_bytes()
    with pytest.raises(legacy.ActivationError, match="preview"):
        media.import_archive(variant, settings, confirmed=package)
    assert settings.read_bytes() == before


@pytest.mark.parametrize("operation", ["import", "export"])
def test_exception_after_native_publish_cleans_only_own_new_data(bundle, tmp_path, monkeypatch, operation):
    document, archive, _, settings = bundle
    before = settings.read_bytes()
    original = legacy._publish_directory

    def publish_then_fail(source, target):
        original(source, target)
        raise OSError("exception after native rename")

    monkeypatch.setattr(legacy, "_publish_directory", publish_then_fail)
    if operation == "import":
        with pytest.raises(legacy.ActivationError):
            media.import_archive(archive, settings)
        assert settings.read_bytes() == before
        assert not list((settings.parent / "imported_soundboards").iterdir())
        assert not list((settings.parent / "import-staging").iterdir())
    else:
        target = tmp_path / "new.zip"
        with pytest.raises(legacy.PackageValidationError):
            media.export_archive(document, target, source_base=tmp_path)
        assert not target.exists()


def test_integrity_rechecked_inside_settings_lock_and_cleanup_refuses_foreign_content(bundle, monkeypatch):
    _, archive, _, settings = bundle
    original = storage.save_preset_settings

    def tamper(path, data, *, expected, before_commit):
        image = next(p["background_image"] for p in data["presets"] if p.get("background_image"))
        Path(image).write_bytes(b"tampered")
        return original(path, data, expected=expected, before_commit=before_commit)

    before = settings.read_bytes()
    monkeypatch.setattr(storage, "save_preset_settings", tamper)
    with pytest.raises(legacy.ActivationError) as error:
        media.import_archive(archive, settings)
    assert error.value.outcome == "not_committed" and settings.read_bytes() == before
    assert not list((settings.parent / "imported_soundboards").iterdir())


def test_cleanup_failure_reports_retained_media_without_deleting_foreign_files(bundle, monkeypatch):
    _, archive, _, settings = bundle

    def fail(path, data, *, expected, before_commit):
        image = next(p["background_image"] for p in data["presets"] if p.get("background_image"))
        (Path(image).parent / "foreign.txt").write_text("do not delete")
        raise storage.PresetStorageError("write", path, "disk failure")

    monkeypatch.setattr(storage, "save_preset_settings", fail)
    with pytest.raises(legacy.ActivationError) as error:
        media.import_archive(archive, settings)
    assert error.value.installed_directory in error.value.retained_paths
    assert (error.value.installed_directory / "backgrounds/foreign.txt").read_text() == "do not delete"
