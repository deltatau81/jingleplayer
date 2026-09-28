"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

import jingleplayer_logic


def resource_path(relative_path):
    """Return a resource path for source runs and future PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


class JingleplayerMainWindow(QMainWindow):
    """Minimal main window backed by the existing Jingleplayer settings."""

    def __init__(self, current_settings):
        super().__init__()
        self.setWindowTitle("Jingleplayer")

        window_size = current_settings["window_size"]
        self.resize(int(window_size[0]), int(window_size[1]))

        icon_path = resource_path(Path("assets") / "jingleplayer.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def closeEvent(self, event):
        current_settings = jingleplayer_logic.get_current_settings()
        current_settings["window_size"] = [self.width(), self.height()]
        jingleplayer_logic.save_settings(current_settings)
        super().closeEvent(event)


def create_main_window():
    """Initialize settings once and create the PySide6 main window."""
    jingleplayer_logic.initialize_settings()
    current_settings = jingleplayer_logic.get_current_settings()
    window = JingleplayerMainWindow(current_settings)

    return window


def main():
    app = QApplication(sys.argv)
    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
