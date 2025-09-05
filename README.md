Jingleplayer

Overview

Jingleplayer is an application for playing audio jingles (MP3, WAV) with a user-friendly graphical user interface (GUI). The software is based on Python, uses Pygame for audio playback and Tkinter for the user interface.

Updated with separate GUI and logic

jingleplayerpygame.py is osolete

Functions

Link any audio files (*.mp3, *.wav) to buttons

Customizable button texts, colors and number of buttons per row

Volume control via a slider

Fadeout function when stopping a jingle

Indicators for displaying the playback status

Settings menu for editing the button properties

Settings are saved automatically

Installation

Prerequisites

Python 3.7 or higher

The following Python libraries:

pip install pygame

Installation & Start

Download the repository or copy the Python file.

Start the program with:

python jingleplayer.py

Operation

Assign jingles: Right-click on a button → Select file.

Button settings: Adjust color, name and jingle via the context menu.

Start jingle: Left-click on a button.

Stop jingle: Left-click again or another jingle is started.

Change settings: Open the “Settings” menu and make adjustments.

Volume: Adjust using the upper slider.

Saving the settings

The configuration is saved in a JSON file in the user directory:

~/.jingleplayer/jingleplayer_settings.json

If the directory is not writable, an alternative directory in the current working directory is used.

License

This project is licensed under the MIT license.

Author

Developed by Young Crashers.

 
