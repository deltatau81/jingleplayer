from copy import deepcopy
from types import SimpleNamespace
import os

import pytest

import jingleplayer_audio_pools as pools
import jingleplayer_logic as logic
import jingleplayer_packages as packages
import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage
from test_presets import schema2


def pool(paths=None, mode="sequential"):
    paths = paths if paths is not None else ["a.wav", "b.mp3", "c.wav"]
    return {"audio_pool": paths, "audio_pool_mode": mode, "selected_audio": paths[0] if paths else ""}


def document(config=None, slot=1):
    result = presets.migrate_settings_to_schema3(schema2())
    config = config if config is not None else pool()
    active = result["presets"][0]
    active["audio_pools"] = {str(slot): deepcopy(config)}
    active["buttons"]["paths"][slot - 1] = config["audio_pool"][0]
    return result


@pytest.mark.parametrize("paths", [["C:\\音楽\\a.MP3", "/tmp/b.wav"], ["relative.wav"], ["a/a.wav", "b/a.wav"]])
def test_model_paths_are_unchanged_without_filesystem_access(paths):
    source = document(pool(paths), slot=50)
    original = deepcopy(source)
    assert presets.validate_schema3_settings(source) == source
    duplicate = presets.duplicate_preset(source, source["active_preset_id"], "Copy")
    duplicate["presets"][1]["audio_pools"]["50"]["audio_pool"].append("extra.wav")
    assert source == original
    assert len(presets.extract_active_board(source)["buttons"]["paths"]) == 50


@pytest.mark.parametrize("windows", [False, True])
def test_explicit_base_and_foreign_absolute_path_semantics(monkeypatch, windows):
    from pathlib import PurePosixPath, PureWindowsPath
    path_type = PureWindowsPath if windows else PurePosixPath
    monkeypatch.setattr(pools, "Path", path_type)
    base = "C:/settings" if windows else "/settings"
    assert pools.pool_file_path("folder/a.wav", base) == path_type(base) / "folder/a.wav"
    native = "D:/audio/a.wav" if windows else "/audio/a.wav"
    assert pools.pool_file_path(native, base) == path_type(native)
    foreign = "/audio/a.wav" if windows else "D:/audio/a.wav"
    with pytest.raises(ValueError):
        pools.pool_file_path(foreign, base)
    with pytest.raises(ValueError):
        pools.pool_file_path("relative.wav", "relative-base")


@pytest.mark.parametrize("field,value", [
    ("audio_pool", []), ("audio_pool", "a.wav"), ("audio_pool", [None]),
    ("audio_pool", ["a.wav", "a.wav"]), ("audio_pool", ["a.ogg"]),
    ("audio_pool", ["x\0.wav"]), ("audio_pool_mode", "shuffle"),
    ("audio_pool_mode", []), ("selected_audio", "absent.wav"), ("selected_audio", None)])
def test_invalid_pool_rejected_without_mutation(field, value):
    data = document()
    data["presets"][0]["audio_pools"]["1"][field] = value
    before = deepcopy(data)
    with pytest.raises(presets.PresetValidationError) as caught:
        presets.validate_schema3_settings(data)
    assert caught.value.code == "pool" and "audio_pools" in caught.value.location
    assert data == before


@pytest.mark.parametrize("slot", ["0", "51", "01", 1])
def test_invalid_slot_rejected(slot):
    data = document()
    data["presets"][0]["audio_pools"] = {slot: pool()}
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


def test_conflicting_compatibility_path_and_unknown_pool_fields_rejected():
    data = document()
    data["presets"][0]["buttons"]["paths"][0] = "other.wav"
    with pytest.raises(presets.PresetValidationError, match="compatibility"):
        presets.validate_schema3_settings(data)
    data = document()
    data["presets"][0]["audio_pools"]["1"]["unknown"] = True
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(data)


def test_old_presets_do_not_gain_pool_fields():
    data = presets.migrate_settings_to_schema3(schema2())
    assert "audio_pools" not in data["presets"][0]
    assert presets.validate_schema3_settings(data) == data


def test_sequence_commits_only_success_and_wraps_and_resets():
    selector, config = pools.PoolSelector(), pool()
    assert selector.candidates(("p", 1), config) == config["audio_pool"]
    assert selector.candidates(("p", 1), config)[0] == "a.wav"  # failed attempt
    for expected in ("a.wav", "b.mp3", "c.wav", "a.wav"):
        assert selector.candidates(("p", 1), config)[0] == expected
        selector.started(("p", 1), config, expected)
    assert selector.candidates(("p", 2), config)[0] == "a.wav"
    assert selector.candidates(("other", 1), config)[0] == "a.wav"
    config["audio_pool"].reverse()
    assert selector.candidates(("p", 1), config)[0] == "c.wav"
    selector.reset()
    assert selector.states == {}


def test_random_no_immediate_repeat_and_failed_choice_keeps_last():
    selector, config = pools.PoolSelector(chooser=lambda candidates: candidates[0]), pool(mode="random")
    choices = []
    for _ in range(8):
        selected = selector.candidates(("p", 1), config)[0]
        choices.append(selected)
        selector.started(("p", 1), config, selected)
    assert all(a != b for a, b in zip(choices, choices[1:]))
    before = deepcopy(selector.states)
    selector.candidates(("p", 1), config)
    assert selector.states == before
    assert selector.candidates(("p", 1), config)[-1] == choices[-1]
    assert selector.candidates(("p", 2), config)[0] == "a.wav"
    assert set(selector.candidates(("p", 1), config)) == set(config["audio_pool"])


def test_manual_selection_is_a_path_and_one_file_can_repeat():
    selector = pools.PoolSelector()
    config = pool(mode="manual")
    config["selected_audio"] = "c.wav"
    assert selector.candidates(("p", 1), config) == ["c.wav"]
    config["audio_pool"].reverse()
    assert selector.candidates(("p", 1), config) == ["c.wav"]
    config = pool(["a.wav"], "random")
    selector.started(("p", 1), config, "a.wav")
    assert selector.candidates(("p", 1), config) == ["a.wav"]


@pytest.fixture
def runtime(audio, tmp_path, monkeypatch):
    paths = [tmp_path / name for name in ("a.wav", "b.mp3", "c.wav")]
    for path in paths:
        path.write_bytes(b"fake audio for fake mixer")
    data = document(pool(list(map(str, paths))))
    monkeypatch.setattr(logic, "settings", data)
    monkeypatch.setattr(logic, "settings_file", tmp_path / "settings.json")
    selector = pools.PoolSelector(chooser=lambda candidates: candidates[0])
    monkeypatch.setattr(logic, "_pool_selector", selector)
    return SimpleNamespace(paths=paths, audio=audio, data=data, selector=selector)


def start(runtime, index=1):
    channel = runtime.audio.channel(index)
    runtime.audio.mixer.available.append(channel)
    return channel, logic.play_button(index, "ignored.wav", 125)


def test_pool_uses_real_engine_sequence_cache_and_natural_end(runtime):
    channel, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[0])
    runtime.audio.events.append(SimpleNamespace(type=channel.endevent))
    assert logic.check_sound_end() == [{"index": 1, "playing": False}]
    assert len(runtime.audio.mixer.loaded_paths) == 1  # no autoplay
    _, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[1])
    logic.stop_jingle(1, 25)
    _, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[2])
    logic.stop_jingle(1, 25)
    _, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[0])
    assert len(runtime.audio.mixer.loaded_paths) == 3


def test_missing_and_corrupt_auto_entries_skipped_but_manual_never_falls_back(runtime, monkeypatch):
    runtime.paths[0].unlink()
    original = runtime.audio.mixer.Sound

    def load(path):
        if path.endswith("b.mp3"):
            raise ValueError("corrupt")
        return original(path)

    monkeypatch.setattr(runtime.audio.mixer, "Sound", load)
    _, result = start(runtime)
    assert result["success"] and result["selected_audio"] == str(runtime.paths[2])
    assert len(result["warnings"]) == 2
    logic.stop_jingle(1, 0)
    config = runtime.data["presets"][0]["audio_pools"]["1"]
    config["audio_pool_mode"] = "manual"
    channel, result = start(runtime)
    assert not result["success"] and "a.wav" in result["error"]
    assert not channel.busy and logic.playing_channels == {}
    assert config["selected_audio"] == str(runtime.paths[0])


def test_pool_edits_and_manual_selection_do_not_change_running_channel(runtime):
    channel, result = start(runtime)
    config = runtime.data["presets"][0]["audio_pools"]["1"]
    config["audio_pool_mode"] = "manual"
    config["selected_audio"] = str(runtime.paths[2])
    assert channel.sound.path == os.path.normcase(str(runtime.paths[0]))
    result = logic.play_button(1, "ignored.wav", 87)
    assert result["indicator_update"]["playing"] is False and channel.fadeouts == [87]
    _, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[2])


def test_all_missing_failure_retains_sequence_state_and_presets(runtime):
    before = deepcopy(runtime.data)
    for path in runtime.paths:
        path.unlink()
    _, result = start(runtime)
    assert not result["success"] and logic.playing_channels == {}
    assert runtime.data == before
    assert next(iter(runtime.selector.states.values()))["next"] == 0


def test_relative_pool_paths_use_settings_directory_not_cwd(runtime, tmp_path, monkeypatch):
    config = runtime.data["presets"][0]["audio_pools"]["1"]
    config.update(audio_pool=[p.name for p in runtime.paths], selected_audio=runtime.paths[0].name)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    channel, result = start(runtime)
    assert result["success"] and channel.sound.path == os.path.normcase(str(runtime.paths[0]))


def test_persistence_restart_and_export_guard(tmp_path):
    path = tmp_path / "settings.json"
    data = document(slot=50)
    before = deepcopy(data)
    token = storage.load_preset_settings(path, initialize=True, initial_settings=data)
    storage.save_preset_settings(path, data, expected=token)
    assert storage.load_preset_settings(path).data == data == before
    with pytest.raises(packages.PackageValidationError) as error:
        packages.export_package_directory(data, tmp_path / "blocked")
    assert error.value.code == "pool_export"
    assert not (tmp_path / "blocked").exists()
    assert presets.extract_active_board(data)["buttons"]["paths"][49] == "a.wav"


def test_single_file_pool_export_preserves_existing_package_format(tmp_path):
    audio = tmp_path / "sound.wav"
    audio.write_bytes(b"export bytes")
    data = document(pool([str(audio)]))
    data["presets"][0]["buttons"]["paths"] = [str(audio)] * 50
    packages.export_package_directory(data, tmp_path / "package")
    package = packages.validate_package_directory(tmp_path / "package")
    assert len(package.assets) == 1
    assert "audio_pools" not in package.settings


def test_failed_channel_start_stops_channel_and_does_not_advance(runtime, monkeypatch):
    channel = runtime.audio.channel(1)

    def broken_play(sound):
        channel.busy = True
        raise RuntimeError("channel failure")

    monkeypatch.setattr(channel, "play", broken_play)
    runtime.audio.mixer.available.append(channel)
    result = logic.play_button(1, "", 100)
    assert not result["success"]
    assert channel.stop_calls == 1 and not channel.busy and channel.endevent == 0
    assert not logic.playing_channels and not logic._playbacks_by_event and not logic._events_by_button
    assert next(iter(runtime.selector.states.values()))["next"] == 0


def test_random_missing_entries_allow_last_only_when_it_is_the_only_usable_file(runtime):
    config = runtime.data["presets"][0]["audio_pools"]["1"]
    config["audio_pool_mode"] = "random"
    _, first = start(runtime)
    logic.stop_jingle(1, 0)
    _, second = start(runtime)
    assert first["selected_audio"] != second["selected_audio"]
    logic.stop_jingle(1, 0)
    for path in runtime.paths:
        if str(path) != second["selected_audio"]:
            path.unlink()
    _, last = start(runtime)
    assert last["selected_audio"] == second["selected_audio"]
    assert len(last["warnings"]) == 2


def test_two_pool_buttons_keep_independent_channels_and_sequence(runtime):
    active = runtime.data["presets"][0]
    active["audio_pools"]["2"] = deepcopy(active["audio_pools"]["1"])
    first, a = start(runtime, 1)
    second, b = start(runtime, 2)
    assert a["selected_audio"] == b["selected_audio"]
    assert first is not second and first.sound is second.sound
    logic.stop_jingle(1, 250)
    assert first.fadeouts == [250] and second.fadeouts == []
    assert logic.playing_channels[2] is second
    _, next_a = start(runtime, 1)
    assert next_a["selected_audio"] == str(runtime.paths[1])


def test_pool_fadeout_stale_event_does_not_stop_the_next_file(runtime):
    old, _ = start(runtime)
    old_event = old.endevent
    logic.stop_jingle(1, 600)
    new, result = start(runtime)
    assert result["selected_audio"] == str(runtime.paths[1])
    runtime.audio.events.append(SimpleNamespace(type=old_event))
    assert logic.check_sound_end() == []
    assert logic.playing_channels[1] is new


def test_generated_wav_pool_plays_in_real_pygame_subprocess(tmp_path):
    import json
    import subprocess
    import sys
    import wave

    files = []
    for name in ("first.wav", "second.wav"):
        path = tmp_path / name
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(44100)
            stream.writeframes(b"\0\0" * 4410)
        files.append(str(path))
    data = document(pool(files))
    script = """
import json, sys
import jingleplayer_logic as logic
document = json.loads(sys.stdin.read())
logic._apply_document(document)
try:
    expected = document['presets'][0]['audio_pools']['1']['audio_pool']
    for path in expected:
        result = logic.play_button(1, '', 0)
        assert result.get('success'), result
        assert result['selected_audio'] == path
        logic.stop_jingle(1, 0)
    assert len(logic.sounds) == 2
finally:
    logic.stop_all_playback()
    logic.pygame.quit()
"""
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script],
                            input=json.dumps(data), text=True, capture_output=True, timeout=30,
                            env={**os.environ, "SDL_AUDIODRIVER": "dummy", "SDL_VIDEODRIVER": "dummy"})
    assert result.returncode == 0, result.stdout + result.stderr
