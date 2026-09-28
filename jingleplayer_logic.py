try:
    import pygame
    pygame_available = True
except Exception as _e:
    pygame = None
    pygame_available = False
    print(f"pygame konnte nicht importiert werden: {_e}. Audio-Funktionen sind deaktiviert.")

import os
import json
from pathlib import Path

# Konstanten definieren für Lesbarkeit und Wartung
DEFAULT_BUTTON_ROW_COUNT = 5 # Anzahl der Reihen
DEFAULT_BUTTONS_PER_ROW_COUNT = 10 # Max Buttons pro Reihe
DEFAULT_BUTTON_COUNT = DEFAULT_BUTTON_ROW_COUNT * DEFAULT_BUTTONS_PER_ROW_COUNT # Max Buttons gesamt
FADEOUT_CHECK_INTERVAL_MS = 100
FONT_SIZE_BUTTONS = 12
FONT_SIZE_TITLE = 24
DEFAULT_FADEOUT_DURATION = 1000 # Default fadeout duration in milliseconds
DEFAULT_BUTTON_HEIGHT = 2 # Definiere eine Standardhöhe der Schaltflächen
DEFAULT_WINDOW_WIDTH = 800 # Definiere eine Standardbreite
DEFAULT_WINDOW_HEIGHT = 600 # Definiere eine Standardhöhe
DEFAULT_VOLUME = 100 # Default volume
MIXER_FREQUENCY = 44100
MIXER_SIZE = -16
MIXER_OUTPUT_CHANNELS = 2
MIXER_BUFFER = 512
MIXER_CHANNEL_COUNT = DEFAULT_BUTTON_COUNT

# Variable, um den aktuellen Status des Players zu speichern
current_jingle = None
jingle_playing = False
sounds = {} # Cache: normalisierter Dateipfad -> pygame Sound
playing_channels = {}  # Map button index -> pygame Channel (für Laufzeit-Volume-Updates)
_playbacks_by_event = {}  # Map endevent id -> (button index, exact Channel)
_events_by_button = {}  # Map button index -> endevent id
_next_end_event = None
button_texts = []
button_colors = []
jingle_paths = []
button_volumes = []  # pro-button volume in dB (-10..+10)
buttons_per_row = []
fadeout_duration = DEFAULT_FADEOUT_DURATION
button_height = DEFAULT_BUTTON_HEIGHT
set_volume = DEFAULT_VOLUME
settings = {}

# Pfad für die Einstellungen im Benutzerverzeichnis
data_dir = Path.home() / ".jingleplayer"
settings_file = data_dir / "jingleplayer_settings.json"

# Initialisierung von pygame (falls verfügbar)
if pygame_available:
    try:
        pygame.mixer.pre_init(
            frequency=MIXER_FREQUENCY,
            size=MIXER_SIZE,
            channels=MIXER_OUTPUT_CHANNELS,
            buffer=MIXER_BUFFER,
        )
        pygame.init()
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(
                frequency=MIXER_FREQUENCY,
                size=MIXER_SIZE,
                channels=MIXER_OUTPUT_CHANNELS,
                buffer=MIXER_BUFFER,
            )
        pygame.mixer.set_num_channels(MIXER_CHANNEL_COUNT)
    except Exception as _e:
        print(f"Fehler bei pygame-Initialisierung: {_e}. Audio-Funktionen sind deaktiviert.")
        pygame_available = False

# ---  Logik-Funktionen (GUI-unabhängig) ---

# Überprüfen und Standardwerte setzen
def check_and_set_defaults(loaded_settings, default_settings):
    for key, value in default_settings.items():
        if key not in loaded_settings:
            loaded_settings[key] = value
    return loaded_settings


def _default_button_texts():
    return [f"Jingle {index}" for index in range(1, DEFAULT_BUTTON_COUNT + 1)]


def _normalize_button_slots(values, defaults):
    normalized = list(values) if isinstance(values, list) else []
    normalized = normalized[:DEFAULT_BUTTON_COUNT]
    if len(normalized) < DEFAULT_BUTTON_COUNT:
        normalized.extend(defaults[len(normalized):DEFAULT_BUTTON_COUNT])
    return normalized


def _normalize_buttons_per_row(per_row):
    if not isinstance(per_row, list) or len(per_row) != DEFAULT_BUTTON_ROW_COUNT:
        return [DEFAULT_BUTTONS_PER_ROW_COUNT] * DEFAULT_BUTTON_ROW_COUNT
    try:
        normalized = [max(0, min(DEFAULT_BUTTONS_PER_ROW_COUNT, int(value))) for value in per_row]
    except (TypeError, ValueError):
        return [DEFAULT_BUTTONS_PER_ROW_COUNT] * DEFAULT_BUTTON_ROW_COUNT
    if sum(normalized) == 0:
        return [DEFAULT_BUTTONS_PER_ROW_COUNT] * DEFAULT_BUTTON_ROW_COUNT
    return normalized

# Einstellungen laden
def load_settings():
    default_settings = {
        "buttons": {
            "texts": _default_button_texts(),
            "colors": ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT,
            "paths": [""] * DEFAULT_BUTTON_COUNT,
            "volumes": [0] * DEFAULT_BUTTON_COUNT,
            "per_row": [DEFAULT_BUTTONS_PER_ROW_COUNT] * DEFAULT_BUTTON_ROW_COUNT  # Default buttons per row for 5 rows
        },
        "fadeout_duration": DEFAULT_FADEOUT_DURATION,
        "button_height": DEFAULT_BUTTON_HEIGHT,
        "window_size": [DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT],
        "volume": DEFAULT_VOLUME,
        "last_folder": str(Path.home())
    }
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                loaded_settings = json.load(f)
            loaded_settings = check_and_set_defaults(loaded_settings, default_settings)
            # remove leftover background_image key if present (feature removed)
            if 'background_image' in loaded_settings:
                loaded_settings.pop('background_image', None)
            buttons = loaded_settings["buttons"]
            buttons["per_row"] = _normalize_buttons_per_row(buttons.get("per_row"))
            buttons["texts"] = _normalize_button_slots(buttons.get("texts"), _default_button_texts())
            buttons["colors"] = _normalize_button_slots(
                buttons.get("colors"), ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT
            )
            buttons["paths"] = _normalize_button_slots(buttons.get("paths"), [""] * DEFAULT_BUTTON_COUNT)
            buttons["volumes"] = _normalize_button_slots(buttons.get("volumes"), [0] * DEFAULT_BUTTON_COUNT)
            return loaded_settings
        except FileNotFoundError: # Spezifischere Exception Behandlung
            print(f"Einstellungsdatei {settings_file} nicht gefunden. Standardeinstellungen werden verwendet.")
            return default_settings
        except (IOError, json.JSONDecodeError, ValueError) as e: # Allgemeine Fehlerbehandlung
            print(f"Fehler beim Lesen der Datei {settings_file}: {e}")
            return default_settings
    return default_settings

# Einstellungen speichern
def save_settings(current_settings): # Nimmt die aktuellen Einstellungen als Argument
    try:
        with open(settings_file, "w") as f:
            json.dump(current_settings, f, indent=4)
        print("Einstellungen gespeichert.") # Feedback für erfolgreiches Speichern
    except IOError:
        print(f"Die Datei {settings_file} konnte nicht gespeichert werden. Überprüfen Sie die Berechtigungen.")

def calculate_effective_volume(global_percent, button_db):
    """Convert global percent and a per-button dB offset to pygame's 0..1 range."""
    try:
        global_linear = max(0.0, min(100.0, float(global_percent))) / 100.0
    except (TypeError, ValueError):
        global_linear = 0.0
    try:
        db_multiplier = 10 ** (float(button_db) / 20.0)
    except (TypeError, ValueError):
        db_multiplier = 1.0
    return max(0.0, min(1.0, global_linear * db_multiplier))


def _button_volume(index):
    idx0 = index - 1
    return button_volumes[idx0] if 0 <= idx0 < len(button_volumes) else 0


def _sync_legacy_playback_state():
    global current_jingle, jingle_playing
    active = list(playing_channels)
    jingle_playing = bool(active)
    current_jingle = active[-1] if active else None


def _release_playback(index, channel=None):
    """Remove mappings only when they still describe the indicated playback."""
    mapped_channel = playing_channels.get(index)
    if channel is not None and mapped_channel is not channel:
        return False
    playing_channels.pop(index, None)
    event_type = _events_by_button.pop(index, None)
    if event_type is not None:
        _playbacks_by_event.pop(event_type, None)
    _sync_legacy_playback_state()
    return mapped_channel is not None


def _allocate_end_event(index, channel):
    global _next_end_event
    first = int(pygame.USEREVENT) + 1
    limit = int(getattr(pygame, "NUMEVENTS", first + DEFAULT_BUTTON_COUNT + 1))
    if _next_end_event is None or not first <= _next_end_event < limit:
        _next_end_event = first
    for _ in range(max(0, limit - first)):
        event_type = _next_end_event
        _next_end_event += 1
        if _next_end_event >= limit:
            _next_end_event = first
        if event_type not in _playbacks_by_event:
            _playbacks_by_event[event_type] = (index, channel)
            _events_by_button[index] = event_type
            return event_type
    raise RuntimeError("Keine freie Pygame-Endevent-ID verfügbar.")


def play_jingle(index, jingle_path, current_fadeout_duration): # Nimmt fadeout_duration als Argument
    if not pygame_available:
        error_message = "Audio-Funktion nicht verfügbar: pygame ist nicht installiert."
        print(error_message)
        return {"error": error_message, "success": False}

    if index in playing_channels:
        result = stop_jingle(index, current_fadeout_duration)
        result["success"] = True
        return result
    if not jingle_path:
        error_message = "Kein Jingle zugewiesen. Bitte wählen Sie eine Datei im Einstellungsmenü."
        return {"error": error_message, "success": False}

    file_path = os.path.normcase(os.path.abspath(os.fspath(jingle_path)))
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension not in (".mp3", ".wav"):
        return {"error": f"Das Dateiformat {file_extension} wird nicht unterstützt.", "success": False}

    try:
        sound = sounds.get(file_path)
        if sound is None:
            sound = pygame.mixer.Sound(file_path)
            sounds[file_path] = sound
        channel = pygame.mixer.find_channel()
        if channel is None:
            return {"error": "Kein freier Audio-Channel verfügbar.", "success": False}
        event_type = _allocate_end_event(index, channel)
        try:
            channel.set_endevent(event_type)
            channel.set_volume(calculate_effective_volume(set_volume, _button_volume(index)))
            channel.play(sound)
        except Exception:
            _release_playback(index, channel)
            _playbacks_by_event.pop(event_type, None)
            _events_by_button.pop(index, None)
            raise
        playing_channels[index] = channel
        _sync_legacy_playback_state()
        update_indicator_state(index, True)
        print(f"Spielt Jingle {index}: {os.path.basename(file_path)}")
        return {"indicator_update": {"index": index, "playing": True}, "success": True}
    except Exception as e:
        error_message = f"Die Datei {file_path} konnte nicht geladen oder abgespielt werden: {e}"
        print(error_message)
        return {"error": error_message, "success": False}


def stop_jingle(index, current_fadeout_duration): # Nimmt fadeout_duration als Argument
    if not pygame_available:
        # Kein Fehler, aber nichts zu tun
        return {}

    channel = playing_channels.get(index)
    if channel is not None:
        try:
            duration = max(0, int(current_fadeout_duration))
        except (TypeError, ValueError):
            duration = 0
        channel.fadeout(duration)
        _release_playback(index, channel)
        update_indicator_state(index, False) # Aufruf der Logik-Funktion für Indikator-Status
        print(f"Jingle {index} gestoppt mit Fadeout.")
        return {"indicator_update": {"index": index, "playing": False}} # Rückmeldung für GUI
    return {} # Rückmeldung für GUI (Kein Sound zum stoppen)


def check_sound_end():
    if not pygame_available:
        return []
    ended_indicators = [] # Liste der Indizes, die gestoppt werden müssen
    for event in pygame.event.get():
        playback = _playbacks_by_event.get(event.type)
        if playback is None:
            continue
        index, channel = playback
        if playing_channels.get(index) is not channel:
            _playbacks_by_event.pop(event.type, None)
            continue
        _release_playback(index, channel)
        update_indicator_state(index, False)
        ended_indicators.append({"index": index, "playing": False})
    return ended_indicators # Rückmeldung für GUI (Liste von Indikator-Updates)


def update_indicator_state(index, playing):
    # Diese Funktion verwaltet *nur* den Zustand, keine GUI-Aktualisierung direkt
    print(f"Indikator {index} wird auf 'playing'={playing} gesetzt (Logik)")
    return {"index": index, "playing": playing} # Gibt Daten zurück, die die GUI zur Aktualisierung nutzen kann

def set_volume_logic(volume_percent):
    # Set global volume percent and update running channels appropriately
    global set_volume, playing_channels
    try:
        global_volume = int(volume_percent) / 100.0
    except Exception:
        global_volume = int(set_volume) / 100.0
    if pygame_available:
        try:
            # First, update channels we track with per-button multipliers
            for idx, chan in list(playing_channels.items()):
                try:
                    chan.set_volume(calculate_effective_volume(volume_percent, _button_volume(idx)))
                except Exception:
                    pass
            # For any other channels not tracked, set to global volume
            for i in range(pygame.mixer.get_num_channels()):
                channel = pygame.mixer.Channel(i)
                if channel not in list(playing_channels.values()):
                    try:
                        channel.set_volume(max(0.0, min(1.0, global_volume)))
                    except Exception:
                        pass
        except Exception as _e:
            print(f"Warnung: Lautstärke konnte nicht auf alle Channels gesetzt werden: {_e}")
    set_volume = volume_percent
    print(f"Lautstärke auf {volume_percent}% gesetzt (Logik)")
    return {"volume_set": volume_percent} # Rückmeldung für GUI

def initialize_settings():
    global settings, button_texts, button_colors, jingle_paths, buttons_per_row, fadeout_duration, button_height, set_volume
    settings = load_settings()
    button_texts = settings["buttons"]["texts"]
    button_colors = settings["buttons"]["colors"]
    jingle_paths = settings["buttons"]["paths"]
    # initialize per-button volumes
    global button_volumes
    button_volumes = settings["buttons"].get("volumes", [0] * len(jingle_paths))
    buttons_per_row = settings["buttons"]["per_row"]
    if len(buttons_per_row) < DEFAULT_BUTTON_ROW_COUNT:
        buttons_per_row += [0] * (DEFAULT_BUTTON_ROW_COUNT - len(buttons_per_row))
    fadeout_duration = settings["fadeout_duration"]
    button_height = settings["button_height"]
    set_volume = settings["volume"]
    # Ensure last_folder exists in settings
    if "last_folder" not in settings or not settings.get("last_folder"):
        settings["last_folder"] = str(Path.home())
    # Ensure window_size always exists
    if "window_size" not in settings:
        settings["window_size"] = [DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT]
    print(f"buttons_per_row: {buttons_per_row} (Typ: {type(buttons_per_row)})")

def get_current_settings():
    global settings, button_texts, button_colors, jingle_paths, buttons_per_row, fadeout_duration, button_height, set_volume
    # Fallback für window_size, falls nicht vorhanden
    window_size = settings.get("window_size", [DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT])
    return {
        "buttons": {
            "texts": button_texts[:],
            "colors": button_colors[:],
            "paths": jingle_paths[:],
            "volumes": button_volumes[:],
            "per_row": buttons_per_row[:]
        },
        "fadeout_duration": fadeout_duration,
        "button_height": button_height,
        "window_size": window_size[:],
        "volume": set_volume,
        "last_folder": settings.get("last_folder", str(Path.home()))
    }

def update_settings_data(texts, colors, paths, per_row, f_duration, b_height, w_size, vol):
    global button_texts, button_colors, jingle_paths, buttons_per_row, fadeout_duration, button_height, set_volume, settings
    button_texts = _normalize_button_slots(texts, _default_button_texts())
    button_colors = _normalize_button_slots(colors, ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT)
    jingle_paths = _normalize_button_slots(paths, [""] * DEFAULT_BUTTON_COUNT)
    global button_volumes
    button_volumes = _normalize_button_slots(button_volumes, [0] * DEFAULT_BUTTON_COUNT)
    buttons_per_row = _normalize_buttons_per_row(per_row)
    fadeout_duration = f_duration
    button_height = b_height
    set_volume = vol
    settings["window_size"] = w_size # Window size wird separat im settings dict gespeichert.

def get_button_volumes_data():
    global button_volumes
    return button_volumes

def set_button_volume(index, db_value):
    """Setzt das pro-Button Volume in dB (-10..10) und passt die laufenden Channels an."""
    global button_volumes, playing_channels, set_volume
    try:
        db = int(db_value)
    except Exception:
        return
    if db < -10:
        db = -10
    if db > 10:
        db = 10
    # index is expected to be 1-based (as used throughout GUI), convert to 0-based for lists
    idx0 = index - 1
    # Ensure list is long enough
    if idx0 >= len(button_volumes):
        button_volumes += [0] * (idx0 + 1 - len(button_volumes))
    button_volumes[idx0] = db
    # Apply to currently playing channel for this button (playing_channels is keyed by 1-based index)
    if pygame_available and index in playing_channels and playing_channels[index] is not None:
        try:
            chan = playing_channels[index]
            chan.set_volume(calculate_effective_volume(set_volume, db))
        except Exception as _e:
            print(f"Warnung: Konnte Volume für laufenden Channel nicht setzen: {_e}")

def set_last_folder(folder):
    """Speichert den zuletzt verwendeten Ordner in den Einstellungen."""
    global settings
    if not folder:
        return
    try:
        settings["last_folder"] = str(folder)
    except Exception:
        settings["last_folder"] = str(Path.home())


def get_last_folder():
    """Gibt den zuletzt verwendeten Ordner zurück (Fallback: Home)."""
    global settings
    return settings.get("last_folder", str(Path.home()))


def get_initial_button_data():
    global button_texts, button_colors
    return button_texts, button_colors

def get_buttons_per_row_data():
    global buttons_per_row
    return buttons_per_row

def get_fadeout_duration_data():
    global fadeout_duration
    return fadeout_duration

def get_button_height_data():
    global button_height
    return button_height

def get_volume_data():
    global set_volume
    return set_volume

def get_jingle_paths_data():
    global jingle_paths
    return jingle_paths

def get_button_colors_data():
    global button_colors
    return button_colors

def get_button_texts_data():
    global button_texts
    return button_texts
