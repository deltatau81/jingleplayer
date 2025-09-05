import pygame
import os
import json
from pathlib import Path

# Konstanten definieren für Lesbarkeit und Wartung
DEFAULT_BUTTON_COUNT = 40 # Max Buttons gesamt
DEFAULT_BUTTONS_PER_ROW_COUNT = 10 # Max Buttons pro Reihe
FADEOUT_CHECK_INTERVAL_MS = 100
FONT_SIZE_BUTTONS = 12
FONT_SIZE_TITLE = 24
DEFAULT_FADEOUT_DURATION = 1000 # Default fadeout duration in milliseconds
DEFAULT_BUTTON_HEIGHT = 2 # Definiere eine Standardhöhe der Schaltflächen
DEFAULT_WINDOW_WIDTH = 800 # Definiere eine Standardbreite
DEFAULT_WINDOW_HEIGHT = 600 # Definiere eine Standardhöhe
DEFAULT_VOLUME = 100 # Default volume

# Variable, um den aktuellen Status des Players zu speichern
current_jingle = None
jingle_playing = False
sounds = {} # Dictionary zum Speichern geladener Sound-Objekte, um Wiederholtes Laden zu vermeiden
button_texts = []
button_colors = []
jingle_paths = []
buttons_per_row = []
fadeout_duration = DEFAULT_FADEOUT_DURATION
button_height = DEFAULT_BUTTON_HEIGHT
set_volume = DEFAULT_VOLUME
settings = {}

# Pfad für die Einstellungen im Benutzerverzeichnis
data_dir = Path.home() / ".jingleplayer"
settings_file = data_dir / "jingleplayer_settings.json"

# Initialisierung von pygame (wird jetzt in der Logik-Datei gemacht)
pygame.init()
pygame.mixer.init()

# ---  Logik-Funktionen (GUI-unabhängig) ---

# Überprüfen und Standardwerte setzen
def check_and_set_defaults(loaded_settings, default_settings):
    for key, value in default_settings.items():
        if key not in loaded_settings:
            loaded_settings[key] = value
    return loaded_settings

# Einstellungen laden
def load_settings():
    default_settings = {
        "buttons": {
            "texts": [f"Jingle {i}" for i in range(1, DEFAULT_BUTTON_COUNT + 1)],
            "colors": ["SystemButtonFace"] * DEFAULT_BUTTON_COUNT,
            "paths": [""] * DEFAULT_BUTTON_COUNT,
            "per_row": [DEFAULT_BUTTONS_PER_ROW_COUNT] * 4  # Default buttons per row for 4 rows
        },
        "fadeout_duration": DEFAULT_FADEOUT_DURATION,
        "button_height": DEFAULT_BUTTON_HEIGHT,
        "window_size": [DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT],
        "volume": DEFAULT_VOLUME
    }
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                loaded_settings = json.load(f)
            loaded_settings = check_and_set_defaults(loaded_settings, default_settings)
            # --- Fix: Ensure per_row is always a list of length 4 and not empty ---
            if ("per_row" not in loaded_settings["buttons"] or
                not isinstance(loaded_settings["buttons"]["per_row"], list) or
                len(loaded_settings["buttons"]["per_row"]) != 4 or
                sum(loaded_settings["buttons"]["per_row"]) == 0):
                loaded_settings["buttons"]["per_row"] = [DEFAULT_BUTTONS_PER_ROW_COUNT] * 4
            # Ensure at least 1 button in first row
            if loaded_settings["buttons"]["per_row"][0] < 1:
                loaded_settings["buttons"]["per_row"][0] = 1
            # Ensure lists match the number of buttons
            total_buttons = sum(loaded_settings["buttons"]["per_row"])
            for key in ["texts", "colors", "paths"]:
                while len(loaded_settings["buttons"][key]) < total_buttons:
                    if key == "colors":
                        loaded_settings["buttons"][key].append("SystemButtonFace")
                    else:
                        loaded_settings["buttons"][key].append("")
                while len(loaded_settings["buttons"][key]) > total_buttons:
                    loaded_settings["buttons"][key].pop()
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

def play_jingle(index, jingle_path, current_fadeout_duration): # Nimmt fadeout_duration als Argument
    global sounds # Zugriff auf das globale Dictionary
    if index in sounds and sounds[index] is not None and sounds[index].get_num_channels() > 0:
        stop_jingle(index, current_fadeout_duration)
    else:
        if jingle_path:
            file_path = jingle_path
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in [".mp3", ".wav"]:
                try:
                    if file_path not in sounds: # Sound-Objekt wiederverwenden, falls bereits geladen
                        sounds[index] = pygame.mixer.Sound(file_path)
                    sound = sounds[index]
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                        channel.set_endevent(pygame.USEREVENT + index)
                        update_indicator_state(index, True) # Aufruf der Logik-Funktion für Indikator-Status
                        print(f"Spielt Jingle {index}: {os.path.basename(file_path)}")
                        return {"indicator_update": {"index": index, "playing": True}, "success": True} # Rückmeldung für GUI
                except pygame.error as e:
                    error_message = f"Die Datei {file_path} konnte nicht geladen werden: {e}"
                    print(error_message)
                    return {"error": error_message, "success": False} # Rückmeldung für GUI
            else:
                error_message = f"Das Dateiformat {file_extension} wird nicht unterstützt."
                print(error_message)
                return {"error": error_message, "success": False} # Rückmeldung für GUI
        else:
            error_message = "Kein Jingle zugewiesen. Bitte wählen Sie eine Datei im Einstellungsmenü."
            print(error_message)
            return {"error": error_message, "success": False} # Rückmeldung für GUI
    return {"success": True} # Rückmeldung für GUI (Stop Jingle Fall)


def stop_jingle(index, current_fadeout_duration): # Nimmt fadeout_duration als Argument
    if index in sounds and sounds[index] is not None and sounds[index].get_num_channels() > 0:
        sounds[index].fadeout(current_fadeout_duration)
        update_indicator_state(index, False) # Aufruf der Logik-Funktion für Indikator-Status
        print(f"Jingle {index} gestoppt mit Fadeout.")
        return {"indicator_update": {"index": index, "playing": False}} # Rückmeldung für GUI
    return {} # Rückmeldung für GUI (Kein Sound zum stoppen)


def check_sound_end():
    ended_indicators = [] # Liste der Indizes, die gestoppt werden müssen
    for event in pygame.event.get():
        if event.type >= pygame.USEREVENT:
            index = event.type - pygame.USEREVENT
            update_indicator_state(index, False) # Logik-Funktion für Indikator-Status
            ended_indicators.append({"index": index, "playing": False}) # Status-Daten für GUI
    return ended_indicators # Rückmeldung für GUI (Liste von Indikator-Updates)


def update_indicator_state(index, playing):
    # Diese Funktion verwaltet *nur* den Zustand, keine GUI-Aktualisierung direkt
    print(f"Indikator {index} wird auf 'playing'={playing} gesetzt (Logik)")
    return {"index": index, "playing": playing} # Gibt Daten zurück, die die GUI zur Aktualisierung nutzen kann

def set_volume_logic(volume_percent):
    volume = int(volume_percent) / 100
    for i in range(pygame.mixer.get_num_channels()):
        channel = pygame.mixer.Channel(i)
        channel.set_volume(volume)
    global set_volume
    set_volume = volume_percent
    print(f"Lautstärke auf {volume_percent}% gesetzt (Logik)")
    return {"volume_set": volume_percent} # Rückmeldung für GUI

def initialize_settings():
    global settings, button_texts, button_colors, jingle_paths, buttons_per_row, fadeout_duration, button_height, set_volume
    settings = load_settings()
    button_texts = settings["buttons"]["texts"]
    button_colors = settings["buttons"]["colors"]
    jingle_paths = settings["buttons"]["paths"]
    buttons_per_row = settings["buttons"]["per_row"]
    if len(buttons_per_row) < 4:
        buttons_per_row += [0] * (4 - len(buttons_per_row))
    fadeout_duration = settings["fadeout_duration"]
    button_height = settings["button_height"]
    set_volume = settings["volume"]
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
            "per_row": buttons_per_row[:]
        },
        "fadeout_duration": fadeout_duration,
        "button_height": button_height,
        "window_size": window_size[:],
        "volume": set_volume
    }

def update_settings_data(texts, colors, paths, per_row, f_duration, b_height, w_size, vol):
    global button_texts, button_colors, jingle_paths, buttons_per_row, fadeout_duration, button_height, set_volume, settings
    # Ensure at least 1 button in first row
    if per_row and per_row[0] < 1:
        per_row[0] = 1
    total_buttons = sum(per_row)
    # Adjust lists to match the new total_buttons count
    if len(texts) < total_buttons:
        texts += [f"Jingle {i+1}" for i in range(len(texts), total_buttons)]
    elif len(texts) > total_buttons:
        texts = texts[:total_buttons]
    if len(colors) < total_buttons:
        colors += ["SystemButtonFace"] * (total_buttons - len(colors))
    elif len(colors) > total_buttons:
        colors = colors[:total_buttons]
    if len(paths) < total_buttons:
        paths += [""] * (total_buttons - len(paths))
    elif len(paths) > total_buttons:
        paths = paths[:total_buttons]

    button_texts = texts
    button_colors = colors
    jingle_paths = paths
    buttons_per_row = per_row
    fadeout_duration = f_duration
    button_height = b_height
    set_volume = vol
    settings["window_size"] = w_size # Window size wird separat im settings dict gespeichert.

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