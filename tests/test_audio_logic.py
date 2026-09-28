from types import SimpleNamespace

import pytest

import jingleplayer_logic as logic


def start(audio, index=1, path="test.wav"):
    channel = audio.channel(index)
    audio.mixer.available.append(channel)
    result = logic.play_jingle(index, path, 250)
    return channel, result


@pytest.mark.parametrize("path", ["test.wav", "test.mp3", "TEST.WAV"])
def test_supported_audio_starts(path, audio):
    channel, result = start(audio, path=path)
    assert result["success"] is True
    assert result["indicator_update"] == {"index": 1, "playing": True}
    assert channel.sound.path.lower().endswith(path.lower())
    assert logic.playing_channels[1] is channel


@pytest.mark.parametrize("path", ["", None])
def test_empty_path_is_rejected(path, audio):
    result = logic.play_jingle(1, path, 100)
    assert result["success"] is False
    assert "Kein Jingle" in result["error"]


def test_unsupported_extension_is_rejected(audio):
    result = logic.play_jingle(1, "test.ogg", 100)
    assert result["success"] is False
    assert "nicht unterstützt" in result["error"]


def test_pygame_unavailable_is_reported(audio, monkeypatch):
    monkeypatch.setattr(logic, "pygame_available", False)
    result = logic.play_jingle(1, "test.wav", 100)
    assert result["success"] is False
    assert "nicht verfügbar" in result["error"]


def test_sound_load_error_is_reported_without_state(audio):
    audio.mixer.load_error = RuntimeError("broken")
    result = logic.play_jingle(1, "test.wav", 100)
    assert result["success"] is False
    assert "broken" in result["error"]
    assert logic.playing_channels == {}


def test_no_free_channel_is_reported_without_playing_indicator(audio):
    result = logic.play_jingle(1, "test.wav", 100)
    assert result == {"error": "Kein freier Audio-Channel verfügbar.", "success": False}
    assert logic.playing_channels == {}


def test_mixer_channel_count_matches_maximum_button_count():
    assert logic.MIXER_CHANNEL_COUNT == logic.DEFAULT_BUTTON_COUNT == 50


def test_mixer_configuration_uses_stable_low_latency_defaults():
    assert (logic.MIXER_FREQUENCY, logic.MIXER_SIZE) == (44100, -16)
    assert (logic.MIXER_OUTPUT_CHANNELS, logic.MIXER_BUFFER) == (2, 512)


def test_cache_reuses_same_path(audio):
    first, _ = start(audio, index=1, path="same.wav")
    logic.stop_jingle(1, 0)
    second, _ = start(audio, index=2, path="same.wav")
    assert len(audio.mixer.loaded_paths) == 1
    assert first.sound is second.sound


def test_different_paths_are_cached_separately(audio):
    first, _ = start(audio, index=1, path="first.wav")
    second, _ = start(audio, index=2, path="second.wav")
    assert len(audio.mixer.loaded_paths) == 2
    assert first.sound is not second.sound


def test_changed_button_path_uses_new_sound(audio):
    first, _ = start(audio, path="old.wav")
    logic.stop_jingle(1, 0)
    second, _ = start(audio, path="new.wav")
    assert first.sound.path.endswith("old.wav")
    assert second.sound.path.endswith("new.wav")


def test_toggle_starts_stops_and_starts_again(audio):
    first, started = start(audio)
    stopped = logic.play_jingle(1, "test.wav", 321)
    assert started["indicator_update"]["playing"] is True
    assert stopped["indicator_update"]["playing"] is False
    assert first.fadeouts == [321]
    assert 1 not in logic.playing_channels
    second, restarted = start(audio)
    assert restarted["indicator_update"]["playing"] is True
    assert logic.playing_channels[1] is second


def test_legacy_playback_state_tracks_multiple_buttons(audio):
    start(audio, index=1)
    start(audio, index=2)
    assert logic.jingle_playing is True
    assert logic.current_jingle == 2
    logic.stop_jingle(2, 0)
    assert logic.jingle_playing is True
    assert logic.current_jingle == 1
    logic.stop_jingle(1, 0)
    assert logic.jingle_playing is False
    assert logic.current_jingle is None


def test_stopping_inactive_button_is_a_no_op(audio):
    assert logic.stop_jingle(9, 100) == {}


@pytest.mark.parametrize("duration, expected", [(750, 750), (0, 0), (-10, 0)])
def test_stop_fades_only_the_buttons_channel(duration, expected, audio):
    first, _ = start(audio, index=1, path="same.wav")
    second, _ = start(audio, index=2, path="same.wav")
    result = logic.stop_jingle(1, duration)
    assert first.fadeouts == [expected]
    assert second.fadeouts == []
    assert 1 not in logic.playing_channels
    assert logic.playing_channels[2] is second
    assert result["indicator_update"]["playing"] is False
    assert not hasattr(first.sound, "fadeout")


def test_same_sound_can_play_on_independent_channels(audio):
    first, _ = start(audio, index=1, path="same.wav")
    second, _ = start(audio, index=2, path="same.wav")
    assert first is not second
    assert first.sound is second.sound


def test_natural_end_cleans_channel_and_returns_indicator(audio):
    channel, _ = start(audio, index=3)
    audio.events.append(SimpleNamespace(type=channel.endevent))
    assert logic.check_sound_end() == [{"index": 3, "playing": False}]
    assert 3 not in logic.playing_channels
    assert channel.endevent not in logic._playbacks_by_event
    assert logic.jingle_playing is False


def test_foreign_pygame_events_are_ignored(audio):
    channel, _ = start(audio)
    audio.events.extend([SimpleNamespace(type=42), SimpleNamespace(type=logic.pygame.USEREVENT + 999)])
    assert logic.check_sound_end() == []
    assert logic.playing_channels[1] is channel


def test_end_event_only_affects_its_own_button(audio):
    first, _ = start(audio, index=1)
    second, _ = start(audio, index=2)
    audio.events.append(SimpleNamespace(type=first.endevent))
    assert logic.check_sound_end() == [{"index": 1, "playing": False}]
    assert 1 not in logic.playing_channels
    assert logic.playing_channels[2] is second


def test_stale_event_after_stop_and_restart_is_ignored(audio):
    old, _ = start(audio)
    old_event = old.endevent
    logic.stop_jingle(1, 0)
    new, _ = start(audio)
    assert new.endevent != old_event
    audio.events.append(SimpleNamespace(type=old_event))
    assert logic.check_sound_end() == []
    assert logic.playing_channels[1] is new
