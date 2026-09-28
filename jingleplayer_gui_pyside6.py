"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSlider,
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
    """Clickable visual representation of one configured jingle."""

    clicked = Signal(int)

    def __init__(self, index, text, background_color, parent=None):
        super().__init__(parent)
        self.jingle_index = index
        self.jingle_text = str(text)
        self.jingle_color = str(background_color)
        self.playing = False

        self.display_color = QColor(self.jingle_color)
        if not self.display_color.isValid():
            self.display_color = QColor("#f0f0f0")

        self.setObjectName("jingleTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.label = QLabel(self.jingle_text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.label.setStyleSheet(
            f"color: {contrasting_text_color(self.display_color.name())};"
            "font-weight: 600;"
            "background: transparent;"
        )
        layout.addWidget(self.label)

    def _apply_style(self):
        border = "3px solid #ffffff" if self.playing else "1px solid rgba(0, 0, 0, 45)"
        self.setStyleSheet(
            "QFrame#jingleTile {"
            f"background-color: {self.display_color.name()};"
            f"border: {border};"
            "border-radius: 8px;"
            "}"
        )

    def set_playing(self, playing):
        self.playing = bool(playing)
        self._apply_style()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.jingle_index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


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
        button_settings = current_settings.get("buttons", {})
        self.jingle_paths = button_settings.get("paths", [])
        self.fadeout_duration = current_settings.get("fadeout_duration", 0)
        self._build_jingle_layout(current_settings)

        self.sound_end_timer = QTimer(self)
        self.sound_end_timer.setInterval(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS)
        self.sound_end_timer.timeout.connect(self._poll_sound_end)
        self.sound_end_timer.start()

    def _build_jingle_layout(self, current_settings):
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        volume_layout = QHBoxLayout()
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(8)

        volume_label = QLabel("Lautstärke", central_widget)
        volume_layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, central_widget)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(current_settings["volume"]))
        volume_layout.addWidget(self.volume_slider, 1)

        self.volume_value_label = QLabel(f"{self.volume_slider.value()} %", central_widget)
        self.volume_value_label.setMinimumWidth(42)
        self.volume_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        volume_layout.addWidget(self.volume_value_label)
        main_layout.addLayout(volume_layout)

        self.volume_slider.valueChanged.connect(self._handle_volume_change)

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
                tile = JingleTile(next_index + 1, texts[next_index], colors[next_index], row_widget)
                tile.clicked.connect(self._handle_tile_click)
                row_layout.addWidget(tile, 1)
                self.jingle_tiles.append(tile)
                next_index += 1

            self.row_widgets.append(row_widget)
            self.row_layouts.append(row_layout)
            main_layout.addWidget(row_widget, 1)

        self.setCentralWidget(central_widget)

    def _handle_tile_click(self, index):
        tile = self.jingle_tiles[index - 1]
        if tile.playing:
            result = jingleplayer_logic.stop_jingle(index, self.fadeout_duration)
            indicator_update = result.get("indicator_update", {}) if result else {}
            if indicator_update.get("playing") is False:
                tile.set_playing(False)
            return

        jingle_path = self.jingle_paths[index - 1] if index <= len(self.jingle_paths) else ""
        result = jingleplayer_logic.play_jingle(index, jingle_path, self.fadeout_duration)
        if result and result.get("success") is True:
            tile.set_playing(True)

    def _poll_sound_end(self):
        indicator_updates = jingleplayer_logic.check_sound_end()
        for update in indicator_updates or []:
            index = update["index"]
            if 1 <= index <= len(self.jingle_tiles):
                self.jingle_tiles[index - 1].set_playing(update["playing"])

    def _handle_volume_change(self, volume_percent):
        self.volume_value_label.setText(f"{volume_percent} %")
        jingleplayer_logic.set_volume_logic(volume_percent)
        jingleplayer_logic.save_settings(jingleplayer_logic.get_current_settings())

    def closeEvent(self, event):
        self.sound_end_timer.stop()
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
