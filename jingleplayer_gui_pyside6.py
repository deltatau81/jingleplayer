"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import jingleplayer_logic


def resource_path(relative_path):
    """Return a resource path for source runs and future PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


def contrasting_text_color(background_color):
    """Return a readable text color without modifying the stored color."""
    color = QColor(str(background_color))
    if not color.isValid():
        color = QColor("#f0f0f0")
    brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
    return "#111111" if brightness >= 150 else "#ffffff"


class JingleTile(QFrame):
    """Read-only visual representation of one configured jingle."""

    def __init__(self, index, text, background_color, parent=None):
        super().__init__(parent)
        self.jingle_index = index
        self.jingle_text = str(text)
        self.jingle_color = str(background_color)

        display_color = QColor(self.jingle_color)
        if not display_color.isValid():
            display_color = QColor("#f0f0f0")

        self.setObjectName("jingleTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(64)
        self.setStyleSheet(
            "QFrame#jingleTile {"
            f"background-color: {display_color.name()};"
            "border: 1px solid rgba(0, 0, 0, 45);"
            "border-radius: 8px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.label = QLabel(self.jingle_text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            f"color: {contrasting_text_color(display_color.name())};"
            "font-weight: 600;"
            "background: transparent;"
        )
        layout.addWidget(self.label)


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

        self.row_widgets = []
        self.row_layouts = []
        self.jingle_tiles = []
        self._build_jingle_layout(current_settings)

    def _build_jingle_layout(self, current_settings):
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        button_settings = current_settings.get("buttons", {})
        texts = button_settings.get("texts", [])
        colors = button_settings.get("colors", [])
        per_row = button_settings.get("per_row", [])
        available_count = min(len(texts), len(colors))
        next_index = 0

        for row_index in range(jingleplayer_logic.DEFAULT_BUTTON_ROW_COUNT):
            row_widget = QWidget(central_widget)
            row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            requested_count = per_row[row_index] if row_index < len(per_row) else 0
            try:
                requested_count = max(0, min(int(requested_count), jingleplayer_logic.DEFAULT_BUTTONS_PER_ROW_COUNT))
            except (TypeError, ValueError):
                requested_count = 0

            for _ in range(requested_count):
                if next_index >= available_count:
                    break
                tile = JingleTile(next_index, texts[next_index], colors[next_index], row_widget)
                row_layout.addWidget(tile, 1)
                self.jingle_tiles.append(tile)
                next_index += 1

            self.row_widgets.append(row_widget)
            self.row_layouts.append(row_layout)
            main_layout.addWidget(row_widget, 1)

        self.setCentralWidget(central_widget)

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
