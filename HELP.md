# Jingleplayer – Benutzerhandbuch

## Übersicht

Jingleplayer ist eine Desktop-Anwendung zum schnellen Abspielen von Jingles über frei konfigurierbare Buttons.

Unterstützt werden MP3- und WAV-Dateien. Für jeden Button können Text, Farbe, Audiodatei und individuelle Lautstärke eingestellt werden.

Mehrere Jingles können gleichzeitig und unabhängig voneinander abgespielt werden.

Die Einstellungen werden automatisch gespeichert.

---

## Hauptfenster

### Jingle-Buttons

Jingleplayer unterstützt bis zu 40 Jingle-Buttons in vier Reihen.

Für jede Reihe kann eingestellt werden, wie viele Buttons angezeigt werden:

- 0 bis 10 Buttons pro Reihe
- maximal 40 Buttons insgesamt

Jeder Button kann unabhängig konfiguriert werden.

### Jingle starten

Klicken Sie mit der linken Maustaste auf einen konfigurierten Button.

Der zugeordnete Jingle wird abgespielt. Die Statusanzeige des Buttons wechselt in den aktiven Zustand.

### Jingle stoppen

Klicken Sie erneut mit der linken Maustaste auf denselben Button.

Der Jingle wird mit der eingestellten Fadeout-Dauer ausgeblendet.

Andere gleichzeitig laufende Jingles werden dadurch nicht gestoppt.

### Mehrere Jingles gleichzeitig

Mehrere Jingles können gleichzeitig abgespielt werden.

Jeder aktive Button wird unabhängig verwaltet. Dadurch kann beispielsweise ein Jingle gestoppt werden, während andere Jingles weiterlaufen.

Auch dieselbe Audiodatei kann unabhängig über unterschiedliche Buttons beziehungsweise Wiedergabekanäle abgespielt werden.

---

## Statusanzeige

Unter jedem Jingle-Button befindet sich eine Statusanzeige.

- **Grün / Pause** – der Button ist nicht aktiv
- **Rot / Play** – der Jingle wird abgespielt

Wenn ein Jingle von selbst vollständig abgespielt wurde, erkennt Jingleplayer das Ende der Wiedergabe und setzt die Anzeige automatisch wieder auf den inaktiven Zustand.

---

## Lautstärke

### Globale Lautstärke

Der Lautstärke-Regler im oberen Bereich des Hauptfensters steuert die Gesamtlautstärke.

Bereich:

`0–100 %`

Die Einstellung wird gespeichert.

### Individuelle Button-Lautstärke

Jeder Jingle-Button besitzt zusätzlich eine individuelle Lautstärkeeinstellung.

Bereich:

`-10 dB bis +10 dB`

Damit können unterschiedlich laute Audiodateien aneinander angepasst werden.

Beispielsweise kann ein besonders lauter Jingle abgesenkt werden, ohne die Lautstärke der anderen Jingles verändern zu müssen.

Änderungen der individuellen Lautstärke werden auch auf einen bereits laufenden Jingle angewendet.

Die globale Lautstärke und die individuelle Button-Lautstärke werden bei der Wiedergabe gemeinsam berücksichtigt.

---

## Button bearbeiten

Klicken Sie mit der rechten Maustaste auf einen Jingle-Button, um dessen Einstellungen zu bearbeiten.

### Text

Die Beschriftung des Buttons kann geändert werden.

### Farbe

Die Farbe des Buttons kann über die angebotenen Farben beziehungsweise den Farbwähler eingestellt werden.

### Audiodatei

Dem Button kann eine Audiodatei zugeordnet werden.

Unterstützte Dateiformate:

- `.mp3`
- `.wav`

Der Dateipfad kann über die Dateiauswahl festgelegt werden.

### Änderungen übernehmen

Mit **Übernehmen** werden die Änderungen gespeichert.

Mit **Abbrechen** wird der Dialog ohne Übernahme der Änderungen geschlossen.

Der Dialog kann ebenfalls über das X des Fensters geschlossen werden.

Nach dem Schließen kann der Bearbeitungsdialog wieder normal für einen anderen Button geöffnet werden.

---

## Einstellungen

Über die Schaltfläche **⚙ Einstellungen** wird das Einstellungsfenster geöffnet.

### Fadeout-Dauer

Die Fadeout-Dauer legt fest, wie lange ein Jingle beim manuellen Stoppen ausgeblendet wird.

Die Angabe erfolgt in Millisekunden.

Standardwert:

`1000 ms`

Der Fadeout betrifft nur den Jingle, der gestoppt wurde. Andere laufende Jingles werden nicht beeinflusst.

### Button-Höhe

Hier kann die Höhe der Jingle-Buttons angepasst werden.

Standardwert:

`2`

Bei Änderungen am Layout kann ein Neustart der Anwendung erforderlich sein.

### Buttons pro Reihe

Jingleplayer besitzt vier konfigurierbare Button-Reihen.

Für jede Reihe kann eine Anzahl zwischen 0 und 10 eingestellt werden.

Damit können insgesamt bis zu 40 Buttons angezeigt werden.

### Standard-Dateipfad

Hier kann ein bevorzugter Ordner für die Auswahl von Audiodateien festgelegt werden.

Dieser Ordner wird bei späteren Datei-Auswahlen wieder verwendet.

### Speicherort der Einstellungsdatei

Jingleplayer speichert seine Konfiguration normalerweise unter:

`C:\Users\<Benutzer>\.jingleplayer\jingleplayer_settings.json`

Der verwendete Speicherort kann über die Einstellungen angezeigt beziehungsweise geändert werden.

Wenn das normale Benutzerverzeichnis nicht verwendet werden kann, kann Jingleplayer auf ein alternatives Datenverzeichnis ausweichen.

---

## Gespeicherte Einstellungen

Jingleplayer speichert unter anderem:

- Button-Texte
- Button-Farben
- Pfade der Audiodateien
- Anzahl der Buttons pro Reihe
- globale Lautstärke
- individuelle Button-Lautstärken
- Fadeout-Dauer
- Button-Höhe
- Fenstergröße
- Standard-Dateipfad

Ältere vorhandene Einstellungen werden beim Laden soweit erforderlich um fehlende Standardwerte ergänzt.

---

## Fenstergröße und Programmstart

Die Größe des Hauptfensters wird gespeichert.

Beim nächsten Start verwendet Jingleplayer die gespeicherte Fenstergröße wieder.

Während die Benutzeroberfläche aufgebaut wird, bleibt das eigentliche Hauptfenster zunächst verborgen. Währenddessen wird ein Startfenster angezeigt.

Dadurch wird verhindert, dass beim Programmstart eine noch unvollständig aufgebaute Oberfläche sichtbar ist.

Nach Abschluss des Aufbaus wird das Hauptfenster angezeigt.

---

## Unterstützte Audioformate

Jingleplayer unterstützt:

- MP3 (`.mp3`)
- WAV (`.wav`)

Andere Dateiformate werden derzeit nicht als Jingle-Dateien angeboten.

---

## Beenden

Die Anwendung kann über die Schaltfläche **Beenden** oder über das Schließen des Hauptfensters beendet werden.

Die Einstellungen werden gespeichert, sodass sie beim nächsten Programmstart wieder zur Verfügung stehen.

---

## Hilfe

Dieses Benutzerhandbuch kann über die Hilfe-Funktion direkt im Jingleplayer geöffnet werden.

Die zugrunde liegende Datei lautet:

`HELP.md`

---

## Fehlerbehebung

### Audio-Funktion nicht verfügbar / pygame fehlt

Jingleplayer verwendet pygame für die Audiowiedergabe.

Falls pygame nicht installiert ist, kann es über die Kommandozeile installiert werden:

```powershell
python -m pip install pygame
```

Alternativ können die Projektabhängigkeiten installiert werden:

```powershell id="5ce8pw"
python -m pip install -r requirements.txt
```

### Ein Jingle startet nicht

Prüfen Sie:

1. Ist dem Button eine Audiodatei zugeordnet?
2. Existiert die Datei noch am gespeicherten Speicherort?
3. Handelt es sich um eine MP3- oder WAV-Datei?
4. Ist pygame installiert?
5. Ist die globale Lautstärke größer als 0?
6. Ist die individuelle Lautstärke des Buttons passend eingestellt?

### Einstellungen werden nicht gespeichert

Prüfen Sie, ob das verwendete Einstellungsverzeichnis beschreibbar ist.

Der normale Speicherort unter Windows lautet:

`C:\Users\<Benutzer>\.jingleplayer\`

### Audiodateien werden nicht angezeigt

Prüfen Sie:

- den ausgewählten Ordner
- die Dateiendung
- ob die Datei tatsächlich eine `.mp3`- oder `.wav`-Datei ist

### Ein Jingle ist zu laut oder zu leise

Verwenden Sie den individuellen Lautstärke-Regler des betreffenden Buttons.

Damit kann die Lautstärke dieses Jingles angepasst werden, ohne die Einstellungen der anderen Buttons zu verändern.

### Statusanzeige bleibt aktiv

Normalerweise erkennt Jingleplayer automatisch, wenn eine Wiedergabe beendet wurde.

Falls die Anzeige trotzdem nicht zurückgesetzt wird, prüfen Sie zunächst, ob die Audiodatei korrekt abgespielt werden kann und ob während der Wiedergabe eine Fehlermeldung in der Konsole ausgegeben wurde.

---

## Tipps

1. Verwenden Sie unterschiedliche Farben für verschiedene Jingle-Gruppen.
2. Verwenden Sie kurze und eindeutige Button-Texte.
3. Gleichen Sie unterschiedlich laute Jingles über die individuellen Lautstärke-Regler an.
4. Nutzen Sie die vier Button-Reihen, um Jingles thematisch zu gruppieren.
5. Legen Sie einen Standard-Dateipfad fest, wenn sich Ihre Audiodateien überwiegend im selben Ordner befinden.
6. Sichern Sie bei wichtigen Konfigurationen regelmäßig die Datei `jingleplayer_settings.json`.

---

## Technische Informationen

Jingleplayer verwendet pygame für die Audiowiedergabe.

Die aktuelle Audio-Engine verwaltet laufende Jingles über separate Mixer-Kanäle. Dadurch können mehrere Jingles gleichzeitig abgespielt und unabhängig voneinander gestoppt beziehungsweise ausgeblendet werden.

Audiodateien werden intern zwischengespeichert, sodass dieselbe Datei nicht bei jedem Start erneut geladen werden muss.

Weitere technische Informationen zur Audio-Engine befinden sich in:

`AUDIO_ENGINE.md`

---

## Kontakt & Support

Bei Problemen können die Konsolenausgaben des Programms zusätzliche Hinweise zur Fehlerursache liefern.

---

**Stand:** September 2026
**Anwendung:** Jingleplayer
