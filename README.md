# Jingleplayer

Jingleplayer is a Windows desktop soundboard and jingle player built with Python, PySide6, and pygame. It provides configurable jingle buttons across up to 50 persistent slots, simultaneous playback, individual jingle volume, fadeout, and persistent settings.

## Project structure

- `jingleplayer_app.py` – stable production entry point
- `jingleplayer_gui_pyside6.py` – production PySide6 interface
- `jingleplayer_gui_tkinter.py` – legacy/fallback interface
- `jingleplayer_logic.py` – shared audio and settings logic
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

The current format uses `schema_version` 2. All 50 slot configurations remain persistent independently of how many tiles are visible.

Legacy pre-schema-2 settings are normalized in memory. Merely starting and closing Jingleplayer without a change does not rewrite the legacy file. On the first actual changed save, the original file is preserved byte-for-byte as:

```text
jingleplayer_settings.pre-pyside6.json
```

Corrupt or structurally invalid settings are not overwritten. Unsupported future schema versions block startup instead of being replaced. Load and save failures are reported through GUI error dialogs.

No fallback settings directory is used.

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
