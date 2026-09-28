# Jingleplayer

Jingleplayer is a desktop application for playing audio jingles using configurable buttons. It supports MP3 and WAV files and provides a graphical user interface based on Tkinter.

The application is written in Python and uses pygame for audio playback.

## Project structure

The application is separated into GUI and application logic:

- `jingleplayer_gui_tkinter.py` – Tkinter graphical user interface
- `jingleplayer_logic.py` – audio playback, settings and application logic
- `HELP.md` – German user manual
- `AUDIO_ENGINE.md` – technical documentation of the audio engine

## Features

### Jingle buttons

- Up to 40 configurable jingle buttons
- Four configurable button rows
- 0–10 buttons per row
- MP3 and WAV playback
- Custom text for every button
- Custom button colors
- Individual audio file assignment
- Right-click configuration dialog
- Playback status indicators
- Individual volume control for each button

A left-click starts the assigned jingle.

Clicking an already playing button again stops that jingle using the configured fadeout.

Multiple jingles can play simultaneously and are handled independently.

### Audio engine

The audio engine is based on `pygame.mixer`.

The current implementation provides:

- Dedicated mixer channels for active buttons
- Up to 50 configured mixer channels
- Independent playback of multiple jingles
- Independent playback even when the same audio file is used by multiple buttons
- Channel-specific fadeout
- Automatic detection of natural playback completion
- Sound caching by normalized file path
- Cleanup of finished playback state

The mixer is initialized with:

- 44.1 kHz sample rate
- 16-bit audio
- Stereo output
- 512 sample buffer

For technical details see `AUDIO_ENGINE.md`.

### Volume control

Jingleplayer provides two levels of volume control.

**Global volume**

The slider in the main window controls the overall playback volume from 0–100%.

**Individual button volume**

Each jingle button has an individual volume adjustment from -10 dB to +10 dB.

Changes to the individual volume are also applied to an already running playback channel.

### Fadeout

When a playing button is stopped, the configured fadeout is applied only to that button's playback channel.

Other simultaneously playing jingles continue playing.

The fadeout duration can be configured in milliseconds.

### Graphical user interface

The GUI provides:

- Configurable button layout
- Playback status indicators
- Global volume slider
- Individual button volume sliders
- Settings dialog
- Right-click button editor
- Saved window size
- Splash screen during application startup

The main window remains hidden while the interface is constructed. This avoids partially rendered controls being visible during startup.

### Persistent settings

Settings are stored in a JSON file.

The default location is:

`~/.jingleplayer/jingleplayer_settings.json`

On Windows this normally corresponds to:

`C:\Users\<username>\.jingleplayer\jingleplayer_settings.json`

If the normal user directory cannot be used, Jingleplayer can use a fallback data directory.

Stored settings include:

- Button texts
- Button colors
- Audio file paths
- Buttons per row
- Global volume
- Individual button volumes
- Fadeout duration
- Button height
- Window size
- Default audio directory

Existing settings are supplemented with required default values when necessary.

## Requirements

- Python 3
- pygame

Install the runtime dependencies with:

```powershell
python -m pip install -r requirements.txt
```

For development and automated testing:

```powershell
python -m pip install -r requirements-dev.txt
```

## Starting Jingleplayer

Open a terminal in the project directory and run:

```powershell
python jingleplayer_gui_tkinter.py
```

## Operation

### Play a jingle

Left-click a configured button.

The assigned audio file starts playing and the status indicator changes to the active state.

### Stop a jingle

Left-click the same button again.

The configured fadeout is applied to that button.

Other active jingles continue playing independently.

### Configure a button

Right-click a jingle button to open its configuration dialog.

The dialog allows you to change:

- Button text
- Button color
- Assigned MP3 or WAV file

Changes can be saved with **Apply** or discarded with **Cancel**.

## Settings

The settings dialog provides configuration for:

- Fadeout duration
- Button height
- Number of buttons in each of the four rows
- Default audio directory
- Settings file location

The default fadeout duration is 1000 ms.

Each of the four rows can contain between 0 and 10 buttons.

## Automated tests

The project contains an automated regression test suite for the audio engine, settings handling and volume logic.

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
