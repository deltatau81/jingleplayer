import jingleplayer_logic
import jingleplayer_gui_tkinter # Hier wird die Tkinter GUI importiert. Für Kivy später `jingleplayer_gui_kivy` importieren

def main():
    # Initialisiere Einstellungen und globale Variablen in der Logik
    jingleplayer_logic.initialize_settings()

    # Starte die Tkinter GUI
    jingleplayer_gui_tkinter.main_gui()

if __name__ == "__main__":
    main()