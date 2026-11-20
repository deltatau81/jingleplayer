"""Isolated frozen runtime check; no native GUI or hardware audio claim."""
import json
import tempfile
from pathlib import Path


def run(report_path):
    import pygame
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage
    import jingleplayer_logic as logic
    from jingleplayer_gui_pyside6 import resource_path, create_main_window
    from jingleplayer_version import APP_VERSION
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="jingleplayer-frozen-") as temp:
        temp = str(Path(temp).resolve())  # macOS /var and /tmp are aliases.
        logic.data_dir = Path(temp)
        logic.settings_file = Path(temp) / "jingleplayer_settings.json"
        window = create_main_window()
        assert window is not None
        assert Path(resource_path("HELP.md")).is_file()
        assert Path(resource_path("assets/jingleplayer.ico")).is_file()
        document = logic.get_preset_settings()
        assert document["schema_version"] == 3
        result = logic.save_settings(document)
        assert result["success"], result
        assert logic.settings_file.is_file()
        assert logic.load_settings()["schema_version"] == 3
        image = QImage(4, 4, QImage.Format_RGB32)
        image.fill(0)
        image_path = Path(temp) / "background.png"
        assert image.save(str(image_path))
        assert not QImage(str(image_path)).isNull()
        import wave
        import jingleplayer_media_packages as media
        import jingleplayer_preset_storage as storage
        audio = Path(temp) / "sample.wav"
        with wave.open(str(audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"\0\0" * 100)
        preset = document["presets"][0]
        preset["background_image"] = str(image_path)
        preset["buttons"]["paths"][0] = str(audio)
        preset["audio_pools"] = {"1": {"audio_pool": [str(audio)],
            "audio_pool_mode": "manual", "selected_audio": str(audio)}}
        archive = Path(temp) / "soundboard.zip"
        media.export_archive(document, archive, source_base=Path(temp), name="Smoke")
        installed = media.import_archive(archive, logic.settings_file)
        assert installed.outcome == "committed"
        assert installed.installed_directory.parent.name == "imported_soundboards"
        reloaded = storage.load_preset_settings(logic.settings_file).data
        imported = reloaded["presets"][-1]
        assert Path(imported["background_image"]).is_file()
        pool = imported["audio_pools"]["1"]
        assert pool["audio_pool_mode"] == "manual"
        assert Path(pool["selected_audio"]).is_file()
        pygame.mixer.Sound(pool["selected_audio"])
        assert pygame.mixer.get_init() is not None
        window.close()
        app.processEvents()
    Path(report_path).write_text(json.dumps({"version": APP_VERSION, "success": True}), encoding="utf-8")
    pygame.quit()
    return 0
