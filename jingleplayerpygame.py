import pygame
import os
import json
import tkinter as tk
from tkinter import simpledialog, messagebox, colorchooser, filedialog
from pathlib import Path

# Variable, um den aktuellen Status des Players zu speichern
current_jingle = None
jingle_playing = False
sounds = []
buttons = []
indicators = []
indicator_ovals = []
current_popup = None  # Track the currently open popup

# Pfad für die Einstellungen im Benutzerverzeichnis
data_dir = Path.home() / ".jingleplayer"
try:
    data_dir.mkdir(exist_ok=True)
except PermissionError:
    fallback_dir = Path.cwd() / "jingleplayer_data"
    try:
        fallback_dir.mkdir(exist_ok=True)
        data_dir = fallback_dir
        messagebox.showinfo("Hinweis", f"Einstellungen werden im Ordner {data_dir} gespeichert, da der Standardordner nicht zugänglich war.")
    except PermissionError:
        messagebox.showerror("Fehler", f"Weder der Standardordner ({Path.home()}) noch das aktuelle Verzeichnis sind beschreibbar. Das Programm kann keine Einstellungen speichern.")
        exit(1)

settings_file = data_dir / "jingleplayer_settings.json"

# Überprüfen und Standardwerte setzen
def check_and_set_defaults(settings, default_settings):
    for key, value in default_settings.items():
        if key not in settings:
            settings[key] = value
    return settings

# Einstellungen laden
def load_settings():
    default_settings = {
        "buttons": {
            "texts": [f"Jingle {i}" for i in range(1, 41)],
            "colors": ["SystemButtonFace"] * 40,
            "paths": [""] * 40,
            "per_row": [10, 10, 10, 10]  # Default buttons per row for 4 rows
        },
        "fadeout_duration": 1000,  # Default fadeout duration in milliseconds
        "button_height": 2,  # Default button height
        "window_size": [800, 600],  # Default window size (width, height)
        "volume": 100  # Default volume
    }
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                loaded_settings = json.load(f)
            loaded_settings = check_and_set_defaults(loaded_settings, default_settings)
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
        except (IOError, json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Die Datei {settings_file} konnte nicht gelesen werden: {e}")
            return default_settings
    return default_settings

# Einstellungen speichern
def save_settings():
    try:
        settings = {
            "buttons": {
                "texts": button_texts[:],
                "colors": button_colors[:],
                "paths": jingle_paths[:],
                "per_row": buttons_per_row[:]
            },
            "fadeout_duration": fadeout_duration,
            "button_height": button_height,
            "window_size": [root.winfo_width(), root.winfo_height()],  # Save current window size
            "volume": volume_slider.get()  # Save current volume
        }
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=4)
    except IOError:
        messagebox.showerror("Fehler", f"Die Datei {settings_file} konnte nicht gespeichert werden. Überprüfen Sie die Berechtigungen.")

def update_indicator(index, playing):
    indicator = indicators[index - 1]
    indicator.delete("all")
    if playing:
        # Draw black border for play symbol (doubled in size)
        indicator.create_polygon(9, 9, 31, 20, 9, 31, outline="black", fill="")
        # Draw red play symbol (doubled in size)
        indicator.create_polygon(10, 10, 30, 20, 10, 30, fill="red")
    else:
        # Draw green pause symbol (doubled in size)
        indicator.create_rectangle(10, 10, 16, 30, fill="green")
        indicator.create_rectangle(20, 10, 26, 30, fill="green")

def play_jingle(index):
    if index < len(sounds) and sounds[index] is not None and sounds[index].get_num_channels() > 0:
        stop_jingle(index)
    else:
        if jingle_paths[index - 1]:
            file_path = jingle_paths[index - 1]
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in [".mp3", ".wav"]:
                try:
                    sound = pygame.mixer.Sound(file_path)
                    if index < len(sounds):
                        sounds[index] = sound
                    else:
                        sounds.append(sound)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sounds[index])
                        channel.set_endevent(pygame.USEREVENT + index)
                        update_indicator(index, True)
                        print(f"Spielt Jingle {index}: {os.path.basename(file_path)}")
                except pygame.error as e:
                    messagebox.showerror("Fehler", f"Die Datei {file_path} konnte nicht geladen werden: {e}")
            else:
                messagebox.showerror("Fehler", f"Das Dateiformat {file_extension} wird nicht unterstützt.")
        else:
            print("Kein Jingle zugewiesen. Bitte wählen Sie eine Datei im Einstellungsmenü.")

def stop_jingle(index):
    if index < len(sounds) and sounds[index] is not None and sounds[index].get_num_channels() > 0:
        sounds[index].fadeout(fadeout_duration)
        update_indicator(index, False)
        print(f"Jingle {index} gestoppt mit Fadeout.")

def check_sound_end():
    for event in pygame.event.get():
        if event.type >= pygame.USEREVENT:
            index = event.type - pygame.USEREVENT
            update_indicator(index, False)

# Initialisierung von pygame
pygame.init()
pygame.mixer.init()

# Einstellungen laden
settings = load_settings()
button_texts = settings["buttons"]["texts"]
button_colors = settings["buttons"]["colors"]
jingle_paths = settings["buttons"]["paths"]
buttons_per_row = settings["buttons"]["per_row"]
fadeout_duration = settings["fadeout_duration"]
button_height = settings["button_height"]
set_volume = settings["volume"]
print(f"buttons_per_row: {buttons_per_row} (Typ: {type(buttons_per_row)})")

# Initialize sounds list with the correct number of elements
sounds = [None] * sum(buttons_per_row)

def open_settings_menu():
    if hasattr(open_settings_menu, 'window') and open_settings_menu.window.winfo_exists():
        open_settings_menu.window.lift()
        return

    def change_button_color(index):
        color_code = colorchooser.askcolor(title=f"Farbe für Jingle {index} wählen")[1]
        if color_code:
            button_colors[index - 1] = color_code
            buttons[index - 1].config(bg=color_code)
            save_settings()

    def assign_jingle_file(index):
        file_path = filedialog.askopenfilename(title=f"Jingle für Button {index} wählen", filetypes=[("Audio Dateien", "*.mp3;*.wav")])
        if file_path:
            jingle_paths[index - 1] = file_path
            save_settings()

    def change_button_text(index):
        new_text = simpledialog.askstring("Button-Text ändern", f"Neuer Text für Button {index}:", initialvalue=button_texts[index - 1])
        if new_text:
            button_texts[index - 1] = new_text
            buttons[index - 1].config(text=new_text)
            save_settings()

    def update_fadeout_duration():
        global fadeout_duration
        fadeout_duration = int(fadeout_entry.get())
        save_settings()

    def update_button_height():
        global button_height
        button_height = int(button_height_entry.get())
        save_settings()
        update_buttons()

    def update_buttons_per_row(row):
        global buttons_per_row
        value = int(buttons_per_row_entries[row].get())
        if value < 0 or value > 10:
            messagebox.showerror("Fehler", "Die Anzahl der Buttons pro Reihe muss zwischen 0 und 10 liegen.")
            buttons_per_row_entries[row].delete(0, tk.END)
            buttons_per_row_entries[row].insert(0, str(buttons_per_row[row]))
        else:
            buttons_per_row[row] = value
            save_settings()
            update_buttons()

    settings_window = tk.Toplevel(root)
    open_settings_menu.window = settings_window
    settings_window.title("Einstellungen")

    # Dropdown menu for editing buttons
    dropdown_frame = tk.Frame(settings_window)
    dropdown_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(dropdown_frame, text="Button bearbeiten:", font=("Arial", 12)).pack(side="left")
    button_var = tk.StringVar(dropdown_frame)
    button_var.set(button_texts[0])  # Default value
    button_menu = tk.OptionMenu(dropdown_frame, button_var, *button_texts)
    button_menu.pack(side="left", padx=5)

    def edit_selected_button():
        index = button_texts.index(button_var.get()) + 1
        change_button_text(index)
        change_button_color(index)
        assign_jingle_file(index)

    tk.Button(dropdown_frame, text="Bearbeiten", font=("Arial", 10), command=edit_selected_button).pack(side="left", padx=5)

    # Fadeout duration settings
    fadeout_frame = tk.Frame(settings_window)
    fadeout_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(fadeout_frame, text="Fadeout-Dauer (ms):", font=("Arial", 12)).pack(side="left")
    fadeout_entry = tk.Entry(fadeout_frame, width=5)
    fadeout_entry.insert(0, str(fadeout_duration))
    fadeout_entry.pack(side="left", padx=5)
    tk.Button(fadeout_frame, text="Aktualisieren", font=("Arial", 10), command=update_fadeout_duration).pack(side="left", padx=5)

    # Button height settings
    button_height_frame = tk.Frame(settings_window)
    button_height_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(button_height_frame, text="Button-Höhe:", font=("Arial", 12)).pack(side="left")
    button_height_entry = tk.Entry(button_height_frame, width=5)
    button_height_entry.insert(0, str(button_height))
    button_height_entry.pack(side="left", padx=5)
    tk.Button(button_height_frame, text="Aktualisieren", font=("Arial", 10), command=update_button_height).pack(side="left", padx=5)

    # Initialize buttons_per_row_entries
    buttons_per_row_entries = []

    # Buttons per row settings
    for row in range(4):
        row_frame = tk.Frame(settings_window)
        row_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(row_frame, text=f"Buttons pro Reihe {row + 1} (0-10):", font=("Arial", 12)).pack(side="left")
        entry = tk.Entry(row_frame, width=5)
        entry.insert(0, str(buttons_per_row[row]))
        entry.pack(side="left", padx=5)
        buttons_per_row_entries.append(entry)
        tk.Button(row_frame, text="Aktualisieren", font=("Arial", 10), command=lambda row=row: update_buttons_per_row(row)).pack(side="left", padx=5)

    # Add the specified text
    tk.Label(settings_window, text="Bei Änderungen des Layouts muss die Anwendung neu gestartet werden.", font=("Arial", 10)).pack(pady=10)

    # Close settings button
    close_button = tk.Button(settings_window, text="Schließen", font=("Arial", 12), command=settings_window.destroy)
    close_button.pack(pady=10)

def on_button_click(index):
    if not jingle_paths[index - 1]:
        messagebox.showerror("Fehler", f"Kein Jingle für Button {index} zugewiesen.")
    else:
        if index < len(sounds) and sounds[index] is not None and sounds[index].get_num_channels() > 0:
            stop_jingle(index)
        else:
            play_jingle(index)

def on_button_right_click(event, index):
    if event.num == 3:  # Right-click
        open_button_settings(index)

def open_button_settings(index):
    global current_popup
    if current_popup is not None:
        current_popup.destroy()
    current_popup = tk.Toplevel(root)
    current_popup.title(f"Button {index + 1} Einstellungen")
    current_popup.attributes("-topmost", True)  # Ensure the popup is always on top

    # Text input for button text
    tk.Label(current_popup, text="Button-Text:").pack(pady=5)
    text_input = tk.Entry(current_popup)
    text_input.insert(0, button_texts[index])
    text_input.pack(pady=5)

    # Color chooser for button color
    tk.Label(current_popup, text="Button-Farbe:").pack(pady=5)
    color_button = tk.Button(current_popup, text="Farbe wählen", command=lambda: choose_color(index, color_button))
    color_button.pack(pady=5)

    # File chooser for button file
    tk.Label(current_popup, text="Jingle-Datei:").pack(pady=5)
    file_button = tk.Button(current_popup, text="Datei wählen", command=lambda: choose_file(index, file_button))
    file_button.pack(pady=5)

    # Button frame for "Übernehmen" and "Abbrechen"
    button_frame = tk.Frame(current_popup)
    button_frame.pack(pady=10)

    # Save button
    save_button = tk.Button(button_frame, text="Übernehmen", bg="lightgray", command=lambda: save_button_settings(index, text_input.get(), color_button.cget("bg"), file_button.cget("text")))
    save_button.pack(side="left", padx=5)

    # Close button
    close_button = tk.Button(button_frame, text="❌Abbrechen", bg="red", fg="white", command=current_popup.destroy)
    close_button.pack(side="left", padx=5)

def choose_color(index, button):
    color_code = colorchooser.askcolor(title=f"Farbe für Jingle {index + 1} wählen")[1]
    if color_code:
        button.config(bg=color_code)

def choose_file(index, button):
    file_path = filedialog.askopenfilename(title=f"Jingle für Button {index + 1} wählen", filetypes=[("Audio Dateien", "*.mp3;*.wav")])
    if file_path:
        button.config(text=file_path)

def save_button_settings(index, text, color, file_path):
    button_texts[index] = text
    button_colors[index] = color
    jingle_paths[index] = file_path
    buttons[index].config(text=text, bg=color)
    print(f"Button {index + 1} gespeichert: Text={text}, Farbe={color}, Datei={file_path}")
    save_settings()
    if current_popup is not None:
        current_popup.destroy()  # Close the popup after saving

def update_buttons(event=None):
    global buttons, indicators, indicator_ovals
    for widget in content_frame.winfo_children():
        widget.destroy() 
    for button in buttons:
        button.destroy()
    buttons.clear()
    for indicator in indicators:
        indicator.destroy()
    indicators.clear()
    indicator_ovals.clear()

    row_frame = None
    button_index = 0
    for row in range(4):
        if buttons_per_row[row] > 0:
            row_frame = tk.Frame(content_frame)
            row_frame.pack(fill="x", padx=20, pady=5)
            for i in range(buttons_per_row[row]):
                # Set default text if button_texts is empty
                if button_index >= len(button_texts) or not button_texts[button_index]:
                    button_texts[button_index] = f"Jingle {button_index + 1}"
                
                button = tk.Button(row_frame, text=button_texts[button_index], font=("Arial", 12), bg=button_colors[button_index], width=10, height=button_height, command=lambda i=button_index: on_button_click(i + 1))
                button.grid(row=0, column=i, sticky="ew", padx=5, pady=5)
                button.bind("<Button-3>", lambda event, i=button_index: on_button_right_click(event, i))
                row_frame.grid_columnconfigure(i, weight=1)

                buttons.append(button)

                indicator_frame = tk.Frame(row_frame)
                indicator_frame.grid(row=1, column=i, sticky="ew")

                indicator = tk.Canvas(indicator_frame, width=40, height=40)  # Adjusted size for doubled symbols
                # Draw initial green pause symbol (doubled in size)
                indicator.create_rectangle(10, 10, 16, 30, fill="green")
                indicator.create_rectangle(20, 10, 26, 30, fill="green")
                indicator.pack(side="left")
                indicators.append(indicator)
                indicator_ovals.append(indicator)

                tk.Label(indicator_frame, text=str(button_index + 1), font=("Arial", 8)).pack(side="left")
                button_index += 1


def restart_app():
    root.quit()
    root.destroy()
    main()

# GUI erstellen
def main():
    global root, buttons, indicators, indicator_ovals, content_frame, volume_slider
    root = tk.Tk()
    root.title("Jingleplayer")

    # Set the window icon
    icon_path = data_dir / "cc.ico"
    if (icon_path.exists()):
        root.iconbitmap(icon_path)

    # Set window size from settings
    root.geometry(f"{settings['window_size'][0]}x{settings['window_size'][1]}")

    # Create top frame for label and volume slider
    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", pady=5, padx=10)

    # Label
    label = tk.Label(top_frame, text="Young Crashers Jingleplayer", font=("Arial", 24))
    label.pack(side="left")

    # Volume slider
    volume_slider = tk.Scale(top_frame, from_=0, to=100, orient="horizontal", label="Lautstärke", command=set_volume)
    volume_slider.set(settings["volume"])  # Set volume from settings
    volume_slider.pack(side="right")

    buttons = []
    indicators = []
    indicator_ovals = []

    content_frame = tk.Frame(root)
    content_frame.pack(fill="both", expand=True, padx=10, pady=10)

    update_buttons()

    button_frame = tk.Frame(root)
    button_frame.pack(side="top", pady=5, anchor="n")  # Bind to top

    settings_button = tk.Button(button_frame, text="⚙ Einstellungen", font=("Arial", 12), bg="lightgray", command=open_settings_menu)
    settings_button.pack(side="left", padx=10)

    exit_button = tk.Button(button_frame, text="❌Beenden", font=("Arial", 12), bg="red", fg="white", command=root.quit)
    exit_button.pack(side="left", padx=10)

    print(f"Jingleplayer GUI gestartet. Einstellungen werden in {settings_file} gespeichert.")

    def periodic_check():
        check_sound_end()
        root.after(100, periodic_check)

    root.after(100, periodic_check)

    # Calculate the minimum width required for the window
    button_width = 10 * 10  # Button width in pixels (10 characters * 10 pixels per character)
    padding = 20 * 2  # Padding on each side
    min_width = max(buttons_per_row) * (button_width + padding)
    root.update_idletasks()
    root.minsize(min_width, root.winfo_height())

    root.bind("<Configure>", on_window_resize)  # Bind window resize event

    root.protocol("WM_DELETE_WINDOW", on_closing)  # Save settings on close
    root.mainloop()

def on_window_resize(event):
    save_settings()  # Save settings after window resize

def set_volume(val):
    volume = int(val) / 100
    for i in range(pygame.mixer.get_num_channels()):
        channel = pygame.mixer.Channel(i)
        channel.set_volume(volume)
    save_settings()  # Save settings after volume change

def on_closing():
    save_settings()
    root.destroy()

if __name__ == "__main__":
    main()
