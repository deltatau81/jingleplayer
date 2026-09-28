"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow


def resource_path(relative_path):
    """Return a resource path for source runs and future PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


def create_main_window():
    """Create the minimal PySide6 main window without starting the event loop."""
    window = QMainWindow()
    window.setWindowTitle("Jingleplayer")

    icon_path = resource_path(Path("assets") / "jingleplayer.ico")
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))

    return window


def main():
    app = QApplication(sys.argv)
    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
