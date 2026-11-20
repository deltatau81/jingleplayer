# Release-Vorbereitung 1.1.0-rc1

Nur `feature/macos-support`. Kein Commit, Push, Tag, Release und keine
Repository-Metadatenänderung sind Teil dieser Vorbereitung.

## Bestehende Infrastruktur und Build

PyInstaller 6.16.0 aus `requirements-dev.txt`, pygame 2.6.1 und PySide6 aus
`requirements.txt`. Windows verwendet weiterhin `build_windows.ps1` (onefile,
windowed, Tests vor Build). macOS verwendet weiterhin `build_macos.sh` (native
Python-3.11-Architektur, onedir `.app`). Linux ergänzt denselben PyInstaller-Weg.
Qt-/pygame-Hooks von PyInstaller sammeln deren Bibliotheken und Qt-Plugins;
HELP.md und Icon werden ausdrücklich eingebunden. Kein Python beim Endnutzer nötig.

```text
# Windows, nach Installation beider requirements-Dateien
powershell -ExecutionPolicy Bypass -File build_windows.ps1
# macOS, native Python-3.11-Umgebung
bash build_macos.sh
# Linux, nach vollständiger Testsuite
python -m pytest -q -ra
bash build_linux.sh
# jeweils nach dem nativen Build
python verify_frozen.py
python release_archive.py
```

Der Frozen-Smoke-Test startet aus fremdem temporären Arbeitsverzeichnis, verwendet
isolierte Settings und prüft GUI-Erzeugung, Schema-3-Speichern/Laden, PNG-Codec,
gebündelte Hilfe/Icon und Mixer mit Dummytreiber. Er ist kein Hardwareaudiotest.
Die übrige Testsuite deckt Pools, Presets, Hintergründe und Paketimport/-export ab.
Alle Produktdaten bleiben im Home-Datenordner; `_MEIPASS` wird nur für Ressourcen gelesen.
Die Buildprüfung schreibt ihre Testdaten ausschließlich in temporäre Verzeichnisse.

## Workflow und Artefakte

`release-build.yml` wird nur manuell auf dem Arbeitsbranch gestartet.
Alle vier Validierungsjobs müssen erfolgreich sein, bevor Builds beginnen.
Windows, Ubuntu 22.04 und beide nativen macOS-Architekturen werden gebaut.
Bestehende `tests.yml` und `macos.yml` bleiben unverändert.
Kein Veröffentlichungsjob, nur `contents: read`; Downloads als Actions-Artefakte,
14 Tage Aufbewahrung. Version kommt aus `jingleplayer_version.py`.

| Plattform | Vorgesehener Archivname | Aktueller Stand |
| --- | --- | --- |
| Windows | `Jingleplayer-1.1.0-rc1-Windows-x86_64-unsigned.zip` | Lokale Prüfung siehe unten |
| macOS Apple Silicon | `Jingleplayer-1.1.0-rc1-Darwin-arm64-unsigned.zip` | Erst nach Actions-Lauf verfügbar |
| macOS Intel | `Jingleplayer-1.1.0-rc1-Darwin-x86_64-unsigned.zip` | Erst nach Actions-Lauf verfügbar |
| Linux | `Jingleplayer-1.1.0-rc1-Linux-x86_64-unsigned.tar.gz` | Erst nach Actions-Lauf verfügbar |

Daneben jeweils `<archiv>.sha256`. Prüfen: Windows `Get-FileHash <archiv> -Algorithm SHA256`,
macOS `shasum -a 256 <archiv>`, Linux `sha256sum -c <archiv>.sha256`.
macOS-Archivierung verwendet das bestehende `ditto`-Verfahren für Bundles.
Linux-tar bewahrt Ausführungsrechte und Symlinks. Archive vollständig entpacken.

## Plattformgrenzen

Windows x86_64: Buildziel Windows Server 2022; Windows-10/11-Nutzergeräte manuell
prüfen. macOS: getrennte native arm64-/x86_64-Builds auf macOS-15-Runnern,
kein Universal-Bundle. Konservatives RC-Testziel macOS 15 oder neuer;
ältere macOS-Versionen sind nicht freigegeben. Die effektive technische Mindestversion
hängt von den aufgelösten Qt-/Python-Binaries ab; vor breiterer Freigabe Info.plist,
Mach-O-Load-Commands und tatsächlichen Start auf der ältesten Zielversion prüfen.
Keine Developer-ID-Signierung oder Notarisierung; PyInstaller kann ad-hoc signieren.

Linux: x86_64, Ubuntu 22.04 als Buildbasis (glibc 2.35); vorgesehenes Testziel
Ubuntu 22.04/24.04 mit Desktop. Andere Distributionen sind nicht validiert.
Systemkomponenten wie glibc, Grafik-/X11-/Wayland-Treiber und Audiogeräte bleiben nötig.
Auf Ubuntu bei fehlenden Qt-Libraries: `libegl1`, `libopengl0`,
`libxkbcommon-x11-0`, `libxcb-cursor0` und das zur Distribution passende ALSA-Paket
(22.04: `libasound2`). Keine Behauptung eines universellen statischen Linux-Builds.

## GitHub-Auftritt – nur Entwurf

Die [öffentliche Repositoryseite](https://github.com/deltatau81/jingleplayer)
konnte über den Web-Lesezugriff geprüft werden. Die bestehende Beschreibung ist
noch auf Windows ausgerichtet und nennt konfigurierbare Buttons, parallele
Wiedergabe, individuelle Lautstärke, Fadeout und persistente Einstellungen.
Bestehende Topics: `desktop-app`, `jingle-player`, `pygame`, `pyside6`, `python`,
`soundboard`, `windows`. Alle erhalten; ergänzen: `audio-player`, `cross-platform`.

Bestehende Releases und deren Artefaktstruktur konnten nicht verifiziert werden:
`gh` scheitert mit HTTP 401, die öffentliche Releases-Seite/API war über den
Webzugriff nicht verfügbar. Der lokale TLS-Abruf scheiterte ebenfalls.

Beschreibung: “Cross-platform audio jingle player with customizable soundboards,
presets, audio pools and portable packages.”

Topics als Ergänzungsvorschlag: `python`, `pyside6`, `pygame`, `soundboard`,
`jingle-player`, `audio-player`, `cross-platform`.

## Validierung und verbleibende Prüfungen

Die Phase-18D-Abnahme meldet Windows 9/9 manuelle Prüfungen und erfolgreiche
Windows-/Ubuntu-/macOS-CI. Diese Angaben wurden nicht als neuer RC-Lauf nachgewiesen.
Native GUI-/Audiotests unter macOS/Linux gelten als akzeptiertes Restrisiko.
Ausstehend: Release-Workflow nach gesondertem Push starten, native Archive prüfen,
macOS-Architekturen/Plist kontrollieren, Linux-Desktop/Hardwareaudio testen und
auf allen Plattformen Settings, Pools, Hintergründe und Paket-Roundtrip aus einem
schreibgeschützten Installationsverzeichnis prüfen. Keine Schreibrechte im Bundle nötig.

Lokale Windows-Prüfung (Python 3.13.7): **807 bestanden, 21 übersprungen**,
eine pygame/pkg_resources-Deprecation-Warnung; `pip check` ohne Konflikte.
Die Skips betreffen unter anderem nicht verfügbare Symlink-Rechte und POSIX-Fälle.
Windows-Build und Frozen-Smoke-Test erfolgreich, einschließlich WAV-Decodierung,
Paketexport/-import mit manuellem Pool und Hintergrundbild im temporären Datenordner.
Keine Hardwareaudio- oder interaktive GUI-Abnahme des neuen RC durchgeführt.
Python-/PowerShell-/Bash-Syntax, Workflow-Struktur, lokale Dokumentationslinks und
`git diff --check` geprüft. Keine Settings-/Paketmodell- oder Audioengineänderungen.
Die bestehenden Änderungen an GUI-Fokusdarstellung und `tests/test_backgrounds.py`
stammen aus dem vorgefundenen Arbeitsstand und wurden erhalten.
Buildlogs liegen lokal unter `build/phase19-build.txt`; Artefakte unter `dist/release/`.
Neue Release-Actions wurden nicht ausgeführt; `main` blieb unberührt.

Abschließende Artefaktprüfung: Windows-ZIP 55.441.748 Bytes; SHA256
`e4759ab193a9e1db391acc8647fa95cd39cfa535ec0ded47b8a9be6ca1aa2b08`.
Archiv entpackt und die darin enthaltene EXE aus fremdem Verzeichnis erfolgreich
geprüft. PE-Subsystem ist GUI (kein Konsolenstart); Qt-Windows-/JPEG-Plugins,
pygame und HELP.md sind im PyInstaller-Payload vorhanden. Auch der finale Build
meldet 807 bestandene und 21 übersprungene Tests. Kein aktueller geeigneter
Oberflächen-Screenshot im Repository vorhanden; deshalb keiner hinzugefügt.
