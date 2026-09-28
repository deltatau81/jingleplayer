# Audio-Engine und Tests

## Analysierter Ausgangszustand

Die GUI rief beim Linksklick `play_jingle()` auf und übernahm dessen
`indicator_update`; ein 100-ms-Timer leitete die Ergebnisse von
`check_sound_end()` an die Indikatoren weiter. Der alte Cache prüfte nach einem
Dateipfad, speicherte Sounds aber unter dem Button-Index. Toggle und Stop
verließen sich auf `Sound.get_num_channels()` und `Sound.fadeout()`, wodurch
nicht der konkrete Button-Channel maßgeblich war. Endevents wurden als
`USEREVENT + index` erzeugt und jedes Event ab `USEREVENT` wurde ungeprüft als
Jingle-Ende behandelt. Die globale Lautstärke aktualisierte bereits laufende
Channels unter Berücksichtigung der Button-dB, enthielt die Umrechnung aber
mehrfach. Settings ohne `buttons.volumes` wurden bereits auf eine passende
Null-Liste migriert; dieses Format bleibt erhalten.

## Architektur

```text
Button-Index
    |
    v
Playback-State (playing_channels: Button -> Channel)
    |
    v
Pygame-Channel
    |
    v
Sound-Objekt (sounds: normalisierter Dateipfad -> Sound)
```

Playback-State und Sound-Cache sind bewusst getrennt: Ein Sound kann von
mehreren Buttons auf unterschiedlichen Channels wiedergegeben werden. Der
Button-Index identifiziert einen laufenden Channel, nicht das Sound-Objekt.

## Channel-Lifecycle und Sound-Cache

`play_jingle()` validiert den Pfad und verwendet einen normalisierten absoluten
Dateipfad als Cache-Key (`sounds: path -> Sound`). Ein freier Mixer-Channel wird
dem Button separat in `playing_channels: button_index -> Channel` zugeordnet.
Damit können verschiedene Buttons, auch mit derselben Datei, gleichzeitig auf
unabhängigen Channels laufen.

Ein erneuter Klick auf denselben aktiven Button ruft `Channel.fadeout()` mit der
konfigurierten Dauer auf. Nur dieser Channel wird beeinflusst; der Button wird
sofort als inaktiv gemeldet. Beim natürlichen Ende ordnet eine eigene, gültige
Pygame-Endevent-ID das Ereignis exakt der gestarteten Wiedergabe zu. Unbekannte
und veraltete Events werden ignoriert, sodass ein schnelles Stoppen und erneutes
Starten keinen neuen Lauf beenden kann.

`check_sound_end()` verarbeitet alle aktuell wartenden Pygame-Events. Bekannte
Endevents entfernen die konkrete Button-/Channel- und Event-Zuordnung; fremde
Events werden ignoriert. Beim manuellen Stop wird die Zuordnung direkt nach dem
Start des Channel-Fadeouts bereinigt.

Der Mixer wird zentral mit 44,1 kHz, 16 Bit signed, Stereo und einem Buffer von
512 Samples initialisiert. Es werden bewusst 50 Mixer-Channels bereitgestellt:
einer je maximal konfigurierbarem Button. Ist trotzdem kein Channel frei, wird
ein Fehler zurückgegeben und kein Playing-Indikator gesetzt.

## Lautstärke

`calculate_effective_volume(global_percent, button_db)` berechnet
`10 ** (dB / 20) * global_percent / 100` und begrenzt das Resultat auf 0,0 bis
1,0. Pygame-Channels können nicht über 1,0 verstärken. Positive dB-Werte werden
daher bei hoher globaler Lautstärke abgeschnitten; es findet bewusst keine
zusätzliche DSP-Verstärkung statt. Globale und individuelle Änderungen werden
auf bereits laufende, dem jeweiligen Button zugeordnete Channels angewendet.

## Testarchitektur

Leere und nicht unterstützte Pfade, fehlendes Pygame, Lade-/Playback-Fehler und
fehlende freie Channels liefern strukturierte Fehler an die unveränderte
GUI-Schnittstelle. Unit-Tests ersetzen Sound, Channel, Mixer und Events komplett;
sie benötigen weder Audiogerät noch hörbare Ausgabe.

Die Unit-Tests verwenden Fake-Sounds, Fake-Channels, einen Fake-Mixer und
kontrollierte Events. Sie benötigen keine Audiohardware. GitHub Actions führt
nur diese automatisierten Tests mit SDL-Dummy-Treibern aus; der interaktive
Smoke-Test ist ausdrücklich nicht Teil der CI.

Abhängigkeiten installieren und automatisierte Tests ausführen:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -v
python -m pytest --cov=jingleplayer_logic --cov-report=term-missing
```

## Manueller Windows-Audio-Smoke-Test

Der reale Audiotest verwendet echte Windows-Audiohardware und wird bewusst
nicht von pytest oder der CI ausgeführt. Er erzeugt hörbare kurze
WAV-Testtöne zur Laufzeit in einem temporären Verzeichnis, verwendet die
produktiven Audiofunktionen und entfernt die Dateien beim Beenden automatisch.
Optional kann ein lokaler MP3-Pfad eingegeben werden; eine MP3-Datei gehört
nicht zum Repository.

Unter Windows im Verzeichnis `jingleplayer` starten:

```powershell
python tests/manual_audio_smoke.py
```

Der Test erzeugt hörbare Signale. Vor dem Start eine moderate
Systemlautstärke einstellen und die zehn interaktiven Schritte anhand der
Konsolenausgaben bestätigen. Technische Checks und subjektive Hörprüfungen
werden in der Abschlussübersicht getrennt gezählt.
