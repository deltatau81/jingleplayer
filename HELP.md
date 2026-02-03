# Jingleplayer - Benutzerhandbuch

## Übersicht
Jingleplayer ist eine Audio-Anwendung zum Abspielen von Jingles (Audiodateien) über Buttons. Sie können Buttons mit Audiodateien verknüpfen, deren Farbe und Text anpassen sowie verschiedene Einstellungen konfigurieren.

---

## Hauptfenster

### Button-Reihen
- Die Anwendung zeigt bis zu 5 Reihen mit bis zu 10 Buttons pro Reihe.
- Jeder Button kann mit einer MP3- oder WAV-Datei verknüpft werden.
- Ein grünes Indikator-Symbol zeigt den Status: **Grün (Pause)** = inaktiv, **Rot (Play)** = läuft ab.

### Button bedienen
- **Linksklick**: Spielt den zugeordneten Jingle ab oder stoppt ihn, wenn bereits abspielend.
- **Rechtsklick**: Öffnet ein Einstellungs-Popup zum Bearbeiten von Text, Farbe und Dateipfad.

### Lautstärke-Slider
- Oben rechts im Fenster: Regelt die Wiedergabelautstärke (0-100%).
- Die Einstellung wird automatisch gespeichert.

### Schaltflächen
- **⚙ Einstellungen**: Öffnet das Einstellungsmenü (siehe unten).
- **❌ Beenden**: Schließt die Anwendung (speichert alle Einstellungen automatisch).

---

## Einstellungsmenü

### Fadeout-Dauer & Button-Höhe
- **Fadeout-Dauer (ms)**: Zeit für das sanfte Ausblenden beim Stoppen (Standard: 1000 ms).
- **Button-Höhe**: Höhe der Button-Elemente in der GUI (Standard: 2).
- Änderungen erfordern einen Neustart der Anwendung.

### Buttons pro Reihe
- Für jede der 5 Reihen: Geben Sie ein, wie viele Buttons in der Reihe angezeigt werden (0-10).
- "Aktualisieren"-Button speichert und aktualisiert die GUI.
- **Wichtig**: Neue Buttons werden in der aktuellen Reihe *vor* den Buttons der nächsten Reihe eingefügt, nicht am Ende.

### Standard-Dateipfad
- **Durchsuchen**: Wählt den Standard-Ordner für Dateiauswahl beim Bearbeiten von Buttons.
- **Speichern**: Speichert den Pfad in den Einstellungen.
- Beim nächsten Öffnen eines Button-Einstellungs-Dialogs wird dieser Ordner als Standard verwendet.

### Speicherort Einstellungsdatei
- Zeigt den aktuellen Pfad der `jingleplayer_settings.json`.
- **Durchsuchen**: Wählt ein neues Verzeichnis.
- **Ändern**: Verschiebt die Einstellungsdatei zum neuen Ort und speichert sie dort. **Erfordert Neustart.**

### Hilfe
- Zeigt dieses Benutzerhandbuch in einem separaten Fenster an.

---

## Button-Einstellungen (Rechtsklick)

### Text
- **Eingabefeld**: Geben Sie den Text ein, der auf dem Button angezeigt wird.

### Farbe
- **Farbpalette**: Klicken Sie auf eine Farbe, um sie auszuwählen.
- **Custom...**: Öffnet einen nativen Farbwähler für exakte Farbcodes.
- **Vorschau**: Zeigt die aktuell ausgewählte Farbe.

### Datei
- **Ordner-Navigation**: Geben Sie den Ordnerpfad ein oder verwenden Sie "Up" zum Navigieren.
- **Dateiliste**: Zeigt alle `.mp3` und `.wav` Dateien im aktuellen Ordner.
- **Datei wählen**: Klicken Sie auf eine Datei in der Liste, um sie auszuwählen.
- **Pfad-Eingabe**: Der vollständige Pfad wird oben angezeigt und kann auch manuell eingegeben werden.
- **Refresh**: Aktualisiert die Dateiliste (z. B. nach Ordnerwechsel).

### Speichern
- **Übernehmen**: Speichert alle Änderungen (Text, Farbe, Datei).
- **Abbrechen**: Schließt das Fenster ohne zu speichern.

---

## Dateiformat

### Einstellungen
- **Speicherort**: `C:\Users\<Benutzer>\.jingleplayer\jingleplayer_settings.json`
- **Inhalt**: JSON-Format mit Button-Texten, Farben, Dateipfaden, Anzahl Buttons pro Reihe, Lautstärke, Fadeout-Dauer, Button-Höhe und zuletzt verwendetem Ordner.

### Unterstützte Audioformate
- `.mp3` (MPEG-3 Audio)
- `.wav` (WAV/PCM Audio)

---

## Tastenkombinationen & Shortcuts
- **Rechtsklick auf Button**: Öffnet Bearbeitungs-Dialog.
- **Linksklick auf Button**: Play/Stop.
- **Schließen-Button (X)**: Speichert Einstellungen und beendet die App.

---

## Fehlerbehebung

### "Audio-Funktion nicht verfügbar: pygame ist nicht installiert."
- **Lösung**: Installieren Sie pygame über: `pip install pygame`

### Button-Einstellungen werden nicht gespeichert
- Stellen Sie sicher, dass das Verzeichnis `C:\Users\<Benutzer>\.jingleplayer\` schreibbar ist.
- Überprüfen Sie die Dateiberechtigungen.

### Dateien nicht im Dateibrowser sichtbar
- Nur `.mp3` und `.wav` Dateien werden angezeigt.
- Überprüfen Sie den Ordnerpfad und die Dateierweiterungen.

### Lautstärke wird nicht angepasst
- pygame muss installiert sein.
- Überprüfen Sie, dass die System-Lautstärke nicht auf 0% gestellt ist.

---

## Tipps & Tricks

1. **Schnelle Navigation**: Verwenden Sie "Up" im Dateibrowser, um mehrere Ordner hoch zu gehen.
2. **Ordner merken**: Der zuletzt verwendete Ordner wird gespeichert und beim nächsten Mal verwendet.
3. **Bulk-Edits**: Um mehrere Buttons zu bearbeiten, öffnen Sie sie nacheinander mit Rechtsklick.
4. **Layout anpassen**: Über "Buttons pro Reihe" können Sie die Anordnung jederzeit ändern.
5. **Backup**: Die `jingleplayer_settings.json` regelmäßig sichern, um Einstellungen nicht zu verlieren.

---

## Kontakt & Support
Für Fragen oder Probleme: Konsultieren Sie die Anwendungs-Logs oder überprüfen Sie den Speicherort der Einstellungsdatei.

---

**Version**: 1.0  
**Datum**: November 2025  
**Anwendung**: Jingleplayer
