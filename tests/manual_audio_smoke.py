"""Interactive Windows smoke test for the real Jingleplayer audio engine.

This file is intentionally not named ``test_*.py`` and is never collected by
pytest. Run it from the repository directory with:

    python tests/manual_audio_smoke.py
"""

from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jingleplayer_logic as audio  # noqa: E402


class Results:
    def __init__(self):
        self.automated_passed = 0
        self.automated_failed = 0
        self.listening_passed = 0
        self.listening_failed = 0
        self.tests: dict[str, str] = {}

    def check(self, condition: bool, message: str) -> bool:
        marker = "PASS" if condition else "FAIL"
        print(f"  [{marker}] {message}")
        if condition:
            self.automated_passed += 1
        else:
            self.automated_failed += 1
        return condition

    def listen(self, prompt: str) -> bool:
        answer = input(f"  {prompt} [j/n] ").strip().lower()
        passed = answer in {"j", "ja", "y", "yes"}
        if passed:
            self.listening_passed += 1
        else:
            self.listening_failed += 1
        return passed

    def set_test(self, name: str, automated: bool, listening: bool | None = None):
        self.tests[name] = "PASS" if automated and listening is not False else "FAIL"


def section(number: int, title: str):
    print(f"\nTEST {number} - {title}")
    print("-" * (9 + len(title)))
    input("Enter druecken, um den Test zu starten ... ")


def channel_label(channel) -> str:
    return f"{type(channel).__name__}@0x{id(channel):x}"


def cache_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def start(button: int, path: Path | str, fadeout_ms: int = 200):
    key = cache_key(path)
    print(
        f"  START button={button}, file={Path(path).name}, "
        f"cache={'HIT' if key in audio.sounds else 'MISS'}"
    )
    result = audio.play_jingle(button, str(path), fadeout_ms)
    channel = audio.playing_channels.get(button)
    if channel is not None:
        print(f"  CHANNEL button={button}: {channel_label(channel)}")
    elif result.get("error"):
        print(f"  ERROR {result['error']}")
    return result, channel


def stop(button: int, fadeout_ms: int = 200):
    channel = audio.playing_channels.get(button)
    print(
        f"  FADEOUT button={button}, duration={fadeout_ms} ms, "
        f"channel={channel_label(channel) if channel else 'none'}"
    )
    result = audio.stop_jingle(button, fadeout_ms)
    print(f"  CLEANUP button={button}, mapped={button in audio.playing_channels}")
    return result


def pump_events() -> list[int]:
    ended = []
    for update in audio.check_sound_end():
        index = update["index"]
        ended.append(index)
        print(f"  END button={index}; CLEANUP mapped={index in audio.playing_channels}")
    return ended


def wait_for_end(button: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if button in pump_events():
            return button not in audio.playing_channels
        time.sleep(0.02)
    pump_events()
    return button not in audio.playing_channels


def create_tone(path: Path, frequency: float, duration: float):
    sample_rate = audio.MIXER_FREQUENCY
    amplitude = 0.28 * 32767
    frame_count = int(sample_rate * duration)
    ramp_frames = max(1, int(sample_rate * 0.01))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(audio.MIXER_OUTPUT_CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for frame in range(frame_count):
            envelope = min(1.0, frame / ramp_frames, (frame_count - frame - 1) / ramp_frames)
            sample = int(amplitude * max(0.0, envelope) * math.sin(2 * math.pi * frequency * frame / sample_rate))
            packed = struct.pack("<h", sample)
            frames.extend(packed * audio.MIXER_OUTPUT_CHANNELS)
        wav_file.writeframes(frames)


def ensure_real_mixer(results: Results) -> bool:
    pygame = audio.pygame
    ok = results.check(pygame is not None, "pygame ist importiert")
    if not ok:
        return False
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(
                frequency=audio.MIXER_FREQUENCY,
                size=audio.MIXER_SIZE,
                channels=audio.MIXER_OUTPUT_CHANNELS,
                buffer=audio.MIXER_BUFFER,
            )
        pygame.mixer.set_num_channels(audio.MIXER_CHANNEL_COUNT)
        audio.pygame_available = True
        mixer_info = pygame.mixer.get_init()
        print(f"  Frequency: {mixer_info[0]} Hz")
        print(f"  Sample format: {mixer_info[1]} bit")
        print(f"  Output channels: {mixer_info[2]}")
        print(f"  Configured buffer: {audio.MIXER_BUFFER} samples")
        print(f"  Mixer channels: {pygame.mixer.get_num_channels()}")
        checks = [
            results.check(mixer_info[0] == audio.MIXER_FREQUENCY, "Frequency entspricht der Anwendungskonfiguration"),
            results.check(mixer_info[1] == audio.MIXER_SIZE, "Sample-Format entspricht der Anwendungskonfiguration"),
            results.check(mixer_info[2] == audio.MIXER_OUTPUT_CHANNELS, "Stereo-Ausgabe ist aktiv"),
            results.check(pygame.mixer.get_num_channels() == audio.MIXER_CHANNEL_COUNT, "50 Mixer-Channels sind vorhanden"),
        ]
        return all(checks)
    except Exception as exc:
        print(f"  [FAIL] Mixer konnte nicht initialisiert werden: {exc}")
        results.automated_failed += 1
        return False


def single_wav(results: Results, tone_a: Path):
    result, channel = start(1, tone_a)
    checks = [
        results.check(result.get("success") is True, "WAV-Start war erfolgreich"),
        results.check(channel is not None, "Channel wurde zugewiesen"),
        results.check(audio.playing_channels.get(1) is channel, "Playback-State wurde gesetzt"),
    ]
    listening = results.listen("War der Ton sauber hoerbar?")
    ended = wait_for_end(1, 3.0)
    checks.append(results.check(ended, "Natuerliches Ende wurde erkannt und bereinigt"))
    results.set_test("Single WAV", all(checks), listening)


def immediate_restart(results: Results, tone_a: Path):
    checks = []
    for attempt in range(1, 6):
        result, channel = start(10, tone_a, 0)
        checks.append(results.check(result.get("success") is True and channel is not None, f"Start {attempt}/5 erfolgreich"))
        time.sleep(0.10)
        stopped = stop(10, 0)
        checks.append(results.check(stopped.get("indicator_update", {}).get("playing") is False, f"Stop {attempt}/5 bereinigt State"))
        time.sleep(0.05)
        pump_events()
    listening = results.listen("Waren die Starts direkt und ohne auffaellige Aussetzer?")
    results.set_test("Restart", all(checks), listening)


def toggle_fadeout(results: Results, tone_a: Path):
    result, channel = start(2, tone_a, 500)
    time.sleep(0.35)
    stopped = stop(2, 500)
    checks = [
        results.check(result.get("success") is True and channel is not None, "Ton wurde gestartet"),
        results.check(stopped.get("indicator_update") == {"index": 2, "playing": False}, "Toggle meldet den Button als inaktiv"),
        results.check(2 not in audio.playing_channels, "Button-Channel wurde bereinigt"),
    ]
    listening = results.listen("War der Fadeout sauber und ohne Knacken?")
    time.sleep(0.6)
    pump_events()
    results.set_test("Fadeout", all(checks), listening)


def parallel_playback(results: Results, tone_a: Path, tone_b: Path):
    t0 = time.monotonic()

    def timeline(message: str):
        print(f"  [+{time.monotonic() - t0:.3f}s] {message}")

    timeline("START A")
    first, channel_a = start(3, tone_a)
    timeline(f"A busy={channel_a.get_busy() if channel_a is not None else None}")
    timeline("START B")
    second, channel_b = start(4, tone_b)
    event_b = audio._events_by_button.get(4)
    timeline(f"B busy={channel_b.get_busy() if channel_b is not None else None}")
    checks = [
        results.check(first.get("success") is True and second.get("success") is True, "Beide WAV-Dateien wurden gestartet"),
        results.check(channel_a is not None and channel_b is not None and channel_a is not channel_b, "Unterschiedliche Channels werden verwendet"),
        results.check({3, 4}.issubset(audio.playing_channels), "Beide Playback-Eintraege sind gesetzt"),
        results.check(event_b is not None, "Endevent von Button B ist registriert"),
    ]

    ended_a = False
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not ended_a:
        for update in audio.check_sound_end():
            index = update["index"]
            timeline(f"EVENT {'A' if index == 3 else 'B' if index == 4 else index}")
            timeline(f"A busy={channel_a.get_busy() if channel_a is not None else None}")
            timeline(f"B busy={channel_b.get_busy() if channel_b is not None else None}")
            timeline(f"CLEANUP {'A' if index == 3 else 'B' if index == 4 else index}: mapped={index in audio.playing_channels}")
            if index == 3:
                ended_a = True
        if not ended_a:
            time.sleep(0.02)

    timeline("PRUEFUNG: Ende von A beeinflusst B nicht")
    a_ended_without_affecting_b = (
        ended_a
        and 3 not in audio.playing_channels
        and audio.playing_channels.get(4) is channel_b
        and channel_b is not None
        and channel_b.get_busy()
        and audio._events_by_button.get(4) == event_b
        and audio._playbacks_by_event.get(event_b) == (4, channel_b)
    )
    checks.append(results.check(a_ended_without_affecting_b, "Ende von A beeinflusst B nicht"))

    timeline("BEGINN Benutzerabfrage")
    listening = results.listen("Waren beide unterschiedlichen Toene gleichzeitig hoerbar?")
    timeline("ENDE Benutzerabfrage")

    ended_b = False
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline and not ended_b:
        for update in audio.check_sound_end():
            index = update["index"]
            timeline(f"EVENT {'A' if index == 3 else 'B' if index == 4 else index}")
            timeline(f"A busy={channel_a.get_busy() if channel_a is not None else None}")
            timeline(f"B busy={channel_b.get_busy() if channel_b is not None else None}")
            timeline(f"CLEANUP {'A' if index == 3 else 'B' if index == 4 else index}: mapped={index in audio.playing_channels}")
            if index == 4:
                ended_b = True
        if not ended_b:
            time.sleep(0.02)

    b_was_cleaned_up = (
        ended_b
        and 4 not in audio.playing_channels
        and 4 not in audio._events_by_button
        and event_b not in audio._playbacks_by_event
    )
    checks.append(results.check(b_was_cleaned_up, "Ende und Event-Mapping von B wurden separat bereinigt"))
    results.set_test("Parallel playback", all(checks), listening)


def same_sound_multiple_channels(results: Results, tone_b: Path):
    _, channel_a = start(5, tone_b)
    _, channel_b = start(6, tone_b)
    key = cache_key(tone_b)
    sound = audio.sounds.get(key)
    channels_have_cached_sound = (
        sound is not None
        and channel_a is not None
        and channel_b is not None
        and channel_a.get_sound() is sound
        and channel_b.get_sound() is sound
    )
    checks = [
        results.check(channels_have_cached_sound, "Beide Channels verwenden dasselbe gecachte Sound-Objekt"),
        results.check(channel_a is not None and channel_b is not None and channel_a is not channel_b, "Die Channels sind unabhaengig"),
    ]
    time.sleep(0.3)
    stop(5, 150)
    checks.append(results.check(channel_b is not None and audio.playing_channels.get(6) is channel_b and channel_b.get_busy(), "Stop von Button A beeinflusst Button B nicht"))
    checks.append(results.check(wait_for_end(6, 3.0), "Button B endet und wird separat bereinigt"))
    results.set_test("Same sound / multiple channels", all(checks))


def global_volume(results: Results, long_tone: Path):
    result, channel = start(7, long_tone)
    checks = [results.check(result.get("success") is True and channel is not None, "Langer Testton wurde gestartet")]
    for value in (100, 75, 50, 25, 0):
        response = audio.set_volume_logic(value)
        print(f"  VOLUME global={value}%")
        checks.append(results.check(response.get("volume_set") == value and audio.set_volume == value, f"Globale Lautstaerke {value}% angewendet"))
        time.sleep(0.3)
    listening = results.listen("Wurde der Ton stufenweise leiser und bei 0 % stumm?")
    stop(7, 100)
    audio.set_volume_logic(100)
    time.sleep(0.15)
    pump_events()
    results.set_test("Global volume", all(checks), listening)


def button_db(results: Results, long_tone: Path):
    audio.set_volume_logic(50)
    result, channel = start(8, long_tone)
    checks = [results.check(result.get("success") is True and channel is not None, "Testton wurde bei 50 % global gestartet")]
    for db in (-10, 0, 10):
        audio.set_button_volume(8, db)
        effective = audio.calculate_effective_volume(audio.set_volume, db)
        print(f"  BUTTON button=8, dB={db:+d}, effective_volume={effective:.4f}")
        checks.append(results.check(0.0 <= effective <= 1.0, f"Effektive Lautstaerke fuer {db:+d} dB ist gueltig"))
        time.sleep(0.4)
    print("  Hinweis: Pygame begrenzt Channel-Lautstaerke auf maximal 1.0.")
    listening = results.listen("Waren die drei Lautstaerkestufen plausibel unterscheidbar?")
    stop(8, 100)
    audio.set_button_volume(8, 0)
    audio.set_volume_logic(100)
    time.sleep(0.15)
    pump_events()
    results.set_test("Button dB", all(checks), listening)


def optional_mp3(results: Results):
    path_text = input("  Optionaler lokaler MP3-Pfad (leer = ueberspringen): ").strip().strip('"')
    if not path_text:
        results.tests["MP3"] = "SKIPPED"
        print("  [SKIPPED] MP3-Test")
        return
    path = Path(path_text).expanduser().resolve()
    exists = results.check(path.is_file() and path.suffix.lower() == ".mp3", "MP3-Pfad ist gueltig")
    if not exists:
        results.set_test("MP3", False)
        return
    first, channel = start(9, path, 250)
    checks = [results.check(first.get("success") is True and channel is not None, "MP3 wurde geladen und gestartet")]
    time.sleep(0.8)
    stop(9, 250)
    checks.append(results.check(9 not in audio.playing_channels, "MP3 wurde gestoppt und bereinigt"))
    time.sleep(0.35)
    pump_events()
    second, channel = start(9, path, 250)
    checks.append(results.check(second.get("success") is True and channel is not None, "MP3 wurde erneut gestartet"))
    sound = audio.sounds.get(cache_key(path))
    timeout = (sound.get_length() if sound is not None else 30.0) + 3.0
    print(f"  Warte auf natuerliches MP3-Ende (Timeout {timeout:.1f} s) ...")
    checks.append(results.check(wait_for_end(9, timeout), "Natuerliches MP3-Ende wurde erkannt"))
    listening = results.listen("War die MP3 sauber hoerbar?")
    results.set_test("MP3", all(checks), listening)


def stress_test(results: Results, tone_a: Path, tone_b: Path):
    checks = []
    sequence = [
        ("start", 11, tone_a), ("start", 12, tone_b), ("stop", 11, None),
        ("start", 11, tone_a), ("stop", 12, None), ("start", 12, tone_b),
        ("stop", 11, None), ("stop", 12, None),
    ]
    try:
        for action, button, path in sequence:
            if action == "start":
                result, _ = start(button, path, 80)
                checks.append(results.check(result.get("success") is True, f"Start Button {button}"))
            else:
                stop(button, 80)
                checks.append(results.check(button not in audio.playing_channels, f"Stop Button {button}"))
            time.sleep(0.12)
            pump_events()
        time.sleep(0.25)
        pump_events()
        checks.extend(
            [
                results.check(not audio.playing_channels, "Keine stale Playback-Eintraege"),
                results.check(not audio._events_by_button, "Keine stale Button/Event-Zuordnungen"),
                results.check(not audio._playbacks_by_event, "Keine stale Event/Playback-Zuordnungen"),
            ]
        )
    except Exception as exc:
        print(f"  [FAIL] Stress-Test Exception: {exc}")
        results.automated_failed += 1
        checks.append(False)
    results.set_test("Stress test", all(checks))


def cleanup():
    for button in list(audio.playing_channels):
        audio.stop_jingle(button, 0)
    time.sleep(0.05)
    pump_events()


def print_summary(results: Results):
    print("\nAudio Smoke Test")
    print("================")
    labels = [
        "Mixer", "Single WAV", "Restart", "Fadeout", "Parallel playback",
        "Same sound / multiple channels", "Global volume", "Button dB", "MP3", "Stress test",
    ]
    for label in labels:
        print(f"{label}: {results.tests.get(label, 'FAIL')}")
    print(f"\nAutomated checks: {results.automated_passed} passed / {results.automated_failed} failed")
    print(f"User listening checks: {results.listening_passed} passed / {results.listening_failed} failed")


def main() -> int:
    if sys.platform != "win32":
        print("WARNUNG: Dieser manuelle Smoke-Test ist fuer Windows vorgesehen.")
    print("Jingleplayer - realer Windows-Audio-Smoke-Test")
    print("Die folgenden Tests erzeugen hoerbare Toene. Lautstaerke vorher moderat einstellen.")
    results = Results()
    try:
        section(1, "Mixer")
        mixer_ok = ensure_real_mixer(results)
        results.set_test("Mixer", mixer_ok)
        if not mixer_ok:
            print("Mixer-Test fehlgeschlagen; Audio-Folgetests werden nicht ausgefuehrt.")
            print_summary(results)
            return 1

        audio.button_volumes = [0] * audio.DEFAULT_BUTTON_COUNT
        audio.set_volume_logic(100)
        with tempfile.TemporaryDirectory(prefix="jingleplayer-smoke-") as temp_dir:
            directory = Path(temp_dir)
            tone_a = directory / "tone_a_440hz.wav"
            tone_b = directory / "tone_b_660hz.wav"
            parallel_tone_a = directory / "parallel_a_440hz_1s.wav"
            parallel_tone_b = directory / "parallel_b_660hz_5s.wav"
            long_tone = directory / "tone_long_440hz.wav"
            create_tone(tone_a, 440.0, 1.2)
            create_tone(tone_b, 660.0, 2.0)
            create_tone(parallel_tone_a, 440.0, 1.0)
            create_tone(parallel_tone_b, 660.0, 5.0)
            create_tone(long_tone, 440.0, 3.5)
            print(f"Temporare Testsignale: {directory}")

            section(2, "Einzelner WAV-Jingle")
            single_wav(results, tone_a)
            section(3, "Sofortiger erneuter Start")
            immediate_restart(results, tone_a)
            section(4, "Toggle/Stop")
            toggle_fadeout(results, tone_a)
            section(5, "Parallelwiedergabe")
            parallel_playback(results, parallel_tone_a, parallel_tone_b)
            section(6, "Gleiche Datei auf zwei Buttons")
            same_sound_multiple_channels(results, tone_b)
            section(7, "Globale Lautstaerke")
            global_volume(results, long_tone)
            section(8, "Button-dB")
            button_db(results, long_tone)
            section(9, "Optionale MP3")
            optional_mp3(results)
            section(10, "Schnelltest")
            stress_test(results, tone_a, tone_b)
    except (KeyboardInterrupt, EOFError):
        print("\nTest durch Benutzer abgebrochen.")
        return 130
    finally:
        cleanup()

    print_summary(results)
    return 1 if results.automated_failed or results.listening_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
