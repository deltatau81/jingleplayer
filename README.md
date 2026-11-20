# Jingleplayer

Jingleplayer ist ein Desktop-Soundboard für Jingles, Veranstaltungen, Podcasts und
Live-Einsätze mit Python, PySide6 und pygame. Zielversion: **1.1.0-rc1**.
Der Release Candidate ist als **öffentlicher Prerelease** veröffentlicht.

## Funktionen

- Bis zu 50 dauerhaft gespeicherte Buttons **pro Preset** in fünf konfigurierbaren Reihen.
- Mehrere unabhängige Presets mit eigenem Layout, Fadeout und Hintergrundbild.
- MP3/WAV, parallele Wiedergabe und individuelle Lautstärke von −10 bis +10 dB.
- Audio-Pools mit sequenzieller, zufälliger oder manueller Dateiauswahl.
- Halbtransparente Buttons mit individuell farbigen Rahmen.
- Vollständige portable Soundboard-ZIP-Pakete mit allen Presets, Audio-Pools und Bildern.

Ein Linksklick startet den Sound; erneutes Klicken stoppt oder blendet ihn aus.
Rechtsklick öffnet **Jingle bearbeiten**. Natürliches Soundende startet keine
weitere Datei. Es gibt keine globale STOP-ALL-Schaltfläche.

## Presets

Auswahl im Hauptfenster; **Presets → Neu…**, **Duplizieren…**, **Umbenennen…** und
**Löschen…** verwalten die Boards. Beim Wechsel wird Wiedergabe gestoppt.
Das letzte Preset bleibt geschützt. Löschen entfernt keine Mediendateien.
Ausgeblendete Slots bleiben gespeichert. [Details](PRESETS.md).

## Audio-Pools

Im Buttondialog **Audio-Pool** auswählen. **Hinzufügen…**, **Entfernen**,
**Leeren**, **Nach oben** und **Nach unten** bearbeiten die Liste.
**Speichern** übernimmt Änderungen, **Abbrechen** verwirft sie.

- **Sequenziell:** Jeder erfolgreiche Start verwendet die nächste Datei.
- **Zufällig:** Keine direkte Wiederholung, wenn eine andere Datei abspielbar ist.
- **Manuell:** Dateiauswahl im Dialog oder direkt am Button; bleibt nach Neustart
  erhalten. Auswählen startet keinen Sound und ersetzt keinen laufenden Sound.

Automatische Modi überspringen unbrauchbare Dateien mit Statusmeldung.
Manuelle Auswahl wird bei Fehlern nicht still ersetzt.

## Hintergründe und Buttondesign

**Presets → Hintergrundbild auswählen…** lädt PNG/JPEG für das aktive Preset.
**Hintergrundbild entfernen** löscht nur die Zuordnung. Das Bild füllt den
Kachelbereich proportional mit mittigem Beschnitt. Die dunkle halbtransparente
Buttonfläche lässt das Bild durchscheinen; individuelle Farben markieren Rahmen.
Fehlende Bilder erzeugen eine Statusmeldung, die Zuordnung bleibt erhalten.

## Portable Soundboards

Portable Soundboard-ZIP-Pakete enthalten Konfiguration und Medien zum Austausch
zwischen Jingleplayer-Installationen. Sie werden in der Anwendung importiert und
sind keine Installationsarchive für das Programm.

**Soundboard → Soundboard exportieren...** erstellt eine neue ZIP-Datei mit allen
Presets, 50 Slots je Preset, vollständigen Pools und Bildern. Fehlende/unlesbare
Medien brechen den Export ab. **Soundboard importieren...** zeigt eine Vorschau
und fügt nach Bestätigung Presets mit neuen IDs und eindeutigen Namen hinzu.
Lokale Fenstergröße, Gesamtlautstärke und letzter Audioordner bleiben erhalten.
Medien werden unabhängig vom Quellarchiv dauerhaft unter
`~/.jingleplayer/imported_soundboards/<paketname>-<uuid>/` abgelegt.
Wiederholter Import erstellt einen eigenen Ordner. Preset-Löschung löscht keine Medien.

Das bisherige Ordnerformat bleibt über **Alten Paketordner importieren...** und
**Einzelboard exportieren (altes Format)...** verfügbar. Mehrdatei-Pools und Bilder
gehören ins neue ZIP-Format. [Formate und Wiederherstellung](PORTABLE_SOUNDBOARDS.md).

## Installation

Die manuell gestartete [Release-Build-Pipeline](.github/workflows/release-build.yml)
stellt nach erfolgreicher Validierung Archive und SHA256-Dateien als
GitHub-Actions-Artefakte bereit (14 Tage). Diese Installationsarchive enthalten die
Anwendung; sie sind von den oben beschriebenen portablen Soundboard-ZIP-Paketen
zu unterscheiden. Der Release Candidate ist als öffentlicher GitHub-Prerelease v1.1.0-rc1 verfügbar.

Der [GitHub-Actions-Lauf 44815755125](https://github.com/deltatau81/jingleplayer/actions/runs/44815755125)
war erfolgreich: alle acht Jobs sowie die Integritäts- und SHA256-Prüfungen der
vier Release-Archive für Windows x86_64, Linux x86_64, macOS arm64 und macOS x86_64.
Diese automatisierte Validierung ersetzt keine nativen GUI-/Audioprüfungen.

Alle Builds sind ohne Herausgeberzertifikat; macOS ist nicht notarisiert.
Architektur, Systemvoraussetzungen, Buildbefehle und Prüfschritte: [RELEASE.md](RELEASE.md).

Im Bereich **Artifacts** dieses Laufs das zur Plattform und Architektur passende
Artefakt herunterladen und zunächst den GitHub-Artefaktcontainer entpacken.
Darin liegen das eigentliche Installationsarchiv und seine `.sha256`-Datei.
Die SHA256-Prüfsumme vor dem Entpacken des Installationsarchivs vergleichen;
Prüfbefehle stehen in [RELEASE.md](RELEASE.md). Anschließend wie folgt starten:

| Plattform | Installationsarchiv und Start |
| --- | --- |
| Windows x86_64 | Installations-ZIP entpacken und `Jingleplayer.exe` per Doppelklick starten; kein Python erforderlich |
| macOS arm64 / x86_64 | Zur Architektur passendes ZIP entpacken (arm64 für Apple Silicon, x86_64 für Intel), `Jingleplayer.app` nach Programme kopieren und dort öffnen |
| Linux x86_64 | tar.gz vollständig entpacken, im Terminal in den Entpackordner wechseln und `./Jingleplayer/Jingleplayer` starten; den gesamten Ordner `Jingleplayer` zusammenhalten |

macOS kann das nicht notarisierte Bundle blockieren. Nur einen geprüften Download
über Finder → Öffnen bzw. die Sicherheitseinstellungen freigeben; keine pauschale
Deaktivierung von Gatekeeper. Native GUI-/Audioprüfungen auf macOS/Linux stehen aus.

## Bedienung und Einstellungen

**Einstellungen** konfiguriert Fadeout, 0–10 sichtbare Buttons je Reihe und
Buttonhöhe. Mindestens ein Button bleibt sichtbar. Gesamtlautstärke: 0–100 %.
**Hilfe** öffnet das gebündelte [Benutzerhandbuch](HELP.md).

Daten liegen unter `~/.jingleplayer/`, auf Windows gewöhnlich
`C:\Users\<Benutzer>\.jingleplayer\`. Bundle und Programmordner dienen nur zum Lesen.
Settings, Importmedien, Staging und Recovery liegen im Benutzerdatenverzeichnis.
Es gibt keinen stillen Ausweichordner bei Schreibfehlern.

Anwendungsfassung **1.1.0-rc1**, internes **Settings-Schema 3** und **ZIP-Paketformat 3**
sind unabhängig. Alte Ordnerpakete verwenden **Paketformat 1 mit Settings-Schema 2**.
Vor dem ersten tatsächlichen Save einer migrierten Settingsdatei entsteht ein
bytegenaues `jingleplayer_settings.json.pre-presets.<SHA256>.json`-Backup.
Version 1.0.0 kann Schema 3 nicht lesen. Beschädigte/neue unbekannte Settings werden
nicht überschrieben. [Migration und Konflikte](PRESETS.md).

## Entwicklung und Tests

```text
python -m pip install -r requirements.txt -r requirements-dev.txt
python jingleplayer_app.py
python -m pytest -q -ra
```

Produkt-Einstieg: `jingleplayer_app.py`; produktive GUI: `jingleplayer_gui_pyside6.py`;
Audio/Settings: `jingleplayer_logic.py`. Die Tkinter-GUI ist historisch.
PyInstaller 6.16.0 ist bereits als Buildwerkzeug vorgegeben; keine zweite Infrastruktur.
[Audioengine](AUDIO_ENGINE.md), [Release Notes](RELEASE_NOTES_v1.1.0-rc1.md).

## Bekannte Einschränkungen

Automatische Tests nutzen Offscreen-Qt und SDL-Dummytreiber; sie bestätigen keine
Hardwareaudioqualität oder nativen Dialoge. Windows: laut Phase-18D-Abnahme 9/9
manuelle Import-/Export-/Audioprüfungen bestanden. Native macOS-/Linux-GUI- und
Audioprüfungen sind akzeptiertes Restrisiko, keine durchgeführten Tests.
Keine Codesignierung/Notarisierung oder garantierte Crash-Durabilität.
Recovery enthält Settings, keine Sicherung zuvor externer Medien.
