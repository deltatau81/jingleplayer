try:
    import pygame
    pygame_available = True
except Exception as _e:
    pygame = None
    pygame_available = False
    print(f"pygame konnte nicht importiert werden: {_e}. Audio-Funktionen sind deaktiviert.")

import os
import json
import tempfile
from uuid import UUID
import jingleplayer_presets as presets
import jingleplayer_preset_storage as preset_storage
from copy import deepcopy
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
CURRENT_SCHEMA_VERSION = 3
PRE_PYSIDE6_BACKUP_NAME = "jingleplayer_settings.pre-pyside6.json"

# Variable, um den aktuellen Status des Players zu speichern
current_jingle = None
jingle_playing = False
sounds = {} # Cache: normalisierter Dateipfad -> pygame Sound
playing_channels = {}  # Map button index -> pygame Channel (für Laufzeit-Volume-Updates)
_playbacks_by_event = {}  # Map endevent id -> (button index, exact Channel)
_events_by_button = {}  # Map button index -> endevent id
_next_end_event = None
_issued_end_events = set()
button_texts = []
button_colors = []
jingle_paths = []
button_volumes = []  # pro-button volume in dB (-10..+10)
buttons_per_row = []
fadeout_duration = DEFAULT_FADEOUT_DURATION
button_height = DEFAULT_BUTTON_HEIGHT
set_volume = DEFAULT_VOLUME
settings = {}
_loaded_settings_path = None
_settings_snapshot = None
_original_settings_bytes = None
_backup_required = False
_write_blocked_error = None
_source_exists = False

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


def _default_settings():
    """Schema-2 board defaults used as migration/initialization input, not storage."""
    return {
        "schema_version": 2,
        "buttons": {
            "texts": _default_button_texts(),
            "colors": ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT,
            "paths": [""] * DEFAULT_BUTTON_COUNT,
            "volumes": [0] * DEFAULT_BUTTON_COUNT,
            "per_row": [DEFAULT_BUTTONS_PER_ROW_COUNT] * DEFAULT_BUTTON_ROW_COUNT,
        },
        "fadeout_duration": DEFAULT_FADEOUT_DURATION,
        "button_height": DEFAULT_BUTTON_HEIGHT,
        "window_size": [DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT],
        "volume": DEFAULT_VOLUME,
        "last_folder": str(Path.home()),
    }


def _validate_settings_data(raw_settings):
    if not isinstance(raw_settings, dict):
        raise ValueError("Das Settings-JSON muss ein Objekt enthalten.")
    raw_buttons = raw_settings.get("buttons")
    if raw_buttons is not None and not isinstance(raw_buttons, dict):
        raise ValueError("Der Settings-Eintrag 'buttons' muss ein Objekt enthalten.")
    version = raw_settings.get("schema_version")
    if version is not None and (not isinstance(version, int) or isinstance(version, bool)):
        raise ValueError("Die schema_version muss eine Ganzzahl sein.")
    if version is not None and version > CURRENT_SCHEMA_VERSION:
        raise ValueError(f"Die Settingsdatei verwendet die nicht unterstützte schema_version {version}.")
    return version


def _normalize_settings_data(raw_settings):
    _validate_settings_data(raw_settings)
    raw_buttons = raw_settings.get("buttons")

    normalized = deepcopy(raw_settings)
    normalized.pop("background_image", None)
    defaults = _default_settings()
    for key, value in defaults.items():
        if key not in normalized:
            normalized[key] = deepcopy(value)

    buttons = deepcopy(raw_buttons) if raw_buttons is not None else {}
    buttons["per_row"] = _normalize_buttons_per_row(buttons.get("per_row"))
    buttons["texts"] = _normalize_button_slots(buttons.get("texts"), _default_button_texts())
    buttons["colors"] = _normalize_button_slots(
        buttons.get("colors"), ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT
    )
    buttons["paths"] = _normalize_button_slots(buttons.get("paths"), [""] * DEFAULT_BUTTON_COUNT)
    buttons["volumes"] = _normalize_button_slots(buttons.get("volumes"), [0] * DEFAULT_BUTTON_COUNT)
    normalized["buttons"] = buttons
    normalized["schema_version"] = 2
    return normalized


def _set_persistence_state(path, snapshot, original_bytes, backup_required, error, source_exists):
    global _loaded_settings_path, _settings_snapshot, _original_settings_bytes
    global _backup_required, _write_blocked_error, _source_exists
    _loaded_settings_path = Path(path)
    _settings_snapshot = deepcopy(snapshot)
    _original_settings_bytes = original_bytes
    _backup_required = bool(backup_required)
    _write_blocked_error = error
    _source_exists = bool(source_exists)


def _save_result(success, skipped=False, error=None):
    return {"success": bool(success), "skipped": bool(skipped), "error": error}


_preset_token = None


def _inspect_unloaded_settings_path():
    load_settings()


def load_settings():
    """Load one schema-3 document; migration remains in RAM until a real save."""
    global _preset_token
    defaults = _default_settings()
    try:
        if not settings_file.parent.exists():
            # New installation: no directory is created by loading.
            document = presets.migrate_settings_to_schema3(defaults)
            _preset_token = None
            _set_persistence_state(settings_file, document, None, False, None, False)
            return document
        _preset_token = preset_storage.load_preset_settings(
            settings_file, initialize=True, initial_settings=defaults,
            legacy_normalizer=_normalize_settings_data)
        document = _preset_token.data
        _set_persistence_state(settings_file, document, _preset_token.original_bytes,
                               _preset_token.original_bytes is not None and _preset_token.source_schema_version != 3,
                               None, _preset_token.fingerprint.exists)
        return deepcopy(document)
    except (OSError, ValueError, TypeError) as error:
        _preset_token = None
        document = presets.migrate_settings_to_schema3(defaults)
        _set_persistence_state(settings_file, document, None, False,
                               f"Einstellungen konnten nicht sicher geladen werden: {error}", True)
        return document


def _board_document(board, document):
    presets._validate_schema2(board)
    result = deepcopy(document)
    for key in ("window_size", "volume", "last_folder"):
        if key in board:
            result[key] = deepcopy(board[key])
    active = next(p for p in result["presets"] if UUID(p["id"]) == UUID(result["active_preset_id"]))
    for key in ("buttons", "fadeout_duration", "button_height"):
        active[key] = deepcopy(board[key])
    return presets.validate_schema3_settings(result)


def save_settings(current_settings):
    """All regular writes use the schema-3 storage lock/token/backup protocol.

    Existing GUI callers may supply the flat active-board projection (schema 2).
    This projection is merged into the single document, never persisted alone.
    """
    global settings, _preset_token, _write_blocked_error
    if _loaded_settings_path != settings_file:
        _inspect_unloaded_settings_path()
    if _write_blocked_error:
        return _save_result(False, error=_write_blocked_error)
    try:
        if not isinstance(current_settings, dict):
            raise ValueError("Einstellungen müssen ein Objekt sein.")
        document = (presets.validate_schema3_settings(current_settings)
                    if current_settings.get("schema_version") == 3 else
                    _board_document(current_settings, _settings_snapshot))
        if _source_exists and document == _settings_snapshot:
            # Even a skipped save must detect another writer.
            preset_storage._check_expected(settings_file, _preset_token)
            return _save_result(True, skipped=True)
        # Check each existing ancestor before creating any missing directory.
        for parent in reversed(settings_file.parents):
            if os.path.lexists(parent):
                preset_storage._stat(parent, directory=True)
            else:
                parent.mkdir(mode=0o700)
        if _preset_token is None:
            token = preset_storage.load_preset_settings(
                settings_file, initialize=True, initial_settings=_default_settings(),
                legacy_normalizer=_normalize_settings_data)
            if token.fingerprint.exists:
                raise ValueError("Settingsdatei wurde seit dem Start neu angelegt; bitte neu laden.")
            _preset_token = token
        _preset_token = preset_storage.save_preset_settings(settings_file, document, expected=_preset_token)
        settings = deepcopy(document)
        _set_persistence_state(settings_file, document, _preset_token.original_bytes, False, None, True)
        return _save_result(True)
    except (OSError, ValueError, TypeError) as error:
        if getattr(error, "outcome", None) in ("saved", "indeterminate"):
            _write_blocked_error = f"Speicherzustand unklar; bitte schließen und neu laden: {error}"
        return _save_result(False, error=str(error))


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
            _issued_end_events.add(event_type)
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


def get_playing_indices():
    """Return the currently tracked 1-based jingle indices."""
    return list(playing_channels)


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

def _apply_document(document):
    global settings, button_texts, button_colors, jingle_paths, button_volumes
    global buttons_per_row, fadeout_duration, button_height, set_volume
    settings = deepcopy(document)
    board = presets.extract_active_board(document)
    button_texts = board["buttons"]["texts"]
    button_colors = board["buttons"]["colors"]
    jingle_paths = board["buttons"]["paths"]
    button_volumes = board["buttons"]["volumes"]
    buttons_per_row = board["buttons"]["per_row"]
    fadeout_duration = board["fadeout_duration"]
    button_height = board["button_height"]
    set_volume = board["volume"]


def initialize_settings():
    _apply_document(load_settings())


def get_current_settings():
    """Detached schema-2 active-board projection for existing GUI/export consumers."""
    current = presets.extract_active_board(settings)
    current["buttons"] = {"texts": button_texts[:], "colors": button_colors[:],
                          "paths": jingle_paths[:], "volumes": button_volumes[:],
                          "per_row": buttons_per_row[:]}
    current.update(fadeout_duration=fadeout_duration, button_height=button_height, volume=set_volume)
    return current


def get_preset_settings():
    return _board_document(get_current_settings(), settings)


def get_settings_storage_token():
    """Detached concurrency token for a confirmed import; never refresh implicitly."""
    if _write_blocked_error or _preset_token is None:
        raise ValueError("Kein gültiger Speicherstand vorhanden; bitte zuerst speichern oder neu laden.")
    return deepcopy(_preset_token)


def manage_presets(operation, *args, **kwargs):
    """Persist unsaved board first, then atomically commit the requested operation."""
    result = save_settings(get_current_settings())
    if not result["success"]:
        return result
    try:
        document = get_preset_settings()
        if operation == "switch":
            target = presets._preset_index(document, args[0])
            document["active_preset_id"] = document["presets"][target]["id"]
        else:
            function = {"create": presets.create_preset, "duplicate": presets.duplicate_preset,
                        "rename": presets.rename_preset, "delete": presets.delete_preset}[operation]
            document = function(document, *args, **kwargs)
        switching = UUID(document["active_preset_id"]) != UUID(settings["active_preset_id"])
        if switching:
            stop_all_playback()
        result = save_settings(document)
        if result["success"]:
            _apply_document(document)
        return result
    except (ValueError, OSError, RuntimeError) as error:
        message = str(error)
        if isinstance(error, presets.PresetValidationError) and error.code == "duplicate_name":
            message = "Ein Preset mit diesem Namen existiert bereits (auch Unicode-/Großschreibungsvarianten)."
        elif isinstance(error, presets.PresetValidationError) and error.location == "preset.name":
            message = "Ungültiger Presetname: Bitte einen nichtleeren Namen ohne äußere Leerzeichen oder Steuerzeichen eingeben."
        return _save_result(False, error=message)


def stop_all_playback():
    """Stop all mixer channels, including untracked fades; retire their events."""
    if pygame_available:
        event_ids = set(_playbacks_by_event) | _issued_end_events
        for index in range(pygame.mixer.get_num_channels()):
            channel = pygame.mixer.Channel(index)
            event = channel.get_endevent() if hasattr(channel, "get_endevent") else 0
            if event:
                event_ids.add(event)
            channel.set_endevent(0)
            channel.stop()
        for channel in list(playing_channels.values()):
            channel.set_endevent(0)
            channel.stop()
        if event_ids and hasattr(pygame.event, "clear"):
            pygame.event.clear(list(event_ids))
    playing_channels.clear()
    _playbacks_by_event.clear()
    _events_by_button.clear()
    _issued_end_events.clear()
    _sync_legacy_playback_state()
    # Do not rewind _next_end_event: queued old IDs must not be reused.


def get_settings_persistence_status():
    """Return read-only state needed by GUIs to report persistence problems."""
    return {
        "write_blocked": _write_blocked_error is not None,
        "error": _write_blocked_error,
        "backup_required": _backup_required,
        "source_exists": _source_exists,
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
