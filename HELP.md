# Jingleplayer – Benutzerhandbuch

## Übersicht

Jingleplayer ist eine Desktop-Anwendung zum schnellen Abspielen von Jingles über frei konfigurierbare Kacheln. Unterstützt werden MP3- und WAV-Dateien.

Mehrere Jingles können gleichzeitig und unabhängig voneinander abgespielt werden. Für jeden Jingle lassen sich Text, Farbe, Audiodatei und individuelle Lautstärke einstellen.

## Hauptfenster

### Jingle-Kacheln

Jingleplayer verwaltet 50 dauerhafte Jingle-Plätze in fünf Reihen. Für jede Reihe kann eingestellt werden, wie viele Kacheln sichtbar sind:

- 0 bis 10 Kacheln pro Reihe
- maximal 50 sichtbare Kacheln insgesamt
- genau fünf konfigurierbare Reihen

Weniger sichtbare Kacheln löschen keine Konfigurationen. Wird die Anzahl später wieder erhöht, erscheinen die zuvor ausgeblendeten Plätze mit ihren gespeicherten Einstellungen erneut.

### Jingle starten und stoppen

Ein Linksklick auf eine inaktive Kachel startet den zugeordneten Jingle. Die aktive Umrandung der Kachel zeigt an, dass dieser Jingle läuft.

Ein weiterer Linksklick auf dieselbe aktive Kachel stoppt beziehungsweise blendet nur diesen Jingle mit der eingestellten Fadeout-Dauer aus. Andere laufende Jingles werden nicht beeinflusst.

Wenn ein Jingle natürlich endet, entfernt Jingleplayer seine aktive Umrandung automatisch.

### Mehrere Jingles gleichzeitig

Mehrere Jingles können gleichzeitig abgespielt und unabhängig voneinander gestoppt werden. Auch dieselbe Audiodatei kann über unterschiedliche Kacheln auf getrennten Wiedergabekanälen laufen.

Eine globale Funktion zum gleichzeitigen Stoppen aller Jingles ist nicht vorhanden.

## Lautstärke

### Globale Lautstärke

Der Regler im oberen Bereich des Hauptfensters steuert die Gesamtlautstärke von 0 bis 100 Prozent. Die Änderung wirkt sofort und wird gespeichert.

### Individuelle Jingle-Lautstärke

Jeder Jingle besitzt im Bearbeitungsdialog eine zusätzliche Einstellung von -10 dB bis +10 dB. Damit können unterschiedlich laute Audiodateien angeglichen werden.

Die globale und die individuelle Lautstärke werden gemeinsam berücksichtigt. Änderungen wirken auch auf einen bereits laufenden Jingle.

## Jingle bearbeiten

Ein Rechtsklick auf eine Jingle-Kachel öffnet den Bearbeitungsdialog. Dort können geändert werden:

- Name beziehungsweise Text
- MP3- oder WAV-Datei
- Kachelfarbe
- individuelle Lautstärke von -10 dB bis +10 dB

Die Schaltfläche **Durchsuchen...** öffnet den nativen Dateidialog. Der zuletzt verwendete Audioordner wird für die nächste Dateiauswahl automatisch vorgemerkt.

Mit **Speichern** werden die Änderungen übernommen. **Abbrechen**, Escape oder das X des Fensters schließen den Dialog ohne Übernahme.

## Einstellungen

Die Schaltfläche **Einstellungen** öffnet den Einstellungsdialog.

### Fadeout-Dauer

Die Fadeout-Dauer bestimmt in Millisekunden, wie lange ein Jingle beim manuellen Stoppen ausgeblendet wird. Der Standardwert beträgt 1000 ms. Der Fadeout betrifft nur den gestoppten Jingle.

### Kacheln pro Reihe

Für jede der fünf Reihen kann ein Wert von 0 bis 10 festgelegt werden. Mindestens eine Kachel muss insgesamt sichtbar bleiben.

Alle 50 Jingle-Plätze bleiben gespeichert, auch wenn über die fünf Reihen momentan weniger Kacheln angezeigt werden.

### Kachelhöhe

Die Höhe der Jingle-Kacheln kann im Einstellungsdialog angepasst werden.

Nach einem erfolgreichen Speichern werden Änderungen an Reihen und Kachelhöhe sofort sichtbar. Ein Neustart ist nicht erforderlich.

### Hilfe

Die Schaltfläche **Hilfe** öffnet dieses mit der Anwendung ausgelieferte Handbuch direkt im Jingleplayer.

Der Einstellungsdialog enthält keine Felder zum Ändern des Settings-Speicherorts oder zum Festlegen eines Standard-Audioordners. Der beim Durchsuchen zuletzt verwendete Audioordner wird automatisch gemerkt.

## Einstellungen und Datensicherheit

Die Konfiguration wird normalerweise hier gespeichert:

```text
C:\Users\<Benutzer>\.jingleplayer\jingleplayer_settings.json
```

Jingleplayer verwendet das Settings-Format Version 2. Gespeichert werden unter anderem:

- Texte, Farben und Audiodateien aller 50 Jingle-Plätze
- individuelle Jingle-Lautstärken
- fünf Werte für die sichtbaren Kacheln pro Reihe
- globale Lautstärke
- Fadeout-Dauer
- Kachelhöhe
- Fenstergröße
- zuletzt verwendeter Audioordner

### Ältere Einstellungen

Ältere Einstellungen werden beim Laden für die aktuelle Anwendung aufbereitet. Reines Starten und unverändertes Schließen schreibt die vorhandene Datei nicht um.

Beim ersten tatsächlichen Speichern einer Änderung wird vor der Umstellung eine exakte Sicherung der bisherigen Datei angelegt:

```text
jingleplayer_settings.pre-pyside6.json
```

### Beschädigte oder neuere Einstellungen

Eine beschädigte oder strukturell ungültige Settingsdatei wird nicht automatisch überschrieben. Dasselbe gilt für eine Datei aus einer neueren, noch nicht unterstützten Formatversion. Jingleplayer zeigt in diesem Fall eine Fehlermeldung und beendet den Start kontrolliert.

Auch Fehler beim späteren Speichern werden in einem Fehlerdialog angezeigt.

## Fenstergröße und Beenden

Die gespeicherte Fenstergröße wird beim nächsten Start wiederhergestellt. Eine geänderte Fenstergröße wird beim Schließen gespeichert; bei unveränderter Größe ist kein zusätzlicher Speichervorgang nötig.

Die Anwendung wird über das X des Hauptfensters geschlossen. Es gibt keine separate Beenden-Schaltfläche im Hauptfenster.

## Unterstützte Audioformate

Jingleplayer unterstützt:

- MP3 (`.mp3`)
- WAV (`.wav`)

Andere Formate werden nicht als Jingle-Dateien unterstützt.

## Fehlerbehebung

### Ein Jingle startet nicht

Prüfen Sie:

1. Ist der Kachel eine Audiodatei zugeordnet?
2. Existiert die Datei noch am gespeicherten Speicherort?
3. Handelt es sich um eine MP3- oder WAV-Datei?
4. Ist die globale Lautstärke größer als 0?
5. Ist die individuelle Lautstärke passend eingestellt?

Wiedergabefehler werden direkt in einem Fehlerdialog angezeigt.

### Einstellungen werden nicht gespeichert

Prüfen Sie, ob das Benutzerverzeichnis und der Ordner `.jingleplayer` beschreibbar sind. Fehler beim Speichern werden direkt in der Anwendung angezeigt.

Die Standarddatei befindet sich unter:

```text
C:\Users\<Benutzer>\.jingleplayer\jingleplayer_settings.json
```

### Audiodateien werden nicht angezeigt

Prüfen Sie den im Dateidialog geöffneten Ordner, die Dateiendung und ob es sich tatsächlich um eine `.mp3`- oder `.wav`-Datei handelt.

### Ein Jingle ist zu laut oder zu leise

Öffnen Sie den Jingle mit einem Rechtsklick und passen Sie seine individuelle dB-Einstellung an. Andere Jingles werden dadurch nicht verändert.

### Aktive Umrandung bleibt sichtbar

Normalerweise wird die aktive Umrandung beim Stoppen oder natürlichen Ende automatisch entfernt. Prüfen Sie bei Problemen, ob die Audiodatei korrekt abgespielt werden kann und ob die Anwendung einen Fehlerdialog anzeigt.

## Tipps

1. Verwenden Sie unterschiedliche Farben für verschiedene Jingle-Gruppen.
2. Verwenden Sie kurze, eindeutige Kacheltexte.
3. Gleichen Sie unterschiedlich laute Jingles über ihre individuellen dB-Einstellungen an.
4. Nutzen Sie die fünf Reihen, um Jingles thematisch zu gruppieren.
5. Sichern Sie bei wichtigen Konfigurationen regelmäßig `jingleplayer_settings.json` und vorhandene Migrationsbackups.

## Technische Kurzinfo

Jingleplayer verwendet pygame für die Audiowiedergabe und PySide6 für die Benutzeroberfläche. Laufende Jingles werden über getrennte Mixer-Kanäle verwaltet, sodass sie gleichzeitig abgespielt und unabhängig voneinander gestoppt oder ausgeblendet werden können.

**Stand:** September 2026

**Anwendung:** Jingleplayer
