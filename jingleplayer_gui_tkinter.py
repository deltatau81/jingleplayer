import tkinter as tk
from tkinter import simpledialog, messagebox, colorchooser, filedialog
import os
import shutil
from pathlib import Path

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
    indicator.config(width=12, height=12)
    indicator.delete("all")
    # Draw a filled circle: red if playing, green if not
    color = "red" if playing else "green"
    indicator.create_oval(2, 2, 10, 10, fill=color, outline="black", width=1)

def open_settings_menu_gui():
    open_settings_menu_gui.window = None  # Initialisierung außerhalb der Funktion
    # Verhindert mehrfaches Öffnen des Fensters
    if open_settings_menu_gui.window and open_settings_menu_gui.window.winfo_exists():  # GEÄNDERT: Vereinfachte Bedingung
        open_settings_menu_gui.window.lift()  # Fenster in den Vordergrund bringen
        return

    settings_window = tk.Toplevel(root)
    open_settings_menu_gui.window = settings_window
    settings_window.title("Einstellungen")

    create_fadeout_duration_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_buttons_per_row_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_default_folder_section_gui(settings_window)  # Auslagerung in separate Funktion
    create_settings_file_location_section_gui(settings_window)  # Auslagerung in separate Funktion

    # Hinweis-Label
    tk.Label(settings_window, text="Bei Änderungen des Layouts muss die Anwendung neu gestartet werden.", font=("Arial", 10), fg="red").pack(pady=10)

    # Button-Frame für Hilfe und Schließen
    button_frame = tk.Frame(settings_window)
    button_frame.pack(pady=10)
    
    help_button = tk.Button(button_frame, text="❓ Hilfe", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), command=show_help_gui)
    help_button.pack(side="left", padx=5)

    # Schließen-Button
    close_button = tk.Button(button_frame, text="Schließen", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), command=settings_window.destroy)
    close_button.pack(side="left", padx=5)

def create_fadeout_duration_section_gui(settings_window):
    """Erstellt den Bereich für die Fadeout-Dauer und Button-Höhe im Einstellungsmenü."""
    settings_frame = tk.Frame(settings_window)
    settings_frame.pack(fill="x", padx=20, pady=5)
    
    # Fadeout-Dauer
    tk.Label(settings_frame, text="Fadeout-Dauer (ms):", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    fadeout_duration_data = jingleplayer_logic.get_fadeout_duration_data()
    fadeout_entry = tk.Entry(settings_frame, width=5)
    fadeout_entry.insert(0, str(fadeout_duration_data))
    fadeout_entry.pack(side="left", padx=5)
    tk.Button(settings_frame, text="Aktualisieren", font=("Arial", 10), command=lambda: update_fadeout_duration_gui(fadeout_entry)).pack(side="left", padx=5)
    
    # Separator
    tk.Label(settings_frame, text=" | ").pack(side="left", padx=10)
    
    # Button-Höhe
    tk.Label(settings_frame, text="Button-Höhe:", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    button_height_data = jingleplayer_logic.get_button_height_data()
    button_height_entry = tk.Entry(settings_frame, width=5)
    button_height_entry.insert(0, str(button_height_data))
    button_height_entry.pack(side="left", padx=5)
    tk.Button(settings_frame, text="Aktualisieren", font=("Arial", 10), command=lambda: update_button_height_gui(button_height_entry)).pack(side="left", padx=5)

def create_button_height_section_gui(settings_window):
    """Diese Funktion wird nicht mehr benötigt, da sie in create_fadeout_duration_section_gui integriert wurde."""
    pass

def create_buttons_per_row_section_gui(settings_window):
    """Erstellt den Bereich für die Buttons-pro-Reihe-Einstellung im Einstellungsmenü."""
    buttons_per_row_entries = []  # Lokale Liste für Entry-Felder
    buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
    row_count = getattr(jingleplayer_logic, 'DEFAULT_BUTTON_ROW_COUNT', 5)
    if len(buttons_per_row_data) < row_count:
        buttons_per_row_data = list(buttons_per_row_data) + [0] * (row_count - len(buttons_per_row_data))
    for row in range(row_count):
        row_frame = tk.Frame(settings_window)
        row_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(row_frame, text=f"Buttons pro Reihe {row + 1} (0-10):", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
        entry = tk.Entry(row_frame, width=5)
        entry.insert(0, str(buttons_per_row_data[row]))
        entry.pack(side="left", padx=5)
        buttons_per_row_entries.append(entry)
        tk.Button(row_frame, text="Aktualisieren", font=("Arial", 10), command=lambda row=row: update_buttons_per_row_gui(row, buttons_per_row_entries)).pack(side="left", padx=5)

def create_default_folder_section_gui(settings_window):
    """Erstellt den Bereich für den Standard-Dateipfad im Einstellungsmenü."""
    folder_frame = tk.Frame(settings_window)
    folder_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(folder_frame, text="Standard-Dateipfad:", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    folder_entry = tk.Entry(folder_frame, width=50)
    folder_entry.insert(0, jingleplayer_logic.get_last_folder())
    folder_entry.pack(side="left", padx=5)
    
    def browse_folder():
        folder = filedialog.askdirectory(title="Wähle Standard-Dateipfad", initialdir=folder_entry.get(), parent=settings_window)
        if folder:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, folder)
    
    def update_default_folder():
        folder = folder_entry.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Fehler", "Ungültiger Pfad. Bitte überprüfen Sie die Eingabe.", parent=settings_window)
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, jingleplayer_logic.get_last_folder())
            return
        jingleplayer_logic.set_last_folder(folder)
        current_settings = jingleplayer_logic.get_current_settings()
        jingleplayer_logic.save_settings(current_settings)
        messagebox.showinfo("Gespeichert", f"Standard-Dateipfad wurde auf:\n{folder}\ngespeichert.", parent=settings_window)
    
    tk.Button(folder_frame, text="Durchsuchen", font=("Arial", 10), command=browse_folder).pack(side="left", padx=5)
    tk.Button(folder_frame, text="Speichern", font=("Arial", 10), command=update_default_folder).pack(side="left", padx=5)

def create_settings_file_location_section_gui(settings_window):
    """Erstellt den Bereich für den Speicherort der Einstellungsdatei im Einstellungsmenü."""
    settings_frame = tk.Frame(settings_window)
    settings_frame.pack(fill="x", padx=20, pady=5)
    tk.Label(settings_frame, text="Speicherort Einstellungsdatei:", font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS)).pack(side="left")
    settings_location_entry = tk.Entry(settings_frame, width=50)
    settings_location_entry.insert(0, str(jingleplayer_logic.settings_file))
    settings_location_entry.pack(side="left", padx=5)
    
    def browse_settings_folder():
        folder = filedialog.askdirectory(title="Wähle Speicherort für Einstellungsdatei", 
                                        initialdir=str(jingleplayer_logic.settings_file.parent), 
                                        parent=settings_window)
        if folder:
            settings_location_entry.delete(0, tk.END)
            settings_location_entry.insert(0, os.path.join(folder, "jingleplayer_settings.json"))
    
    def update_settings_location():
        new_path = settings_location_entry.get()
        if not new_path:
            messagebox.showerror("Fehler", "Pfad darf nicht leer sein.", parent=settings_window)
            return
        
        try:
            new_path = Path(new_path)
            # Sicherstelle, dass der Dateiname .json ist
            if new_path.suffix != ".json":
                new_path = new_path.with_suffix(".json")
            
            # Prüfe ob das Verzeichnis existiert
            new_dir = new_path.parent
            if not new_dir.exists():
                try:
                    new_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Fehler", f"Verzeichnis konnte nicht erstellt werden:\n{e}", parent=settings_window)
                    settings_location_entry.delete(0, tk.END)
                    settings_location_entry.insert(0, str(jingleplayer_logic.settings_file))
                    return
            
            # Kopiere alte Datei zum neuen Ort, falls sie existiert
            if jingleplayer_logic.settings_file.exists():
                try:
                    import shutil
                    shutil.copy2(str(jingleplayer_logic.settings_file), str(new_path))
                except Exception as e:
                    messagebox.showerror("Fehler", f"Einstellungen konnten nicht kopiert werden:\n{e}", parent=settings_window)
                    return
            
            # Aktualisiere den Pfad in der Logik
            jingleplayer_logic.settings_file = new_path
            
            # Speichere aktuelle Einstellungen am neuen Ort
            current_settings = jingleplayer_logic.get_current_settings()
            jingleplayer_logic.save_settings(current_settings)
            
            messagebox.showinfo("Gespeichert", f"Speicherort wurde auf:\n{new_path}\ngeändert.\n\nBitte starten Sie die Anwendung neu.", parent=settings_window)
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Ändern des Speicherorts:\n{e}", parent=settings_window)
            settings_location_entry.delete(0, tk.END)
            settings_location_entry.insert(0, str(jingleplayer_logic.settings_file))
    
    tk.Button(settings_frame, text="Durchsuchen", font=("Arial", 10), command=browse_settings_folder).pack(side="left", padx=5)
    tk.Button(settings_frame, text="Ändern", font=("Arial", 10), command=update_settings_location).pack(side="left", padx=5)

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
        # Save last folder
        try:
            jingleplayer_logic.set_last_folder(os.path.dirname(file_path))
        except Exception:
            pass
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
            # Anpassung: Elemente in den flachen Button-Listen an der richtigen Stelle einfügen/entfernen
            buttons_per_row_data = jingleplayer_logic.get_buttons_per_row_data()
            row_count = getattr(jingleplayer_logic, 'DEFAULT_BUTTON_ROW_COUNT', 5)
            if len(buttons_per_row_data) < row_count:
                buttons_per_row_data = list(buttons_per_row_data) + [0] * (row_count - len(buttons_per_row_data))

            old_count = buttons_per_row_data[row]
            new_count = value
            # Berechne flachen Startindex der betroffenen Reihe
            start_index = sum(buttons_per_row_data[:row])

            # Hole aktuelle flachen Listen (kopien)
            texts = jingleplayer_logic.get_button_texts_data()[:]
            colors = jingleplayer_logic.get_button_colors_data()[:]
            paths = jingleplayer_logic.get_jingle_paths_data()[:]

            if new_count > old_count:
                # Einfügen: neue Platzhalter am Ende der aktuellen Reihe einfügen
                delta = new_count - old_count
                insert_pos = start_index + old_count
                for _ in range(delta):
                    texts.insert(insert_pos, "")
                    colors.insert(insert_pos, "SystemButtonFace")
                    paths.insert(insert_pos, "")
                    insert_pos += 1
            elif new_count < old_count:
                # Entfernen: entferne überschüssige Einträge aus der aktuellen Reihe
                delta = old_count - new_count
                remove_start = start_index + new_count
                for _ in range(delta):
                    if remove_start < len(texts):
                        texts.pop(remove_start)
                    if remove_start < len(colors):
                        colors.pop(remove_start)
                    if remove_start < len(paths):
                        paths.pop(remove_start)

            # Setze die neue Anzahl in der per-row Liste
            buttons_per_row_data[row] = new_count

            # Aktualisiere die Einstellungen mit den modifizierten flachen Listen
            jingleplayer_logic.update_settings_data(
                texts,
                colors,
                paths,
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

    # Inline color picker (palette + preview)
    tk.Label(current_popup, text="Button-Farbe:").pack(pady=(8,2))
    color_frame = tk.Frame(current_popup)
    color_frame.pack(pady=2)
    # Preview
    color_preview = tk.Label(color_frame, text=" ", width=10, bg=jingleplayer_logic.get_button_colors_data()[index])
    color_preview.pack(side="left", padx=5)
    # Palette of common colors
    palette_colors = ["SystemButtonFace", "red", "green", "blue", "yellow", "orange", "purple", "gray", "white", "black"]
    palette_frame = tk.Frame(current_popup)
    palette_frame.pack(pady=2)
    def _set_color(c):
        color_preview.config(bg=c)
    for c in palette_colors:
        b = tk.Button(palette_frame, bg=c, width=2, command=lambda c=c: _set_color(c))
        b.pack(side="left", padx=2, pady=2)
    # Optional custom color (still opens native dialog if clicked)
    def pick_custom_color():
        col = colorchooser.askcolor(parent=current_popup)[1]
        if col:
            _set_color(col)
    tk.Button(current_popup, text="Custom...", command=pick_custom_color).pack(pady=(4,8))

    # Inline simple file browser: folder entry + file list (filter .mp3/.wav)
    tk.Label(current_popup, text="Jingle-Datei (wähle Datei aus Liste oder füge Pfad ein):").pack(pady=(6,2))
    file_frame = tk.Frame(current_popup)
    file_frame.pack(fill="both", expand=False, padx=8)
    file_entry = tk.Entry(file_frame, width=60)
    file_entry.pack(side="top", fill="x", padx=2, pady=4)

    # Folder navigation
    nav_frame = tk.Frame(file_frame)
    nav_frame.pack(fill="x", pady=2)
    # Determine initial folder from existing jingle path if available
    existing_paths = jingleplayer_logic.get_jingle_paths_data()
    existing_path = existing_paths[index] if index < len(existing_paths) else ""
    initial_folder = str(Path(existing_path).parent) if existing_path else jingleplayer_logic.get_last_folder()
    current_folder_var = tk.StringVar(value=initial_folder)
    folder_entry = tk.Entry(nav_frame, textvariable=current_folder_var, width=50)
    folder_entry.pack(side="left", padx=2)
    def refresh_file_list():
        folder = folder_entry.get() or str(Path.home())
        try:
            items = os.listdir(folder)
        except Exception:
            items = []
        files = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in ('.mp3', '.wav')]
        listbox.delete(0, tk.END)
        for f in sorted(files):
            listbox.insert(tk.END, f)
        current_folder_var.set(folder)
    def go_up():
        p = Path(folder_entry.get())
        if p.parent:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, str(p.parent))
            refresh_file_list()
    tk.Button(nav_frame, text="↑ Up", width=6, command=go_up).pack(side="left", padx=2)
    tk.Button(nav_frame, text="⟳ Refresh", width=8, command=refresh_file_list).pack(side="left", padx=2)

    listbox_frame = tk.Frame(file_frame)
    listbox_frame.pack(fill="both", expand=False, pady=4)
    listbox = tk.Listbox(listbox_frame, height=6, width=70)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)

    def on_listbox_select(evt):
        sel = listbox.curselection()
        if sel:
            filename = listbox.get(sel[0])
            folder = folder_entry.get() or str(Path.cwd())
            file_entry.delete(0, tk.END)
            file_entry.insert(0, os.path.join(folder, filename))
    listbox.bind('<<ListboxSelect>>', on_listbox_select)

    # Initialize file list
    refresh_file_list()
    # Prefill file entry with existing path and select in listbox if present
    if existing_path:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, existing_path)
        try:
            basename = os.path.basename(existing_path)
            # find in listbox
            for i in range(listbox.size()):
                if listbox.get(i) == basename:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(i)
                    listbox.see(i)
                    break
        except Exception:
            pass

    # Button frame for "Übernehmen" and "Abbrechen"
    button_frame = tk.Frame(current_popup)
    button_frame.pack(pady=10)

    # Save button
    save_button = tk.Button(button_frame, text="Übernehmen", bg="lightgray",
                            command=lambda: save_button_settings_gui(index, text_input.get(), color_preview.cget("bg"), file_entry.get()))
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
    # Save last folder from file_path if provided
    try:
        if file_path:
            jingleplayer_logic.set_last_folder(os.path.dirname(file_path))
    except Exception:
        pass
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

    row_count = getattr(jingleplayer_logic, 'DEFAULT_BUTTON_ROW_COUNT', 5)
    if len(buttons_per_row_data) < row_count:
        buttons_per_row_data = list(buttons_per_row_data) + [0] * (row_count - len(buttons_per_row_data))

    for row in range(row_count):
        print(f"Debug: Row loop - row: {row}, buttons_per_row_data[row]: {buttons_per_row_data[row]}")
        if buttons_per_row_data[row] > 0:
            row_frame = tk.Frame(content_frame)
            row_frame.pack(fill="x", padx=20, pady=5)
            for i in range(buttons_per_row_data[row]):
                print(f"Debug: Button loop - i: {i}, button_index: {button_index}")
                btn_text = button_texts_data[button_index] if button_index < len(button_texts_data) and button_texts_data[button_index] else f"Jingle {button_index + 1}"
                btn_color = button_colors_data[button_index] if button_index < len(button_colors_data) else "SystemButtonFace"

                # Custom button frame: colored, clickable, with label at top and slider inside
                btn_container = tk.Frame(row_frame, bg=btn_color, relief="raised", bd=2, highlightbackground="black", highlightthickness=1)
                btn_container.grid(row=0, column=i, sticky="nsew", padx=5, pady=5)
                row_frame.grid_columnconfigure(i, weight=1)

                # Button label at top
                btn_label = tk.Label(btn_container, text=btn_text, font=("Arial", jingleplayer_logic.FONT_SIZE_BUTTONS), bg=btn_color, anchor='n')
                # Set button height using configured value
                btn_label.pack(fill='x', pady=(2,0))
                btn_container.update_idletasks()
                # Height logic: set min height for container and label
                try:
                    pixel_height = int(button_height_data) * 20  # scale factor, tweak as needed
                    btn_container.config(height=pixel_height)
                    btn_label.config(height=int(button_height_data))
                except Exception:
                    pass

                # Slider inside button
                try:
                    vols = jingleplayer_logic.get_button_volumes_data()
                    initial_db = vols[button_index] if button_index < len(vols) else 0
                except Exception:
                    initial_db = 0
                # Place slider and dB label side by side in a subframe
                slider_row = tk.Frame(btn_container, bg=btn_color)
                slider_row.pack(fill='x', padx=5, pady=(0,2))
                vol_slider = tk.Scale(slider_row, from_=-10, to=10, orient="horizontal", resolution=1, showvalue=False, bg=btn_color, troughcolor="white", highlightthickness=0, sliderlength=10, width=8)
                vol_slider.set(initial_db)
                vol_slider.pack(side="left", fill='x', expand=True)
                # Only slider, no dB value label
                def slider_callback(val, idx=button_index):
                    # Snap to 0 if near 0 (±1 dB)
                    try:
                        v = int(float(val))
                    except Exception:
                        v = 0
                    if -1 < v < 1:
                        v = 0
                        vol_slider.set(0)
                    on_button_volume_change_gui(idx+1, v)
                vol_slider.config(command=slider_callback)
                # Size the slider to match the button width
                try:
                    root.update_idletasks()
                    btn_pixel_width = btn_container.winfo_reqwidth() if hasattr(btn_container, 'winfo_reqwidth') else 100
                    vol_slider.config(length=max(40, int(btn_pixel_width)-40))
                except Exception:
                    pass

                # Indicator (play/pause) to the right of the slider
                indicator = tk.Canvas(btn_container, width=12, height=12, bg=btn_color, highlightthickness=0)
                indicator.place(relx=1.0, rely=0.0, anchor="ne", x=-2, y=2)
                indicators.append(indicator)
                indicator_canvases.append(indicator)
                # Draw initial indicator state (not playing)
                update_indicator_gui(button_index + 1, False)

                # Make the whole button frame clickable (play/pause)
                def play_callback(event, idx=button_index):
                    on_button_click_gui(idx+1)
                btn_container.bind("<Button-1>", play_callback)
                btn_label.bind("<Button-1>", play_callback)
                vol_slider.bind("<Button-3>", lambda event, i=button_index: on_button_right_click_gui(event, i))
                btn_label.bind("<Button-3>", lambda event, i=button_index: on_button_right_click_gui(event, i))
                btn_container.bind("<Button-3>", lambda event, i=button_index: on_button_right_click_gui(event, i))
                buttons.append(btn_container)
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

def on_button_volume_change_gui(index, val):
    """GUI callback when a per-button dB slider changes. Index is 1-based."""
    try:
        db_val = int(float(val))
    except Exception:
        return
    jingleplayer_logic.set_button_volume(index, db_val)
    # Save settings after change
    current_settings = jingleplayer_logic.get_current_settings()
    jingleplayer_logic.save_settings(current_settings)

def show_help_gui():
    """Zeigt die Hilfedatei in einem neuen Fenster an."""
    help_file = Path(__file__).parent / "HELP.md"
    
    # Versuche, die Hilfedatei zu lesen
    try:
        if help_file.exists():
            with open(help_file, "r", encoding="utf-8") as f:
                help_text = f.read()
        else:
            help_text = "Hilfedatei nicht gefunden.\n\nDatei: HELP.md"
    except Exception as e:
        help_text = f"Fehler beim Laden der Hilfedatei:\n{e}"
    
    # Erstelle Hilfe-Fenster
    help_window = tk.Toplevel(root)
    help_window.title("Jingleplayer - Hilfe")
    help_window.geometry("700x600")
    
    # Scrollbarer Text-Widget
    scrollbar = tk.Scrollbar(help_window)
    scrollbar.pack(side="right", fill="y")
    
    text_widget = tk.Text(help_window, wrap="word", yscrollcommand=scrollbar.set)
    text_widget.pack(fill="both", expand=True, padx=10, pady=10)
    scrollbar.config(command=text_widget.yview)
    
    # Füge Hilftext ein
    text_widget.insert("1.0", help_text)
    text_widget.config(state="disabled")  # Schreibgeschützt
    
    # Schließen-Button
    close_btn = tk.Button(help_window, text="Schließen", command=help_window.destroy)
    close_btn.pack(pady=10)

def on_closing_gui():
    current_settings = jingleplayer_logic.get_current_settings()  # Aktuelle Einstellungen holen
    jingleplayer_logic.save_settings(current_settings)  # Einstellungen speichern
    root.destroy()

if __name__ == "__main__":
    main_gui()