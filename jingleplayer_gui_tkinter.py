import tkinter as tk
from tkinter import simpledialog, messagebox, colorchooser, filedialog

import jingleplayer_logic  # Importiert die Logik-Datei!

# Globale GUI-Variablen (tkinter-spezifisch)
root = None
buttons = []
indicators = []
indicator_canvases = []
content_frame = None
volume_slider = None
current_popup = None
periodic_check_id = None  # Global variable to store the after ID for periodic_check_gui # NEU: Globale Variable für after ID

def periodic_check_gui(): # GLOBALE DEFINITION, VOR main_gui()
    global root, indicators, periodic_check_id
    if root is None or not indicators:
        return
    indicator_updates = jingleplayer_logic.check_sound_end()
    for update_data in indicator_updates:
        update_indicator_gui(update_data["index"], update_data["playing"])
    periodic_check_id = root.after(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS, periodic_check_gui)

def main_gui():
    global root, buttons, indicators, indicator_canvases, content_frame, volume_slider, periodic_check_id

    # Settings initialisieren und laden
    jingleplayer_logic.initialize_settings()

    root = tk.Tk()
    root.title("Jingleplayer")

    # Set the window icon
    icon_path = jingleplayer_logic.data_dir / "cc.ico"
    if (icon_path.exists()):
        root.iconbitmap(str(icon_path))  # Pfad muss String sein für iconbitmap

    # Create top frame for label, volume slider, and buttons  <-- TOP_FRAME UMFASST JETZT AUCH BUTTONS
    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", pady=5, padx=10)

    # Label
    label = tk.Label(top_frame, text="Young Crashers Jingleplayer", font=("Arial", jingleplayer_logic.FONT_SIZE_TITLE))
    label.pack(side="left")  # Label links

    # Volume slider
    volume_slider = tk.Scale(top_frame, from_=0, to=100, orient="horizontal", label="Lautstärke", command=set_volume_gui)
    volume_data = jingleplayer_logic.get_volume_data()
    if isinstance(volume_data, dict) and 'startup_volume' in volume_data:
        volume_slider.set(volume_data['startup_volume'])
    else:
        volume_slider.set(volume_data)
    volume_slider.pack(side="right")  # Slider rechts

    button_frame = tk.Frame(top_frame)  # Frame für untere Buttons erstellen, JETZT IM TOP_FRAME
    button_frame.pack(side="right", padx=10)  # Button Frame rechts im top_frame positionieren

    settings_button = tk.Button(button_frame, text="⚙ Einstellungen", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), bg="lightgray", command=open_settings_menu_gui)
    settings_button.pack(side="left", padx=10)

    exit_button = tk.Button(button_frame, text="❌Beenden", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), bg="red", fg="white", command=root.quit)
    exit_button.pack(side="left", padx=10)

    button_frame_height = button_frame.winfo_reqheight()  # Höhe des button_frame ermitteln, nachdem er gepackt wurde

    # Set window size from settings
    buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
    active_rows = sum(1 for row_count in buttons_per_row_data if row_count > 0)  # Anzahl der Reihen mit Buttons
    initial_height = jingleplayer_logic.DEFAULT_WINDOW_HEIGHT  # Standardhöhe
    if active_rows > 0:
        initial_height = (active_rows * 100)  # Dynamische Höhe basierend auf Reihenanzahl (Beispielwerte)
    initial_height += button_frame_height  # HIER NEU: Höhe des button_frame hinzufügen

    # Fix: Use .get() with fallback for window_size
    window_size = jingleplayer_logic.settings.get('window_size', [jingleplayer_logic.DEFAULT_WINDOW_WIDTH, initial_height])
    root.geometry(f"{window_size[0]}x{initial_height}")  # Dynamische Höhe verwenden


    buttons = []
    indicators = []
    indicator_canvases = []

    content_frame = tk.Frame(root)
    content_frame.pack(fill="both", expand=True, padx=10, pady=10)

    update_buttons_gui(initial=True)

    print(f"Jingleplayer GUI gestartet. Einstellungen werden in {jingleplayer_logic.settings_file} gespeichert.")

    def periodic_check_gui():
        global periodic_check_id
        indicator_updates = jingleplayer_logic.check_sound_end()
        for update_data in indicator_updates:
            update_indicator_gui(update_data["index"], update_data["playing"])
        periodic_check_id = root.after(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS, periodic_check_gui)
    periodic_check_id = root.after(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS, periodic_check_gui) # NEU: Speichere after ID

    # Calculate the minimum width required for the window
    button_width = 10 * 10  # Button width in pixels (10 characters * 10 pixels per character)
    padding = 20 * 2  # Padding on each Seite
    buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
    total_buttons_in_row = sum(buttons_per_row_data)  # Summe der Buttons pro Reihe
    if total_buttons_in_row > 0:  # Vermeide Fehler, wenn alle Reihen entfernt wurden
        max_buttons_per_row = max(buttons_per_row_data)  # Max Buttons pro Reihe für die Berechnung der Breite pro Button
        min_width = max_buttons_per_row * (button_width + padding)
    else:
        min_width = jingleplayer_logic.DEFAULT_WINDOW_WIDTH  # Fallback-Breite, wenn keine Buttons vorhanden sind
    root.update_idletasks()
    root.minsize(min_width, root.winfo_height())
    root.minsize(width=root.winfo_reqwidth(), height=root.winfo_reqheight())  # Setze minimale Höhe auch hier, falls nötig


    root.bind("<Configure>", on_window_resize_gui)  # Bind window resize event

    root.protocol("WM_DELETE_WINDOW", on_closing_gui)  # Save settings on close
    root.mainloop()

def update_indicator_gui(index, playing):
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

def open_settings_menu_gui():
    open_settings_menu_gui.window = None  # Initialisierung außerhalb der Funktion
    # Verhindert mehrfaches Öffnen des Fensters
    if open_settings_menu_gui.window and open_settings_menu_gui.window.winfo_exists():  # GEÄNDERT: Vereinfachte Bedingung
        open_settings_menu_gui.window.lift()  # Fenster in den Vordergrund bringen
        return

    settings_window = tk.Toplevel(root)
    open_settings_menu_gui.window = settings_window
    settings_window.title("Einstellungen")

    create_button_edit_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_fadeout_duration_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_button_height_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_buttons_per_row_section_gui(settings_window)  # Auslagerung in separate Funktion

    # Hinweis-Label
    tk.Label(settings_window, text="Bei Änderungen des Layouts muss die Anwendung neu gestartet werden.", font=("Arial", 10), fg="red").pack(pady=10)

    # Schließen-Button
    close_button = tk.Button(settings_window, text="Schließen", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), command=settings_window.destroy)
    close_button.pack(pady=10)

def create_button_edit_section_gui(settings_window):
    """Erstellt den Bereich für die Button-Bearbeitung im Einstellungsmenü."""
    dropdown_frame = tk.Frame(settings_window)
    dropdown_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(dropdown_frame, text="Button bearbeiten:", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    button_texts_data = jingleplayer_logic.get_button_texts_data()
    button_var = tk.StringVar(dropdown_frame)
    # Fix: Avoid IndexError if list is empty
    if button_texts_data:
        button_var.set(button_texts_data[0])  # Default value
        button_menu = tk.OptionMenu(dropdown_frame, button_var, *button_texts_data)
    else:
        button_var.set("Kein Button vorhanden")
        button_menu = tk.OptionMenu(dropdown_frame, button_var, "Kein Button vorhanden")
        button_menu.config(state="disabled")
    button_menu.pack(side="left", padx=5)

    def edit_selected_button_gui():
        if not button_texts_data:
            return
        index = button_texts_data.index(button_var.get()) + 1
        change_button_text_gui(settings_window, index)  # Übergabe settings_window für messagebox
        change_button_color_gui(settings_window, index)  # Übergabe settings_window für messagebox
        assign_jingle_file_gui(settings_window, index)  # Übergabe settings_window für messagebox

    tk.Button(dropdown_frame, text="Bearbeiten", font=("Arial", 10), command=edit_selected_button_gui, state="normal" if button_texts_data else "disabled").pack(side="left", padx=5)

def create_fadeout_duration_section_gui(settings_window):
    """Erstellt den Bereich für die Fadeout-Dauer-Einstellung im Einstellungsmenü."""
    fadeout_frame = tk.Frame(settings_window)
    fadeout_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(fadeout_frame, text="Fadeout-Dauer (ms):", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    fadeout_duration_data = jingleplayer_logic.get_fadeout_duration_data()
    fadeout_entry = tk.Entry(fadeout_frame, width=5)
    fadeout_entry.insert(0, str(fadeout_duration_data))
    fadeout_entry.pack(side="left", padx=5)
    tk.Button(fadeout_frame, text="Aktualisieren", font=("Arial", 10), command=lambda: update_fadeout_duration_gui(fadeout_entry)).pack(side="left", padx=5)

def create_button_height_section_gui(settings_window):
    """Erstellt den Bereich für die Button-Höhen-Einstellung im Einstellungsmenü."""
    button_height_frame = tk.Frame(settings_window)
    button_height_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(button_height_frame, text="Button-Höhe:", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    button_height_data = jingleplayer_logic.get_button_height_data()
    button_height_entry = tk.Entry(button_height_frame, width=5)
    button_height_entry.insert(0, str(button_height_data))
    button_height_entry.pack(side="left", padx=5)
    tk.Button(button_height_frame, text="Aktualisieren", font=("Arial", 10), command=lambda: update_button_height_gui(button_height_entry)).pack(side="left", padx=5)

def create_buttons_per_row_section_gui(settings_window):
    """Erstellt den Bereich für die Buttons-pro-Reihe-Einstellung im Einstellungsmenü."""
    buttons_per_row_entries = []  # Lokale Liste für Entry-Felder
    buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
    # Fix: Ensure always 4 elements
    if len(buttons_per_row_data) < 4:
        buttons_per_row_data = list(buttons_per_row_data) + [0] * (4 - len(buttons_per_row_data))
    for row in range(4):
        row_frame = tk.Frame(settings_window)
        row_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(row_frame, text=f"Buttons pro Reihe {row + 1} (0-10):", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
        entry = tk.Entry(row_frame, width=5)
        entry.insert(0, str(buttons_per_row_data[row]))
        entry.pack(side="left", padx=5)
        buttons_per_row_entries.append(entry)
        tk.Button(row_frame, text="Aktualisieren", font=("Arial", 10), command=lambda row=row: update_buttons_per_row_gui(row, buttons_per_row_entries)).pack(side="left", padx=5)

def change_button_color_gui(settings_window, index):  # settings_window übergeben für messagebox
    color_code = colorchooser.askcolor(title=f"Farbe für Jingle {index} wählen", parent=settings_window)[1]  # parent hinzugefügt
    if color_code:
        button_colors_data = jingleplayer_logic.get_button_colors_data()
        button_colors_data[index - 1] = color_code
        update_button_in_gui(index - 1, color=color_code)  # Button Farbe direkt in GUI aktualisieren
        current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
        jingleplayer_logic.update_settings_data(jingleplayer_logic.button_texts, button_colors_data, jingleplayer_logic.jingle_paths, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, jingleplayer_logic.button_height, current_settings["window_size"], current_settings["volume"])  # Einstellungen in Logik aktualisieren
        jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern

def assign_jingle_file_gui(settings_window, index):  # settings_window übergeben für messagebox
    file_path = filedialog.askopenfilename(title=f"Jingle für Button {index} wählen", filetypes=[("Audio Dateien", "*.mp3;*.wav")], parent=settings_window)  # parent hinzugefügt
    jingle_paths_data = jingleplayer_logic.get_jingle_paths_data() # HIER INITIALISIEREN, VOR DER IF-BEDINGUNG
    if file_path:
        jingle_paths_data[index - 1] = file_path
        current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
        jingleplayer_logic.update_settings_data(jingleplayer_logic.button_texts, jingleplayer_logic.button_colors, jingle_paths_data, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, jingleplayer_logic.button_height, current_settings["window_size"], current_settings["volume"])  # Einstellungen in Logik aktualisieren
        jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern

def change_button_text_gui(settings_window, index):  # settings_window übergeben für messagebox
    new_text = simpledialog.askstring("Button-Text ändern", f"Neuer Text für Button {index}:", initialvalue=jingleplayer_logic.button_texts[index - 1], parent=settings_window)  # parent hinzugefügt
    jingle_paths_data = jingleplayer_logic.get_jingle_paths_data() # HIER INITIALISIEREN, VOR DER IF-BEDINGUNG
    if new_text:
        button_texts_data = jingleplayer_logic.get_button_texts_data()
        button_texts_data[index - 1] = new_text
        update_button_in_gui(index - 1, text=new_text)  # Button Text direkt in GUI aktualisieren
        current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
        jingleplayer_logic.update_settings_data(button_texts_data, jingleplayer_logic.button_colors, jingle_paths_data, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, jingleplayer_logic.button_height, current_settings["window_size"], current_settings["volume"])  # Einstellungen in Logik aktualisieren
        jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern

def update_fadeout_duration_gui(fadeout_entry):
    try:  # Validierung der Eingabe
        fadeout_duration_value = int(fadeout_entry.get())
        if fadeout_duration_value < 0:
            messagebox.showerror("Fehler", "Fadeout-Dauer muss eine positive Zahl sein.", parent=open_settings_menu_gui.window)  # parent hinzugefügt
            fadeout_entry.delete(0, tk.END)
            fadeout_entry.insert(0, str(jingleplayer_logic.fadeout_duration))  # Alten Wert wiederherstellen
            return
        current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
        jingleplayer_logic.update_settings_data(jingleplayer_logic.button_texts, jingleplayer_logic.button_colors, jingleplayer_logic.jingle_paths, jingleplayer_logic.buttons_per_row, fadeout_duration_value, jingleplayer_logic.button_height, current_settings["window_size"], current_settings["volume"])  # Einstellungen in Logik aktualisieren
        jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern
        messagebox.showinfo("Gespeichert", "Fadeout-Dauer wurde aktualisiert.", parent=open_settings_menu_gui.window)  # Feedback für Speichern, parent hinzugefügt
    except ValueError:
        messagebox.showerror("Fehler", "Ungültige Eingabe. Bitte geben Sie eine Zahl ein.", parent=open_settings_menu_gui.window)  # parent hinzugefügt
        fadeout_entry.delete(0, tk.END)
        fadeout_entry.insert(0, str(jingleplayer_logic.fadeout_duration))  # Alten Wert wiederherstellen

def update_button_height_gui(button_height_entry):
    try:  # Validierung der Eingabe
        button_height_value = int(button_height_entry.get())
        if button_height_value <= 0:
            messagebox.showerror("Fehler", "Button-Höhe muss größer als 0 sein.", parent=open_settings_menu_gui.window)  # parent hinzugefügt
            button_height_entry.delete(0, tk.END)
            button_height_entry.insert(0, str(jingleplayer_logic.button_height))  # Alten Wert wiederherstellen
            return
        current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
        jingleplayer_logic.update_settings_data(jingleplayer_logic.button_texts, jingleplayer_logic.button_colors, jingleplayer_logic.jingle_paths, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, button_height_value, current_settings["window_size"], current_settings["volume"])  # Einstellungen in Logik aktualisieren
        jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern
        update_buttons_gui()  # GUI Buttons neu erstellen
        confirm_restart_gui()  # Neustart-Popup aufrufen  <--- HIER GEÄNDERT, Info-Popup entfernt
    except ValueError:
        messagebox.showerror("Fehler", "Ungültige Eingabe. Bitte geben Sie eine Zahl ein.", parent=open_settings_menu_gui.window)  # parent hinzugefügt
        button_height_entry.delete(0, tk.END)
        button_height_entry.insert(0, str(jingleplayer_logic.button_height))  # Alten Wert wiederherstellen

def update_buttons_per_row_gui(row, buttons_per_row_entries):
    try:
        value = int(buttons_per_row_entries[row].get())
        if value < 0 or value > jingleplayer_logic.DEFAULT_BUTTONS_PER_ROW_COUNT:
            messagebox.showerror("Fehler", f"Die Anzahl der Buttons pro Reihe muss zwischen 0 und {jingleplayer_logic.DEFAULT_BUTTON_COUNT} liegen.", parent=open_settings_menu_gui.window)
            buttons_per_row_entries[row].delete(0, tk.END)
            buttons_per_row_entries[row].insert(0, str(jingleplayer_logic.buttons_per_row[row]))
        else:
            current_settings = jingleplayer_logic.get_current_settings()
            buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
            if len(buttons_per_row_data) < 4:
                buttons_per_row_data = list(buttons_per_row_data) + [0] * (4 - len(buttons_per_row_data))
            buttons_per_row_data[row] = value
            jingleplayer_logic.update_settings_data(
                jingleplayer_logic.button_texts,
                jingleplayer_logic.button_colors,
                jingleplayer_logic.jingle_paths,
                buttons_per_row_data,
                jingleplayer_logic.fadeout_duration,
                jingleplayer_logic.button_height,
                current_settings["window_size"],
                current_settings["volume"]
            )
            # Fix: get updated settings after update_settings_data
            current_settings = jingleplayer_logic.get_current_settings()
            jingleplayer_logic.save_settings(current_settings)
            update_buttons_gui()
            confirm_restart_gui()
    except ValueError:
        messagebox.showerror("Fehler", "Ungültige Eingabe. Bitte geben Sie eine Zahl ein.", parent=open_settings_menu_gui.window)
        buttons_per_row_entries[row].delete(0, tk.END)
        buttons_per_row_entries[row].insert(0, str(jingleplayer_logic.buttons_per_row[row]))  # Alten Wert wiederherstellen

def confirm_restart_gui():
    """Zeigt ein Bestätigungs-Popup für den Neustart an."""
    restart_window = tk.Toplevel(root)
    restart_window.title("Neustart erforderlich")
    restart_window.attributes("-topmost", True)  # Popup immer im Vordergrund

    tk.Label(restart_window, text="Layout-Änderungen erfordern einen Neustart.\nJetzt neu starten?", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), padx=20, pady=10).pack()

    def restart_application():
        """Startet die Anwendung neu."""
        jingleplayer_logic.save_settings(jingleplayer_logic.get_current_settings())  # Einstellungen speichern
        restart_window.destroy()  # Popup schließen
        root.destroy()  # Hauptfenster schließen
        import jingleplayer_app  # App-Modul importieren (hier innerhalb der Funktion, um Zirkelbezüge zu vermeiden)
        jingleplayer_app.main()  # Hauptfunktion neu starten

    def cancel_restart():
        """Bricht den Neustart ab und schließt das Popup."""
        restart_window.destroy()

    yes_button = tk.Button(restart_window, text="Ja, neu starten", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), command=restart_application, padx=10, pady=5)
    yes_button.pack(side="left", padx=10, pady=10)

    no_button = tk.Button(restart_window, text="Nein", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), command=cancel_restart, padx=10, pady=5)
    no_button.pack(side="right", padx=10, pady=10)

    restart_window.transient(root)  # Popup an Hauptfenster binden
    restart_window.grab_set()  # Fokus auf Popup setzen
    root.wait_window(restart_window)  # Warten, bis Popup geschlossen wird

def on_button_click_gui(index):
    jingle_path = jingleplayer_logic.get_jingle_paths_data()[index - 1]
    fadeout_duration_data = jingleplayer_logic.get_fadeout_duration_data()
    play_result = jingleplayer_logic.play_jingle(index, jingle_path, fadeout_duration_data)  # Logik-Funktion aufrufen
    if play_result and play_result.get("error"):  # Fehlerbehandlung basierend auf Rückmeldung der Logik
        messagebox.showerror("Fehler", play_result["error"], parent=root)
    elif play_result and play_result.get("indicator_update"):  # Indikator-Update basierend auf Rückmeldung der Logik
        update_indicator_gui(play_result["indicator_update"]["index"], play_result["indicator_update"]["playing"])


def on_button_stop_click_gui(index):
    fadeout_duration_data = jingleplayer_logic.get_fadeout_duration_data()
    stop_result = jingleplayer_logic.stop_jingle(index, fadeout_duration_data)  # Logik-Funktion aufrufen
    if stop_result and stop_result.get("indicator_update"):  # Indikator-Update basierend auf Rückmeldung der Logik
        update_indicator_gui(stop_result["indicator_update"]["index"], stop_result["indicator_update"]["playing"])

def on_button_right_click_gui(event, index):
    if event.num == 3:  # Right-click
        open_button_settings_gui(index)

def open_button_settings_gui(index):
    global current_popup
    if current_popup is not None:
        current_popup.destroy()
    current_popup = tk.Toplevel(root)
    current_popup.title(f"Button {index + 1} Einstellungen")
    current_popup.attributes("-topmost", True)  # Ensure the popup is always on top

    # Text input for button text
    tk.Label(current_popup, text="Button-Text:").pack(pady=5)
    text_input = tk.Entry(current_popup)
    button_texts_data = jingleplayer_logic.get_button_texts_data()
    text_input.insert(0, button_texts_data[index])
    text_input.pack(pady=5)

    # Color chooser for button color
    tk.Label(current_popup, text="Button-Farbe:").pack(pady=5)
    color_button = tk.Button(current_popup, text="Farbe wählen", command=lambda: choose_color_gui(index, color_button))
    color_button.pack(pady=5)

    # File chooser for button file
    tk.Label(current_popup, text="Jingle-Datei:").pack(pady=5)
    file_button = tk.Button(current_popup, text="Datei wählen", command=lambda: choose_file_gui(index, file_button))
    file_button.pack(pady=5)

    # Button frame for "Übernehmen" and "Abbrechen"
    button_frame = tk.Frame(current_popup)
    button_frame.pack(pady=10)

    # Save button
    save_button = tk.Button(button_frame, text="Übernehmen", bg="lightgray", command=lambda: save_button_settings_gui(index, text_input.get(), color_button.cget("bg"), file_button.cget("text")))
    save_button.pack(side="left", padx=5)

    # Close button
    close_button = tk.Button(button_frame, text="❌Abbrechen", bg="red", fg="white", command=current_popup.destroy)
    close_button.pack(side="left", padx=5)

def choose_color_gui(index, button):
    color_code = colorchooser.askcolor(title=f"Farbe für Jingle {index + 1} wählen")[1]
    if color_code:
        button.config(bg=color_code)

def choose_file_gui(index, button):
    file_path = filedialog.askopenfilename(title=f"Jingle für Button {index + 1} wählen", filetypes=[("Audio Dateien", "*.mp3;*.wav")])
    if file_path:
        button.config(text=file_path)

def save_button_settings_gui(index, text, color, file_path):
    button_texts_data = jingleplayer_logic.get_button_texts_data()
    button_colors_data = jingleplayer_logic.get_button_colors_data()
    jingle_paths_data = jingleplayer_logic.get_jingle_paths_data()

    button_texts_data[index] = text
    button_colors_data[index] = color
    jingle_paths_data[index] = file_path
    update_button_in_gui(index, text=text, color=color)  # Button direkt in GUI aktualisieren
    print(f"Button {index + 1} gespeichert: Text={text}, Farbe={color}, Datei={file_path}")
    current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
    window_size = current_settings["window_size"]
    volume = current_settings["volume"]
    jingleplayer_logic.update_settings_data(button_texts_data, button_colors_data, jingle_paths_data, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, jingleplayer_logic.button_height, window_size, volume)
    jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern
    if current_popup is not None:
        current_popup.destroy()  # Close the popup after saving

def update_buttons_gui(event=None, initial=False):
    global buttons, indicators, indicator_canvases, content_frame, prev_buttons_per_row_data, periodic_check_id
    if not hasattr(update_buttons_gui, 'prev_buttons_per_row_data'):
        update_buttons_gui.prev_buttons_per_row_data = list(jingleplayer_logic.get_buttons_per_row_data())

    prev_buttons_per_row_data = update_buttons_gui.prev_buttons_per_row_data

    # Fix: Remove any scheduled periodic_check_gui before rebuilding, and set to None
    global periodic_check_id  # <-- move global to the top of the function, before any use!
    if periodic_check_id is not None:
        try:
            root.after_cancel(periodic_check_id)
        except Exception:
            pass
        periodic_check_id = None

    for widget in content_frame.winfo_children():
        widget.destroy()
    for button in buttons:
        button.destroy()
    buttons.clear()
    for indicator in indicators:
        indicator.destroy()
    indicators.clear()
    indicator_canvases.clear()

    row_frame = None
    button_index = 0
    button_texts_data, button_colors_data = jingleplayer_logic.get_initial_button_data()
    buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
    button_height_data = jingleplayer_logic.get_button_height_data()

    if len(buttons_per_row_data) < 4:
        buttons_per_row_data = list(buttons_per_row_data) + [0] * (4 - len(buttons_per_row_data))

    for row in range(4):
        print(f"Debug: Row loop - row: {row}, buttons_per_row_data[row]: {buttons_per_row_data[row]}")
        if buttons_per_row_data[row] > 0:
            row_frame = tk.Frame(content_frame)
            row_frame.pack(fill="x", padx=20, pady=5)
            for i in range(buttons_per_row_data[row]):
                print(f"Debug: Button loop - i: {i}, button_index: {button_index}")
                # Do NOT modify button_texts_data here at all!
                btn_text = button_texts_data[button_index] if button_index < len(button_texts_data) and button_texts_data[button_index] else f"Jingle {button_index + 1}"
                btn_color = button_colors_data[button_index] if button_index < len(button_colors_data) else "SystemButtonFace"

                button = tk.Button(row_frame, text=btn_text,
                                   font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS),
                                   bg=btn_color,
                                   width=10, height=button_height_data,
                                   command=lambda i=button_index: on_button_click_gui(i + 1))
                button.grid(row=0, column=i, sticky="ew", padx=5, pady=5)
                button.bind("<Button-3>", lambda event, i=button_index: on_button_right_click_gui(event, i))
                row_frame.grid_columnconfigure(i, weight=1)

                buttons.append(button)

                indicator_frame = tk.Frame(row_frame)
                indicator_frame.grid(row=1, column=i, sticky="ew")

                indicator = tk.Canvas(indicator_frame, width=40, height=40)
                indicator.create_rectangle(10, 10, 16, 30, fill="green")
                indicator.create_rectangle(20, 10, 26, 30, fill="green")
                indicator.pack(side="left")
                indicators.append(indicator)
                indicator_canvases.append(indicator)

                tk.Label(indicator_frame, text=str(button_index + 1), font=("Arial", 8)).pack(side="left")
                button_index += 1

    # Nur speichern, wenn nicht initial
    if not initial:
        update_buttons_gui.prev_buttons_per_row_data = list(buttons_per_row_data)
        periodic_check_id = root.after(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS, periodic_check_gui)
    print(f"Debug: End update_buttons_gui")
def update_button_in_gui(index, text=None, color=None):
    if text is not None:
        buttons[index].config(text=text)
    if color is not None:
        buttons[index].config(bg=color)


def on_window_resize_gui(event):
    current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
    window_size = [root.winfo_width(), root.winfo_height()]
    jingleplayer_logic.update_settings_data(jingleplayer_logic.button_texts, jingleplayer_logic.button_colors, jingleplayer_logic.jingle_paths, jingleplayer_logic.buttons_per_row, jingleplayer_logic.fadeout_duration, jingleplayer_logic.button_height, window_size, current_settings["volume"])  # Einstellungen in Logik aktualisieren
    jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern

def set_volume_gui(val):
    volume_percent = int(val)
    jingleplayer_logic.set_volume_logic(volume_percent)  # Logik Funktion aufrufen, um Lautstärke zu setzen und zu speichern
    current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
    jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern

def on_closing_gui():
    current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
    jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern
    root.destroy()

if __name__ == "__main__":
    main_gui()