# Jingleplayer

Jingleplayer is a desktop soundboard and jingle player built with Python, PySide6, and pygame. It provides configurable jingle buttons across up to 50 persistent slots, simultaneous playback, individual jingle volume, fadeout, and persistent settings. This feature branch adds macOS build support and portable directory soundboards; native macOS release validation remains a separate requirement.

## Project structure

- `jingleplayer_app.py` – stable production entry point
- `jingleplayer_gui_pyside6.py` – production PySide6 interface
- `jingleplayer_gui_tkinter.py` – legacy/fallback interface
- `jingleplayer_logic.py` – shared audio and settings logic
- `jingleplayer_packages.py` – portable directory package validation, export, preparation and disk activation
- `PORTABLE_SOUNDBOARDS.md` – German export/import, recovery and validation guide
- `HELP.md` – German user manual bundled with the application
- `AUDIO_ENGINE.md` – technical audio-engine documentation
- `build_windows.ps1` – authoritative Windows build procedure

## Features

### Jingle layout

- Five configurable rows
- 0–10 visible tiles per row
- 50 persistent jingle slots in total
- Custom text, color, audio file, and individual volume for every slot
- Responsive tile widths and configurable tile height

Reducing the number of visible tiles does not discard hidden slot configurations. Increasing the row counts later restores those slots.

### Playback

- MP3 and WAV support
- Independent simultaneous playback of multiple jingles
- Independent playback of the same audio file from different tiles
- Channel-specific fadeout
- Automatic detection of natural playback completion
- Sound caching by normalized file path

Left-clicking an inactive tile starts its jingle. Clicking the same tile while it is playing stops or fades only that jingle; other active jingles continue unaffected. An active border represents the playing state and is cleared when playback stops or ends naturally.

There is intentionally no global STOP ALL control.

### Volume and fadeout

The main window provides a global volume slider from 0–100%. Each jingle also has an individual adjustment from -10 dB to +10 dB in its editor. Volume changes are applied to already running channels.

The global fadeout duration is configured in milliseconds and applies when an individual playing tile is stopped.

### Jingle editor

Right-click a tile to edit:

- jingle name/text
- MP3 or WAV file
- tile color
- individual dB adjustment

Audio selection uses the native file dialog. The directory of the most recently browsed audio file is remembered automatically. **Speichern** applies the changes; **Abbrechen**, Escape, and the window close button discard them.

### Settings and help

The **Einstellungen** dialog controls:

- fadeout duration
- the visible tile count for each of the five rows
- tile/button height

At least one tile must remain visible. Successfully saved layout changes take effect immediately without restarting the application.

The dialog also opens the bundled `HELP.md` manual. The production settings dialog does not provide controls for changing the settings-file location or configuring a default audio directory.

## Audio engine

The pygame mixer is initialized with:

- 44.1 kHz sample rate
- signed 16-bit audio
- stereo output
- 512-sample buffer
- 50 mixer channels, matching the maximum persistent slot count

For implementation and test details, see `AUDIO_ENGINE.md`.

## Settings and safe migration

Settings are stored at:

```text
~/.jingleplayer/jingleplayer_settings.json
```

On Windows this normally resolves to:

```text
C:\Users\<username>\.jingleplayer\jingleplayer_settings.json
```

Die lokale Settingsdatei verwendet jetzt `schema_version: 3`: globale Fenstergröße,
Gesamtlautstärke und Audioordner sowie die Presetliste und die aktive Preset-ID.
Jedes Preset erhält alle 50 Slots, Texte, Farben, Pfade, dB-Werte, Reihenlayout,
Fadeout und Kachelhöhe. Die Auswahl im Hauptfenster und das Menü **Presets** bieten
Erstellen, Duplizieren, Umbenennen und Löschen. Das letzte Preset ist geschützt;
beim Löschen des aktiven Presets wird ein Nachfolger ausgewählt.

Schema 2 und unterstützte ältere Settings werden beim Laden nur im Speicher in
ein Standard-Preset migriert. Erst ein tatsächlicher Save schreibt Schema 3 und
legt vorher ein bytegenaues Backup an:

```text
jingleplayer_settings.json.pre-presets.<SHA256>.json
```

Bestehende Pre-PySide6-Backups bleiben unverändert. Fehlerhafte oder unbekannte
Felder werden nicht still verworfen, sondern blockieren die Migration. Die alte
v1.0.0-Anwendung kann Schema 3 nicht laden; für einen Rückwechsel ist die geprüfte
Pre-Preset-Sicherung nötig. [Preset-Details und Wiederherstellung](PRESETS.md).

Corrupt or structurally invalid settings are not overwritten. Unsupported future schema versions block startup instead of being replaced. Load and save failures are reported through GUI error dialogs.

No fallback settings directory is used.

## Portable Soundboards

### Hintergrundbild pro Preset

Im Menü **Presets → Hintergrundbild auswählen…** ein PNG/JPEG auswählen. Das Bild
wird sofort für das aktive Preset gespeichert und hinter dessen Jingle-Kacheln
angezeigt. **Hintergrundbild entfernen** stellt die bisherige Darstellung wieder
her und löscht keine Bilddatei. Im Menü steht der aktuell gespeicherte Bildpfad.
Preset-Wechsel und Neustart übernehmen die jeweilige Einstellung automatisch.

Die Darstellung füllt den Kachelbereich proportional aus und beschneidet mittig;
Resize skaliert das bereits geladene Bild. Buttonfarben und Bedienung bleiben
erhalten, Menüs und Lautstärkeregler liegen außerhalb der Bildfläche. Fehlende oder
beschädigte Bilder führen zum normalen Hintergrund mit Statusmeldung; der Pfad
bleibt gespeichert. Schema 3 bleibt unverändert nummeriert, das Feld ist optional.

Bilder bleiben in Phase 18B lokal: Paketversion 1/Board-Schema 2 enthält weiterhin
keine Hintergrunddaten. Ein Import als neues Preset startet ohne Bild; Ersetzen des
aktiven Presets entfernt dessen Hintergrundzuweisung. Andere Presets bleiben
unverändert. Die portable Bildmitnahme ist für Phase 18D vorgesehen.

Im Menü **Soundboard** stehen **Soundboard exportieren...** und **Soundboard importieren...** bereit. Export: vorhandenen Ziel-Elternordner auswählen, neuen Paketnamen eingeben und gegebenenfalls fehlende Audiozuweisungen ausdrücklich nur für den Export leeren. Alle 50 Plätze einschließlich ausgeblendeter Tasten werden berücksichtigt.

Import: Paketordner auswählen, Vorschau prüfen und Ersetzen bestätigen. Lokale Fenstergröße, Gesamtlautstärke und der gemerkte Audioordner bleiben erhalten. Vor dem Wechsel wird die Wiedergabe gestoppt; eine separate Wiederherstellungskopie sichert die vorherige Settingsdatei. Der Import kann ein neues Preset hinzufügen oder nach ausdrücklicher Auswahl nur das aktive ersetzen. Exportiert wird ausschließlich das aktive Preset; ZIP und Jingle-Pools bleiben nicht implementiert.

Anleitung, Paketformat, Grenzen bei parallelen Schreibzugriffen und sichere manuelle Wiederherstellung: [Portable Soundboards](PORTABLE_SOUNDBOARDS.md). Import bewahrt die übrigen Presets; die Kopie ist keine Garantie für vollständige Ausfallsicherheit.

## Requirements

Runtime dependencies include PySide6 and pygame:

```powershell
python -m pip install -r requirements.txt
```

Install development and test dependencies with:

```powershell
python -m pip install -r requirements-dev.txt
```

## Starting from source

From the project directory, run the stable product entry point:

```powershell
python jingleplayer_app.py
```

## Automated tests

Run the complete regression suite with:

```powershell
python -m pytest -q
```

The suite covers audio logic, settings persistence and migration, volume behavior, the PySide6 interface, and the product/build entry points. The real audio smoke test remains a separate interactive Windows test.

The automatic test workflow is configured for Ubuntu and Windows with Python 3.11/3.13, plus macOS with Python 3.11. It uses offscreen Qt and dummy SDL drivers; real audio hardware is not tested. The separate manually dispatched macOS workflow retains its native arm64/x86_64 builds and artifact names. Workflow configuration alone does not establish a successful CI run. See the [validation checklist](PORTABLE_SOUNDBOARDS.md#validierung-und-freigabe) for native manual checks and platform-specific skips.

## Windows build

The authoritative Windows build procedure is:

```powershell
.\build_windows.ps1
```

The script runs syntax checks and the automated test suite before creating the windowed onefile application:

```text
dist\Jingleplayer.exe
```

The root-level historical `.spec` files are not the authoritative build procedure.

## Changing the application icon

The application icon is:

```text
assets\jingleplayer.ico
```

To use another icon:

1. Create or obtain a Windows `.ico` file.
2. Replace `assets\jingleplayer.ico` with the new file.
3. Keep the filename `jingleplayer.ico`.
4. Rebuild the application:

   ```powershell
   .\build_windows.ps1
   ```

The resulting executable is:

```text
dist\Jingleplayer.exe
```

The same icon file is used by the PySide6 application window and the packaged Windows executable. For good results at different display scales, use a multi-resolution ICO containing common sizes such as 16x16, 32x32, 48x48, 128x128, and 256x256.

Windows may cache executable icons, so File Explorer or the taskbar may temporarily continue to display the previous icon after replacement.
