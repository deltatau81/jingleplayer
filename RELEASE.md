# Release-Vorbereitung 1.1.0-rc1

## Preset-Konflikttest nach Linux-Run 44812198703

Untersucht auf `feature/macos-support`, Ausgangscommit `97b01c5`.
`_read` erfasst Existenz, Device-ID, Inode/File-ID, Größe, `mtime_ns`, `ctime_ns`,
optionales `birthtime_ns` und SHA256. `_check_expected` vergleicht zusätzlich die
Originalbytes. Der Vergleich erfolgt vor dem Schreiben und erneut vor Replace.
Es fehlt kein vorhandenes Vergleichsmerkmal in der Produktivimplementierung.

Die Annahme des bisherigen `recreate`-Tests war zu stark: Nach dem letzten Unlink
kann der Inode sofort wiederverwendet werden; bei gleicher Zeitstempelauflösung
und identischen Bytes können sämtliche beobachteten Merkmale gleich bleiben.
Nanosekunden als Einheit garantieren keine Nanosekundenauflösung. Für die
vorliegende Implementierung bedeutet das ausgebliebene Konfliktsignal, dass
Fingerprint und Bytes gleich verglichen wurden. Die einzelnen CI-Statwerte wurden
nicht protokolliert; Inode-Recycling mit Zeitstempelgleichheit ist die daraus
abgeleitete Erklärung, kein separat beobachteter Linux-Metadatenmitschnitt.

Korrektur nur im Test: Ein vor dem Laden angelegter Hardlink hält den ursprünglichen
Inode im Dateisystem, während der Settingspfad tatsächlich gelöscht und neu
angelegt wird. Die neue Datei muss daher eine andere Identität haben; dies wird
explizit geprüft. Der Link wird vor dem Load angelegt, damit seine eigene
Metadatenänderung nicht versehentlich den erwarteten Konflikt auslöst.
Die Fälle `modify`, `delete`, `recreate` und `replace_same_bytes` bleiben erhalten.

Zusätzliche Regressionen führen je 16 schnelle Recreate-/Replace-Vorgänge mit
identischen Bytes und simuliert identischen Stat-Zeitstempeln aus. Trotz gleicher
Größe/Hashes/Zeitstempel muss die andere Dateiidentität den Save blockieren.
Ein weiterer Test ändert den Inhalt bei gleicher Größe, Identität und simuliert
gleichen Zeitstempeln; SHA256/Bytes erkennen weiterhin den Konflikt.
Keine neuen Skips, keine Wartezeiten und keine Produktionsänderung.

Reproduktion: Unter Windows keine vollständige Metadatenkollision in 200 nativen
Recreate-Durchläufen; bei gezielt simuliert gleichem Identitätstupel ist der
unbeobachtbare Austausch reproduzierbar. Kein natives Linux/WSL installiert.
Die grundsätzliche Snapshot-Grenze bleibt: Werden Inhalt und sämtliche erfassten
Metadaten/Identität unbemerkt identisch wiederhergestellt, ist ohne zusätzliche
Dateisystemhistorie keine Unterscheidung möglich. Das ist keine Garantie, jedes
zwischenzeitliche Ereignis zu erkennen; die vorhandenen OS-Locks koordinieren
kooperierende Writer. Die Produktion bleibt einschließlich Linux-PyInstaller-
Ausschluss `pkg_resources`, GUI, Audio und Formaten unverändert.

Quellen: [Python stat-Zeitstempel und Auflösung](https://docs.python.org/3/library/os.html#os.stat_result),
[Linux unlink und Lebensdauer einer Datei](https://man7.org/linux/man-pages/man2/unlink.2.html).

Prüfergebnisse dieser Korrektur: gezielt 40 bestanden, 1 bestehender Symlink-Skip
(Windows ohne entsprechende Rechte); vollständige Suite: 813 bestanden,
21 bestehende Skips, eine pygame/pkg_resources-Deprecation-Warnung.
`git diff --check` erfolgreich. Lokales vollständiges Log:
`build/preset-conflict-full-tests.txt`.
Linux/macOS müssen den stabilisierten Test in der bestehenden CI bestätigen.

Linux-Frozen-Korrektur nach Run `44804714580`, Job `136526492613`:
`pygame.pkgdata` importiert `pkg_resources` optional. Dessen Aufnahme aktiviert
PyInstallers `pyi_rth_pkgres`, der schon vor dem Anwendungseinstieg
`pkg_resources` lädt. Über `jaraco.text` folgt das vendorte `jaraco.context`.
Unter Python < 3.12 benötigt dieses konkret `backports.tarfile` (statt des
Standardbibliotheksmoduls); der gemeldete Frozen-Build enthält dessen öffentlichen
`backports`-Importpfad nicht. Setuptools stellt vendorte Abhängigkeiten über eine
zur Laufzeit ergänzte Suchpfadposition bereit; diese Import-/Aliasstruktur wird
im fehlerhaften Bundle nicht vollständig abgebildet. Ohne den CI-Buildgraphen
ist nicht abschließend geklärt, an welchem Analyseschritt der Alias verloren ging.
Lokal untersucht: PyInstaller 6.16.0, setuptools 80.9.0, pygame 2.6.1;
die exakte setuptools-Version des Linux-Runners wurde nicht separat verifiziert.

Korrektur ausschließlich in `build_linux.sh`: `--exclude-module pkg_resources`.
Die Anwendung verwendet keine pkg_resources-API; pygame 2.6.1 behandelt den
Import ausdrücklich als optional und lädt Ressourcen sonst relativ zu `__file__`.
Dieser vorhandene Fallback funktioniert für das entpackte onedir-Bundle.
Somit wird der unnötige Runtime-Hook nicht mehr eingebunden und die fehlerhafte
Importkette vor dem Start entfällt. Kein Hidden Import, kein `--collect-all`,
keine Paketinstallation und keine Requirements-Änderung erforderlich.
Windows/macOS, Anwendungslogik und `verify_frozen.py` bleiben unverändert.

Regression: Der echte PyInstaller-Modulgraph bestätigt, dass der Ausschluss
`pyi_rth_pkgres` verhindert. Ein zweiter Test führt die installierte
pygame-Implementierung mit gesperrtem pkg_resources-Import aus und liest eine
Ressource erfolgreich über den Fallback. Gezielte Buildtests: 7 bestanden;
Bash-Syntax und `git diff --check` erfolgreich. Die lokale pygame-Warnung zu
`pkg_resources` stammt aus der normalen, nicht ausgeschlossenen Testumgebung.

Offen bleibt die native Linux-Bestätigung: nach manuellem Commit/Push den
[Release-Workflow](https://github.com/deltatau81/jingleplayer/actions/workflows/release-build.yml)
auf `feature/macos-support` neu starten. Er muss unverändert Build,
`python verify_frozen.py` und Archivierung erfolgreich durchlaufen.
Ein erneuter Lauf des alten Commits enthält diese Korrektur nicht.
Hier wurde kein Workflow gestartet: uncommittierte lokale Korrektur,
kein automatischer Push erlaubt und vorhandene gh-Anmeldung ungültig.
Bei künftig zusätzlich eingeführten Abhängigkeiten mit zwingender
pkg_resources-Nutzung muss der Linux-Ausschluss erneut bewertet werden.

Quellen: [pygame 2.6.1 pkgdata-Fallback](https://github.com/pygame/pygame/blob/2.6.1/src_py/pkgdata.py),
[PyInstaller 6.16.0 pkg_resources-Runtime-Hook](https://github.com/pyinstaller/pyinstaller/blob/v6.16.0/PyInstaller/hooks/rthooks/pyi_rth_pkgres.py).

Linux-Pfadkorrektur nach Release-Workflow `44801607888`: Relative Quellpfade
bei `--add-data` wurden in die generierte Spec übernommen und von PyInstaller
gegen `build/linux/spec/` aufgelöst. Dadurch fehlte dort `HELP.md`; derselbe
Fehler betraf das Icon. `build_linux.sh` bestimmt jetzt einmal den absoluten
Projektpfad mit `pwd -P` und verwendet ihn für beide Ressourcen, Einstiegspunkt
und Ausgabepfade. Die Bundle-Ziele `.` und `assets` bleiben unverändert.
Der Regressionstest erzeugt mit PyInstaller eine verschachtelte Spec bei fremdem
Arbeitsverzeichnis und Projektpfad mit Leerzeichen und prüft die tatsächliche
Auflösung beider Datenquellen. Windows, macOS und Workflows bleiben unverändert.
Lokale Prüfung unter Windows: 808 Tests bestanden, 21 übersprungen; gezielte
Buildtests 5/5 bestanden. Bash-Syntax und `git diff --check` fehlerfrei. Ein
nativer Linux-Build muss im Release-Workflow erneut geprüft werden.

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
