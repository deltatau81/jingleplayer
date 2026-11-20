# v1.1.0-rc1 – Entwurf, unveröffentlicht

## Neue Funktionen

Mehrere unabhängige Presets mit individuellen Hintergrundbildern und
halbtransparenten Buttons mit farbigen Rahmen. Audio-Pools pro Button bieten
`sequential`, `random` und `manual`; die manuelle Auswahl bleibt nach Neustart
bestehen und lässt sich direkt am Button ändern.

## Verbesserungen

Portable ZIP-Medienpakete transportieren sämtliche Presets, versteckte Slots,
vollständige Pools, manuelle Auswahl und Hintergrundbilder. Import installiert
Medien dauerhaft unter `imported_soundboards/`; Quellarchive werden danach nicht
benötigt. Wiederholte Imports erhalten eigene Ordner und eindeutige Presetnamen.
Ein vollständiger Export bricht bei fehlenden Medien ab.

## Kompatibilität

Anwendung 1.1.0-rc1, Settings-Schema 3 und Paketformat 3 sind unabhängig.
Alte Ordnerpakete (Version 1 / Settings-Schema 2) bleiben unterstützt.
Migration sichert frühere Settings vor dem ersten tatsächlichen Speichern.
Version 1.0.0 kann Settings-Schema 3 nicht lesen.

## Installation

Geplante Actions-Artefakte: Windows-x86_64-ZIP, macOS-arm64-/x86_64-ZIP mit `.app`
und Linux-x86_64-tar.gz, jeweils mit SHA256. Keine separate Python-Installation.
Alle Builds ohne Herausgeberzertifikat, macOS nicht notarisiert.
Voraussetzungen und Download-/Prüfanleitung: [RELEASE.md](RELEASE.md).

## Bekannte Einschränkungen

Keine neue öffentliche Veröffentlichung. Native macOS-/Linux-GUI- und Audiotests
stehen aus und sind akzeptiertes Planungsrisiko. Keine garantierte vollständige
Crash-Durabilität; Recovery und Medien nicht ungeprüft löschen.

## Teststatus

Ausgangsabnahme laut Auftrag: 805 Tests bestanden, 21 übersprungen; bestehende
Windows-/Ubuntu-/macOS-CI erfolgreich; Phase 18D Windows manuell 9/9 bestanden.
Diese Angaben sind historische Vorgaben, keine erneute RC-Buildabnahme.
Aktuelle lokale Ergebnisse und ausstehende Plattformprüfungen: [RELEASE.md](RELEASE.md).
Offscreen-/Dummytests ersetzen keine native GUI oder echte Audiowiedergabe.
