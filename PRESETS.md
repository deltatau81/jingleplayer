# Presets – Schema 3 und Betrieb

## Bedienung

Die Auswahl im Hauptfenster und das Menü **Presets** verwalten unabhängige Boards:

- **Neu…** erzeugt 50 leere Audiozuweisungen mit den bisherigen Standardwerten und aktiviert das Preset.
- **Duplizieren…** kopiert alle Daten einschließlich versteckter Slots in eine unabhängige Kopie mit neuer UUID; Audio wird nicht kopiert.
- **Umbenennen…** ändert den Anzeigenamen, nicht die UUID.
- **Löschen…** erfordert Bestätigung, schützt das letzte Preset und fragt beim aktiven Preset einen Nachfolger ab. Audio- und Librarydateien bleiben erhalten.
- Die Auswahl speichert das aktive Preset dauerhaft und beendet alte Wiedergabe sofort, einschließlich bereits laufender Fadeouts. Audio startet nach Fehlern nicht automatisch erneut.

Dialoge vor dem Wechsel speichern oder schließen. Namen sind nach Unicode-Normalisierung und Casefold eindeutig. Bei einem gescheiterten Wechsel bleiben die vorherige Auswahl und Belegungen erhalten; bereits erfolgreich gesicherte Änderungen bleiben gespeichert. Nach einem bestätigten Commit mit fehlgeschlagenem Reload wird Speichern gesperrt und ein Neustart verlangt.

## Daten und Migration

Eine Hauptdatei: `~/.jingleplayer/jingleplayer_settings.json`, lokal `schema_version: 3`.

- Global: `window_size`, `volume`, `last_folder`.
- Dokument: `active_preset_id`, nichtleere `presets`-Liste.
- Pro Preset: UUID, Name, `buttons.texts/colors/paths/volumes` mit jeweils genau 50 Einträgen, fünf `per_row`-Werte, `fadeout_duration`, `button_height`.

Schema 2 wird beim Laden verlustfrei im Speicher migriert. Unterstützte unversionierte/Schema-1-Daten benutzen die kontrollierte Legacy-Normalisierung. Defekte, widersprüchliche oder unbekannte Felder werden nicht still entfernt; ein Fehler blockiert den Start/Speichern. Fehlende Standardwerte werden nur bei unterstützten alten Daten ergänzt. Bestehende Pfadstrings bleiben unverändert, einschließlich relativer Pfade mit ihrer bisherigen Wiedergabebasis.

Starten und unverändertes Schließen schreibt eine bestehende Datei nicht um. Der erste tatsächliche Save erzeugt vor der Umstellung ein exaktes `jingleplayer_settings.json.pre-presets.<SHA256>.json`. Ein identisches Backup wird wiederverwendet, ein abweichendes blockiert den Save. Pre-PySide6-Backups werden nicht verändert. Wiederholte Starts erzeugen keine zusätzlichen Standard-Presets. Die alte v1.0.0-Anwendung kann die neue Schema-3-Datei nicht lesen.

## Persistenz, Konflikte und Wiederherstellung

Alle aktuellen Anwendungswriter und Paketaktivierungen verwenden `jingleplayer_preset_storage`: Validierung, kurze OS-Sperre, Fingerprintvergleich, temporäre Geschwisterdatei, Flush/Fsync, erneuter Vergleich und `os.replace`. Die persistente leere `.presets.lock`-Datei ist keine zweite Settingsquelle und darf bei laufenden Instanzen nicht gelöscht werden. Gelöschte/ersetzte/geänderte Settings werden als Konflikt abgewiesen. Es gibt kein automatisches Wiederholen mit einem neu geladenen Token, das fremde Änderungen überschreiben könnte.

Ältere Anwendungsversionen und externe Editoren beachten die Sperre nicht. Gegenüber ihnen bleibt eine Check-to-Replace-Restlücke. Pfadprüfungen erfordern stabile vertrauenswürdige Vorfahren; kein Schutz gegen jeden feindlichen Prozess desselben Benutzers. Keine Garantie vollständiger Crash-Durabilität oder einer Dateisystemtransaktion über Settings, Library und Backups.

Bei `saved`/`indeterminate` nach einem Speicherfehler blockiert die Anwendung weitere Saves einschließlich Close-Save. Alle Instanzen schließen, aktuellen Zustand separat sichern und Datenträgerstand prüfen; nicht ungeprüft eine alte Datei zurückspielen. Für einen bewussten Rückwechsel Backupgröße/Hash prüfen (Hash steht im Backupnamen), den aktiven Pfad unabhängig bestätigen und erst dann die Sicherung zurückkopieren. Recovery stellt Settings wieder her, keine alten externen Audiodateien. Teilbackups und unsichere Restdaten werden erhalten und gemeldet.

## Portable Pakete

Paketversion 1 und dessen Schema-2-Boarddaten bleiben unverändert. Export umfasst ausschließlich das aktive Preset mit allen 50 Slots. Globale Werte werden für die Kompatibilität mitgegeben; der Empfänger behält seine lokalen Werte. Fehlende Dateien können weiterhin ausdrücklich nur in der Exportkopie ausgelassen werden.

Import bietet **Als neues Preset** (neue UUID, eindeutiger vom Benutzer gewählter Name) oder **Aktives Preset ersetzen** (bestehende lokale UUID und Name bleiben erhalten). Andere Presets werden nie durch den einzelnen Import ersetzt. Die bestehende Vorschau, Assetprüfung, SHA-256-Hashes, Link-/Junction-Abweisung und sichere Libraryveröffentlichung bleiben erhalten.

Vor dem Import werden aktuelle bestätigte Änderungen gesichert und das aktuelle Persistenztoken festgehalten. Spätere konkurrierende Saves führen zum Konflikt. Der Import sichert die kompletten vorherigen Settingsbytes unter `import-recovery/import-<uuid>/` und prüft Recovery und installierte Assets noch unmittelbar vor dem Settingscommit unter der Sperre. Bei Fehlern vor Commit bleibt das Dokument unverändert; unsichere/neue Assets und Recoverydaten werden nicht blind gelöscht oder automatisch zurückgespielt. Die GUI lädt nach bestätigtem Commit Dokument und aktive Projektion neu.

Details zur Wiederherstellung und zu verbleibenden Vorbereitungspfaden: [Portable Soundboards](PORTABLE_SOUNDBOARDS.md). ZIP und Jingle-Pools sind weiterhin nicht implementiert.

## Validierung

Die Tests decken reine Migration/CRUD, atomare Persistenz, OS-Locks, konkurrierende Writer, Laufzeit- und GUI-CRUD, versteckte Slots, Neustart, Import als neues Preset und Ersetzen sowie aktiven Export und Fehlergrenzen ab. Echte Windows-/macOS-Dialoge, Hardwareaudio einschließlich hörbarer Fadeouts, paketierte EXE/App und native Dateisystemfälle benötigen zusätzlich manuelle Tests. Lokale Windows-Dummy-/Offscreen-Tests sind kein Nachweis eines erfolgreichen macOS-/Linux-CI-Laufs.
