# Portable Soundboards – Bedienung und Freigabe

Diese Anleitung beschreibt den PySide6-Produkt-Einstiegspunkt `jingleplayer_app.py`.
Die Tkinter-Oberfläche hat diese Paketfunktionen nicht. Normale Audiozuweisungen
dürfen weiterhin beliebige absolute lokale Pfade verwenden; es findet keine
automatische Umstellung bestehender Soundboards statt.

## Vollständiges ZIP-Medienpaket (Phase 18D)

**Soundboard exportieren...** fragt nach Zielordner und neuem Paketnamen und
erstellt eine neue ZIP-Datei. Exportiert werden alle Presets, alle 50 Slots,
vollständige geordnete Pools mit Modus/manueller Auswahl und sämtliche Hintergründe.
Originale, aktive Settings und Wiedergabe werden beim Export nicht geändert.
Fehlende, unlesbare oder unsichere Dateien brechen den gesamten Export ab.
Für bisherige relative Einzeldatei-Zuweisungen fragt die GUI ausdrücklich nach
dem passenden Basisordner. Pool- und Bildpfade verwenden weiterhin den Settingsordner.
Es wird kein Arbeitsverzeichnis geraten. Die Backend-API verlangt ebenfalls einen
expliziten absoluten Basisordner; sie entdeckt keinen Datenordner selbst.

**Soundboard importieren...** wählt eine ZIP-Datei. Die Vorschau nennt Paketname,
Presetanzahl, Audio-/Bildanzahl und den dauerhaften Importordner. Nach Bestätigung
wird die Wiedergabe für die Aktivierung gestoppt. Alle Presets werden hinzugefügt:
neue IDs, nummerierte NFC/Casefold-Namenskonflikte und Übernahme der aktiven Auswahl
aus dem Paket. Lokale Fenstergröße, globale Lautstärke und letzter Ordner bleiben
erhalten. Nach Erfolg wird die Oberfläche ohne Neustart aktualisiert.

```text
<bestehendes Jingleplayer-Datenverzeichnis>/
  jingleplayer_settings.json
  imported_soundboards/
    <bereinigter-paketname>-<uuid>/
      manifest.json
      audio/
        intro.wav
        intro-2.wav
      backgrounds/
        bild.png
  import-staging/
  import-recovery/
    media3-<uuid>/
      jingleplayer_settings.json
      recovery.json
```

Jeder Import erhält einen eigenen Ordner, ohne bestehende Medien zu überschreiben.
Mediennamen und Erweiterungen bleiben möglichst erhalten; unsichere Namen werden
bereinigt, case-/Unicode-kollidierende Namen nummeriert. Wiederholte Referenzen
auf denselben Quellpfad werden einmal kopiert. Inhaltlich gleiche Dateien unter
unterschiedlichen Pfaden müssen nicht dedupliziert werden. Die dauerhaft gespeicherten
Settings verweisen ausschließlich auf installierte lokale Dateien, niemals auf
Staging oder ursprüngliche Quellen. Nach erfolgreichem Import dürfen das Archiv
und die Quellen entfernt werden. Ein Neustart verwendet die installierten Medien.
Löschen eines Presets löscht keine Medien; automatische Medienbereinigung gibt es nicht.

### Format und Grenzen

Paketversion **3** ist unabhängig vom internen Preset-Schema **3**. Das Manifest ist:

```json
{
  "package_version": 3,
  "name": "Mein Soundboard",
  "settings": {"schema_version": 3, "...": "vollständiges Preset-Dokument"},
  "assets": [
    {"path": "audio/intro.wav", "kind": "audio", "size": 123, "sha256": "64 Kleinbuchstaben-Hexzeichen"}
  ]
}
```

Das Beispiel verkürzt ausschließlich die Settings. Alle Medienreferenzen in den
Presets sind relative Vorwärtsslash-Pfade. Manifest und ZIP-Inventar müssen exakt
übereinstimmen; jede Datei ist referenziert und jede Referenz ist deklariert.
`last_folder` ist im Paket leer. Absolute Pfade, Traversal, Backslashes,
Windows-reservierte Namen, Kontrollzeichen, Unicode-/Case-Kollisionen, doppelte
JSON-Schlüssel, widersprüchliche Pools und unbekannte Felder werden zurückgewiesen.
Nur reguläre Dateien sind zulässig, keine Links, Geräte, Verzeichniseinträge,
verschlüsselten Einträge oder fremden Zusatzdateien. Audio ist MP3/WAV, Bilder
PNG/JPEG. Hashes sichern Bytes, nicht die Abspielbarkeit beliebiger Audiodaten.

Limits: Manifest 1 MiB; höchstens 4096 ZIP-Einträge einschließlich Manifest,
1 GiB je Audiodatei und 5 GiB Medien insgesamt; Kompressionsverhältnis höchstens
200:1 und begrenztes ZIP-Zentralverzeichnis vor Indexaufbau. Größen werden vor
und während des Lesens geprüft. ZIP unterstützt STORED und DEFLATE; eigene Exporte
verwenden STORED. Bilder: 32 MiB, 40 Megapixel, 16384 Pixel je Dimension,
einschließlich tatsächlicher Decode-Prüfung. Die vorhandene Cover-Darstellung
und ihr Resize-Cache ändern sich nicht.

### Fehler, Recovery und Grenzen

Export veröffentlicht eine vollständig geprüfte ZIP-Datei atomar ohne Überschreiben.
Import entpackt in eigene Staging-Verzeichnisse innerhalb des Datenbereichs, prüft
SHA-256 und Bilder und veröffentlicht erst vollständige Medien. Anschließend
aktiviert die bestehende Settings-Persistenz unter Sperre mit geladenem Fingerprint.
Unmittelbar vor dem Settings-Austausch werden installierte Medien und Recovery
erneut geprüft. Die Recoverydatei enthält die ursprünglichen Settingsbytes;
`recovery.json` nennt Größe, SHA-256, vorgeschlagenen Settings-Hash und Medienordner.

Bei sicher fehlgeschlagenem Commit bleiben alte Presets unverändert; eigene neue
Medien und Staging werden bereinigt. Schlägt die sichere Bereinigung fehl, werden
Restpfade ausdrücklich gemeldet. Recoverydaten werden absichtlich behalten.
Bei bereits erfolgtem oder unklarem Commit-Ausgang dürfen möglicherweise aktive
Medien nicht gelöscht werden: gemeldete Dateien bleiben erhalten, die bestehende
GUI-Behandlung für unklare Speicherzustände sperrt weitere Saves. Niemals blind
eine Sicherung zurückspielen. Alle Instanzen schließen, aktuellen Zustand separat
sichern, Settings/Medien und Recoverygröße/-hash prüfen und erst dann manuell
entscheiden. Eine Wiederherstellung von Settings löscht keine neu importierten Medien.

Keine Garantie für vollständige Crash-/Stromausfall-Durabilität oder für Sicherheit
gegen feindlichen Austausch vertrauenswürdiger Elternverzeichnisse durch andere
Prozesse desselben Benutzers. Ein Absturz zwischen Medienveröffentlichung und
Settings-Commit kann unreferenzierte Dateien hinterlassen. Ältere Anwendungsversionen
und externe Editoren beachten die Settings-Sperre nicht. Native Windows-/macOS-,
Bundle-, Hardwareaudio- und Berechtigungstests bleiben zusätzlich notwendig.

## Kompatibilität: altes Ordnerformat

Die folgenden Abschnitte beschreiben ausschließlich das weiterhin unterstützte
alte Format: **Paketversion 1 mit Settings-Schema 2**. Es wird nicht automatisch
umgeschrieben. **Alten Paketordner importieren...** behält Hinzufügen/Ersetzen,
**Einzelboard exportieren (altes Format)...** den bisherigen aktiven Boardexport.
Bilder und Mehrdatei-Pools werden nur vom neuen vollständigen ZIP-Format transportiert.

## Altes Format: Exportieren

1. Offene Tasten- oder Einstellungsdialoge zuerst speichern oder schließen.
2. **Soundboard → Einzelboard exportieren (altes Format)...** wählen.
3. Einen vorhandenen übergeordneten Ordner auswählen und anschließend einen
   **neuen Paketnamen** eingeben. Das Paket wird als direkter Unterordner angelegt.
   Vorhandene Ziele werden weder überschrieben noch zusammengeführt. Pfadzeichen,
   reservierte Windows-Namen, Steuerzeichen und abschließende Punkte/Leerzeichen
   sind im Paketnamen nicht erlaubt; die Oberfläche begrenzt ihn auf 200 UTF-8-Bytes.
4. Bei relativen Audiozuweisungen den ausdrücklich abgefragten Basisordner wählen.
   Der Export rät diesen nicht aus dem Arbeitsverzeichnis. Für alte relative
   Zuweisungen muss der gewählte Ordner zu deren bisheriger Wiedergabe passen.
5. Die Prüfung umfasst **alle 50 dauerhaften Tastenplätze**, auch ausgeblendete.
   Fehlende Dateien werden mit Tastennummer, Beschriftung und Pfad aufgelistet.
   **Export abbrechen** lässt alles unverändert. **Ohne fehlende Dateien exportieren**
   leert nur diese Audiozuweisungen in der Exportkopie; Texte, Farben, individuelle
   Lautstärke und Layout bleiben erhalten. Wiederholte Referenzen auf dieselbe
   fehlende Datei werden für alle betroffenen Plätze behandelt.
6. Die Erfolgsmeldung nennt den vollständigen Paketpfad. Den gesamten Ordner
   einschließlich beider JSON-Dateien und `Musik/` übertragen.

Nicht lesbare Dateien, Links/Junctions, nicht reguläre Dateien und nicht unterstützte
Endungen blockieren den Export. Sie werden nicht als fehlende Dateien übersprungen.
Zum Neuzuweisen den Export abbrechen und per Rechtsklick die Tasteneinstellungen
öffnen; für versteckte Plätze zunächst die sichtbaren Reihen erweitern.
Die Vorprüfung prüft Lesbarkeit, nicht die Audio-Decodierung. Größe und SHA-256
sichern die übertragenen Bytes, beweisen aber keine abspielbare MP3/WAV-Datei.
Verschwindet oder verändert sich eine Datei nach der Vorprüfung, kann der Export
weiterhin fehlschlagen; er lässt dann keine absichtlich unvollständige Veröffentlichung zu.

Der Export kopiert ausschließlich das aktive Preset als kompatiblen Schema-2-Board-Snapshot, einschließlich bereits
bestätigter Änderungen, deren Speichern fehlgeschlagen sein kann. Unbestätigte
Dialogeingaben werden nicht übernommen. Originalaudio, aktive Settingsdatei und
laufende Wiedergabe werden beim Export nicht verändert.

## Paketformat und Plattformen

```text
MeinSoundboard/
  jingleplayer_package.json
  jingleplayer_settings.json
  Musik/
    asset-001.mp3
    asset-002.wav
```

Der Manifestvertrag bleibt **Paketversion 1**, die Konfiguration **Settingsschema 2**:

```json
{
  "package_version": 1,
  "assets": [
    {"path": "Musik/asset-001.wav", "size": 0,
     "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
  ]
}
```

Das Beispiel zeigt den Hash einer leeren Datei, keine Empfehlung für Audiodaten.
Jede aufgeführte Datei muss mindestens einer nichtleeren Tastenreferenz entsprechen;
alle Referenzen müssen genau zum Manifest passen. Mehrere Tasten dürfen dieselbe
Datei verwenden. Der Export kopiert kanonisch identische Quellen/Hardlinks einmal;
verschiedene Quellen erhalten kurze, eindeutig nummerierte ASCII-Dateinamen.
Gleiche Basenamen sowie Unterschiede nur in Großschreibung oder Unicode-Schreibweise
führen dadurch nicht zu Überschreibungen. Eine inhaltliche Deduplizierung verschiedener
Quelldateien wird nicht versprochen.

Paketpfade sind relative Pfade mit `/` unter `Musik/`, unabhängig von Windows oder
macOS. Absolute Pfade, Laufwerks-/UNC-/Gerätepfade, `..`, Backslashes, leere
Komponenten, problematische Zeichen und reservierte Gerätenamen sind unzulässig.
Unicode-Dateinamen sind grundsätzlich erlaubt; NFC-/Casefold-Kollisionen werden
einschließlich Verzeichnissen zurückgewiesen. Metadaten und tatsächliche Einträge
müssen zusammenpassen; normalisierende Dateisysteme können handerstellte Unicode-
Pakete einschränken. Der Anwendungsexport vermeidet das durch ASCII-Assetnamen.
MP3/WAV-Endungen werden unabhängig von Großschreibung akzeptiert.

Grenzen: je JSON-Datei 1 MiB, höchstens 50 Assets, 1 GiB pro Asset und insgesamt
5 GiB deklarierte Audiodaten. Ein- und Ausgabe werden zusätzlich beim Lesen/Kopieren
begrenzt. Unbekannte Paket-/Settingsfelder werden abgelehnt; `last_folder` ist im
Paket nur leer oder abwesend zulässig und wird vom Export entfernt. Fremde Dateien
im Paketordner, etwa nachträglich eingefügte Finder-Metadaten, können die Prüfung
blockieren. Das alte Ordnerformat unterstützt ZIP und Mehrdatei-Pools nicht;
lokale Schema-3-Presets unterstützen Audio-Pools. Enthält das aktive Preset einen
Pool mit mehreren Dateien, wird der Export vor der Ordnerauswahl blockiert, auch
bei ausgeblendeten Slots. Kein Teil-Export im alten Format: Der normale ZIP-Export mit Paketversion 3 nimmt Pools vollständig mit. Ein-Datei-Pools werden im alten Format als einzelne Audiozuordnung exportiert. Import
bisheriger Pakete enthält keine Pools und entfernt nur die Poolzuordnungen des
ausdrücklich ersetzten Presets; andere Presets bleiben erhalten.

## Altes Format: Importieren

1. **Soundboard → Alten Paketordner importieren...** wählen und den Paketordner auswählen,
   der `jingleplayer_package.json` enthält. Die aktive Settingsdatei muss bereits
   existieren; bei einer Neuinstallation gegebenenfalls zuerst eine Einstellung speichern.
2. Die vollständige Prüfung abwarten. Die Vorschau nennt die Zahl der Audiodateien
   und belegten Tasten einschließlich ausgeblendeter Plätze.
3. Den Import bestätigen und als Ziel ein neues Preset mit eindeutigem Namen oder ausdrücklich das Ersetzen des aktiven Presets wählen. Andere Presets bleiben unverändert. Abbrechen
   vor dieser Bestätigung ändert weder Wiedergabe noch Einstellungen.
4. Nach Vorbereitung wird die Wiedergabe über die vorhandenen Engine-Methoden
   ohne Fadeout gestoppt. Der Import legt Recoverydaten an, installiert eine
   unabhängige verifizierte Kopie und ersetzt erst danach die aktive JSON-Datei.
5. Nach bestätigter Aktivierung werden Settings und Oberfläche neu geladen.
   Alle 50 Plätze, Farben, Texte, individuelle Lautstärke und Reihenlayout stammen
   aus dem importierten Board. **Fenstergröße, globale Lautstärke und `last_folder`**
   bleiben lokal; die sichtbare Fenstergröße wird durch den Import nicht neu gesetzt.

Die installierten Audiozuweisungen sind native absolute Pfade. Der ursprüngliche
Paketordner kann anschließend verschoben werden; er ist kein Wiedergabe-Verzeichnis.
Die Oberfläche leitet ihre separaten verwalteten Ordner aus dem tatsächlichen
Settingsverzeichnis ab (standardmäßig `~/.jingleplayer`):

```text
~/.jingleplayer/
  jingleplayer_settings.json
  import-staging/.jingleplayer-import-<zufällig>/...
  imported_soundboards/import-<uuid>/
    jingleplayer_package.json
    jingleplayer_settings.json
    Musik/...
  import-recovery/import-<uuid>/
    jingleplayer_settings.json
    recovery.json
```

Die JSON-Datei im Library-Paket behält portable Referenzen für Integritätsprüfungen;
nur die aktive JSON verwendet installierte absolute Pfade. Die GUI entfernt
erfolgreiche Vorbereitungen derzeit nicht automatisch, weil keine öffentliche
Backend-Cleanup-API dafür existiert. Ihr Pfad wird angezeigt. Alte Librarydaten
und Recoverykopien werden nicht automatisch gelöscht.

## Fehler, Parallelzugriffe und Aufbewahrung

Dateioperationen laufen in einem Qt-Worker; Widgets und Audiosteuerung bleiben im
GUI-Thread. Überlappende Paketvorgänge, Einstellungen und Schließen sind während
des Vorgangs gesperrt. Laufende Kopier-/Aktivierungsschritte haben keinen
Abbruchknopf und sollen nicht durch Prozessbeendigung unterbrochen werden.

Assets werden zunächst vollständig geprüft und per Rename ohne Überschreiben
veröffentlicht. Settings werden über eine temporäre Geschwisterdatei, Flush/Fsync
und `os.replace` gewechselt. Vor diesem Wechsel lässt ein Importfehler die bisherigen
Settingsbytes unangetastet; konkurrierende Änderungen anderer Instanzen bleiben
davon ausgenommen. Eine Fingerprintprüfung unmittelbar vor dem Wechsel erkennt
beobachtete Änderungen, schließt aber das Zeitfenster zwischen Prüfung und Replace
nicht. Die aktuelle Anwendung und der Import verwenden dieselbe kurze OS-Sperre über die persistente `.presets.lock`-Datei. Ältere Versionen oder externe Editoren beachten diese Sperre nicht. Für einen
kontrollierten Wechsel andere Instanzen vorher schließen.

Links, Junctions und Reparse-Punkte werden auch in Vorfahren abgelehnt. Das kann
System-Aliasordner wie `/tmp` oder `/var` auf macOS betreffen: einen tatsächlich
kanonischen, linkfreien Ziel-/Quellpfad verwenden; die Sicherheitsprüfung nicht
umgehen. Pfadprüfungen sind keine Sandbox gegen einen anderen Prozess desselben
Benutzers, der Verzeichnisse genau zwischen Prüfung und Zugriff austauscht.
Eine bytegleiche Ersetzung vor Aktivierungsbeginn ist mit den gespeicherten
Inhaltsnachweisen nicht von der Originaldatei unterscheidbar.

Es gibt **keine garantierte Crash-Durabilität oder vollständige Dateisystemtransaktion**.
Ein Absturz kann zusätzliche Recovery-, Library-, Vorbereitungs- oder temporäre
Settingsdateien hinterlassen. Das Backend räumt nur nachgewiesene eigene
Vorbereitungsdaten auf; bei ersetzten/unerwarteten Einträgen verweigert es das
Löschen und nennt den Pfad. Aktivierungsfehler behalten unsichere/neue Daten,
statt möglicherweise bereits referenzierte Audiodateien zu löschen.

Aktivierungszustände:

- **`not_committed`**: Der Import hat Settings nicht gewechselt; die GUI lädt den
  aktuellen Datenträgerstand neu. Bereits gestoppte Wiedergabe startet nicht erneut.
- **`committed`**: Replace wurde bestätigt bzw. die vorgeschlagenen Bytes nach einer
  außergewöhnlichen Replace-Rückgabe gefunden. Das ist kein Schutz vor einem
  weiteren Schreibzugriff einer anderen Instanz.
- **`indeterminate`**: Der Stand ist unklar. Die GUI meldet keinen Erfolg, sperrt
  Speichern und verlangt Schließen und Zustandsprüfung. Kein automatisches Restore.
- **Aktiviert, aber GUI-Reload fehlgeschlagen**: Der Import kann bereits auf dem
  Datenträger aktiv sein. Speichern bleibt auch beim Schließen gesperrt. Nach
  Prüfung neu starten; nicht ungeprüft die Recoverykopie zurückspielen.

## Manuelle Wiederherstellung

1. Alle Jingleplayer-Instanzen schließen und sicherstellen, dass kein Writer mehr
   läuft. Bei unklarem Ausgang zuerst den aktuellen Zustand untersuchen.
2. Aktive Settings sowie relevante Recovery- und Libraryverzeichnisse separat
   sichern. Keine vermeintlich unbenutzten Librarydateien vorschnell löschen.
3. In der gemeldeten Recoverydirectory `recovery.json` lesen. Sie enthält
   `recovery_version: 1`, `settings_path`, `settings_size`, `settings_sha256`,
   `proposed_settings_sha256` und `library_directory`. Die benachbarte
   `jingleplayer_settings.json` enthält die **unveränderten Bytes vor dem Import** (den ganzen lokalen Presetbestand, nicht nur das aktive Board).
4. Größe und SHA-256 der Recovery-JSON mit `settings_size` und `settings_sha256`
   vergleichen. Windows: `Get-FileHash -Algorithm SHA256 -LiteralPath '<Snapshot>'`
   und `(Get-Item -LiteralPath '<Snapshot>').Length`. macOS:
   `shasum -a 256 '<Snapshot>'` und `stat -f %z '<Snapshot>'`.
   Diese Befehle lesen nur; Platzhalter durch den ausdrücklich geprüften Pfad ersetzen.
5. Aktuelle Settings hashen: stimmen sie mit `proposed_settings_sha256` überein,
   sind es die erwarteten Importbytes; mit `settings_sha256` die vorherigen Bytes.
   Bei keinem Treffer von einem anderen/unklaren Stand ausgehen und diesen erhalten.
   Hashgleichheit beweist Integrität zum Snapshot, nicht dessen Vertrauenswürdigkeit.
6. Nur nach ausdrücklicher Entscheidung die geprüfte Snapshotdatei an den
   unabhängig bestätigten aktiven Settingspfad zurückkopieren. Pfade aus Metadaten
   nicht als automatische Schreibanweisung ausführen. Die gesicherte aktuelle Datei
   behalten; erst danach neu starten und Belegungen kontrollieren.

Recovery enthält Einstellungen, **keine Kopie der vorherigen externen Audiodateien**.
Alte absolute Audioziele müssen weiterhin erreichbar sein. Ein Konflikt mit
einem vorhandenen Pre-Preset-Backup blockiert die Umstellung. Ein vorhandenes
`jingleplayer_settings.pre-pyside6.json` wird weder als Import-Recovery verwendet noch überschrieben.
Auch teilweise fehlgeschlagene Recoverydaten bleiben erhalten. Fehlt die Metadatei
oder stimmt der Hash nicht, nicht als automatisch geprüfte Wiederherstellung behandeln.
Es gibt keinen Restore-Button und keinen automatischen Rückwechsel.

## Validierung und Freigabe

Automatische Tests verwenden temporäre Settings/Audiofixturedateien, Qt `offscreen`
und SDL-Dummytreiber. Testdateien sind teilweise beliebige Bytes, keine akustischen
Wiedergabenachweise. Die allgemeine CI ist für Ubuntu/Windows (Python 3.11 und 3.13)
und macOS (Python 3.11) konfiguriert. Der manuelle macOS-Workflow behält native
arm64-/x86_64-Builds und bestehende Artefaktnamen bei. Keine neue Veröffentlichung.
Workflow-Konfiguration ist kein Nachweis eines erfolgreichen nativen CI-Laufs.

Gezielte lokale Prüfung mit bereits vorhandenen Abhängigkeiten:

```text
python -m pytest -q -ra tests/test_packages.py tests/test_portable_gui.py tests/test_pyside6_gui.py
python -m pytest -q -ra --basetemp="<neues beschreibbares temporäres Verzeichnis>" -p no:cacheprovider
git diff --check
git status --short
```

`--basetemp` darf kein Verzeichnis mit wichtigen Daten sein; pytest verwaltet diesen
Inhalt selbst. Auf macOS linkfreie temporäre Pfade verwenden. Die CI benutzt dafür
ein Unterverzeichnis von `runner.temp`. `-ra` protokolliert Skip-Gründe:

- Junctiontests sind Windows-spezifisch; Symlinktests werden bei fehlenden
  Berechtigungen übersprungen (Windows benötigt häufig Entwicklermodus/Rechte).
- Tests tatsächlich Windows-ungültiger Quelldateinamen laufen nur auf POSIX.
- Ein Test für verschiedene NFC/NFD-Dateinamen prüft die Dateisystemfähigkeit und
  überspringt Dateisysteme, die beide Schreibweisen auf denselben Eintrag abbilden.
- Solche Skips sind keine erfolgreiche native Prüfung des übersprungenen Falls.

Vor einer Freigabe auf **Windows und beiden macOS-Architekturen** manuell prüfen:

- Native Ordner-/Namensdialoge, Unicode/Leerzeichen, vorhandenes Ziel und Abbrechen.
- Export mit sichtbaren/versteckten fehlenden Dateien, danach Import auf dem anderen
  Betriebssystem ohne manuelle Dateineuzuweisung.
- Echte MP3/WAV-Wiedergabe vor/nach Import, Stop, Lautstärke, Neustart und Schließen.
- Erhaltene lokale Fenstergröße, Gesamtlautstärke und Audioordner; alle 50 Slots.
- Paketpfade auf case-sensitiven und case-insensitiven Volumes, externe Datenträger,
  macOS-Systemaliases/Unicode-Normalisierung, Berechtigungen und Platzmangel.
- Paketierte Windows-EXE/macOS-App außerhalb des Repository-Arbeitsverzeichnisses,
  Recoveryprüfung und kontrollierter Umgang mit unklarem Aktivierungsstatus.

Bis diese Ergebnisse tatsächlich vorliegen, ist native macOS-/plattformübergreifende
Freigabereife nicht bestätigt. Auch erfolgreiche Dummy-/Offscreen-Tests ersetzen
weder echte Audiohardware noch native Dialog- und Bundletests.

## Release Candidate 1.1.0-rc1

Anwendungsfassung, Settings-Schema 3 und Paketformat 3 sind unabhängig. Der neue manuelle Release-Workflow erzeugt versionierte Plattformarchive mit SHA256 ohne Veröffentlichung. Aktueller Build-/Abnahmestand und akzeptiertes macOS-/Linux-Restrisiko: [RELEASE.md](RELEASE.md).
