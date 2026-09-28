"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import jingleplayer_logic

MAX_FADEOUT_DURATION_MS = 2_147_483_647
MIN_BUTTON_HEIGHT = 1
MAX_BUTTON_HEIGHT = 10


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
    edit_requested = Signal(int)

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

    def update_content(self, text, background_color):
        self.jingle_text = str(text)
        self.jingle_color = str(background_color)
        self.display_color = QColor(self.jingle_color)
        if not self.display_color.isValid():
            self.display_color = QColor("#f0f0f0")
        self.label.setText(self.jingle_text)
        self.label.setStyleSheet(
            f"color: {contrasting_text_color(self.display_color.name())};"
            "font-weight: 600;"
            "background: transparent;"
        )
        self._apply_style()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.jingle_index)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self.rect().contains(event.position().toPoint()):
            self.edit_requested.emit(self.jingle_index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class JingleEditDialog(QDialog):
    """Temporary, read-only-to-settings editor prepared for Phase 6B."""

    def __init__(self, text, color, path, volume_db, last_folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jingle bearbeiten")
        self.color_value = str(color)
        self.last_folder = str(last_folder)
        self.selected_folder = None

        form_layout = QFormLayout()

        self.name_edit = QLineEdit(str(text), self)
        form_layout.addRow("Name", self.name_edit)

        path_widget = QWidget(self)
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit(str(path), path_widget)
        self.browse_button = QPushButton("Durchsuchen...", path_widget)
        self.browse_button.clicked.connect(self._browse_audio_file)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.browse_button)
        form_layout.addRow("Audiodatei", path_widget)

        self.color_button = QPushButton(self.color_value, self)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_preview()
        form_layout.addRow("Farbe", self.color_button)

        self.volume_spin = QSpinBox(self)
        self.volume_spin.setRange(-10, 10)
        self.volume_spin.setSuffix(" dB")
        self.volume_spin.setValue(int(volume_db))
        form_layout.addRow("Individuelle Lautstärke", self.volume_spin)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Speichern")
        self.save_button.setEnabled(True)
        self.cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.setText("Abbrechen")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    def _browse_audio_file(self):
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Audiodatei auswählen",
            self.last_folder,
            "Audiodateien (*.mp3 *.wav)",
        )
        if selected_path:
            self.path_edit.setText(selected_path)
            self.selected_folder = str(Path(selected_path).parent)

    def _choose_color(self):
        initial_color = QColor(self.color_value)
        selected_color = QColorDialog.getColor(initial_color, self, "Jingle-Farbe auswählen")
        if selected_color.isValid():
            self.color_value = selected_color.name()
            self._update_color_preview()

    def _update_color_preview(self):
        display_color = QColor(self.color_value)
        if not display_color.isValid():
            display_color = QColor("#f0f0f0")
        self.color_button.setText(self.color_value)
        self.color_button.setStyleSheet(
            f"background-color: {display_color.name()};"
            f"color: {contrasting_text_color(display_color.name())};"
        )

    def get_values(self):
        return {
            "text": self.name_edit.text(),
            "color": self.color_value,
            "path": self.path_edit.text(),
            "volume_db": self.volume_spin.value(),
            "selected_folder": self.selected_folder,
        }


class SettingsDialog(QDialog):
    """Application settings for audio and the visible jingle layout."""

    def __init__(self, fadeout_duration, per_row, button_height, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")

        audio_group = QGroupBox("Audio", self)
        audio_layout = QFormLayout(audio_group)
        self.fadeout_spin = QSpinBox(audio_group)
        self.fadeout_spin.setRange(0, MAX_FADEOUT_DURATION_MS)
        self.fadeout_spin.setSingleStep(1)
        self.fadeout_spin.setSuffix(" ms")
        self.fadeout_spin.setValue(int(fadeout_duration))
        audio_layout.addRow("Fadeout", self.fadeout_spin)

        layout_group = QGroupBox("Layout", self)
        layout_form = QFormLayout(layout_group)
        self.per_row_spins = []
        for row_index in range(jingleplayer_logic.DEFAULT_BUTTON_ROW_COUNT):
            row_spin = QSpinBox(layout_group)
            row_spin.setRange(0, jingleplayer_logic.DEFAULT_BUTTONS_PER_ROW_COUNT)
            row_spin.setValue(int(per_row[row_index]))
            layout_form.addRow(f"Jingles in Reihe {row_index + 1}", row_spin)
            self.per_row_spins.append(row_spin)

        self.button_height_spin = QSpinBox(layout_group)
        self.button_height_spin.setRange(MIN_BUTTON_HEIGHT, MAX_BUTTON_HEIGHT)
        self.button_height_spin.setValue(int(button_height))
        layout_form.addRow("Button-/Tilehöhe", self.button_height_spin)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.addWidget(audio_group)
        dialog_layout.addWidget(layout_group)
        dialog_layout.addWidget(self.button_box)

    def _validate_and_accept(self):
        if sum(spin.value() for spin in self.per_row_spins) == 0:
            QMessageBox.warning(
                self,
                "Ungültiges Layout",
                "Mindestens eine Reihe muss einen Jingle enthalten.",
            )
            return
        self.accept()

    def get_values(self):
        return {
            "fadeout_duration": self.fadeout_spin.value(),
            "per_row": [spin.value() for spin in self.per_row_spins],
            "button_height": self.button_height_spin.value(),
        }


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
        self.jingle_texts = button_settings.get("texts", [])
        self.jingle_colors = button_settings.get("colors", [])
        self.jingle_paths = button_settings.get("paths", [])
        self.jingle_volumes = button_settings.get("volumes", [])
        self.last_folder = current_settings.get("last_folder", "")
        self.fadeout_duration = current_settings.get("fadeout_duration", 0)
        self.buttons_per_row = list(button_settings.get("per_row", []))
        self.button_height = int(current_settings.get("button_height", 2))
        self._build_main_layout(current_settings)

        self.sound_end_timer = QTimer(self)
        self.sound_end_timer.setInterval(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS)
        self.sound_end_timer.timeout.connect(self._poll_sound_end)
        self.sound_end_timer.start()

    def _build_main_layout(self, current_settings):
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

        self.settings_button = QPushButton("Einstellungen", central_widget)
        self.settings_button.clicked.connect(self._open_settings_dialog)
        volume_layout.addWidget(self.settings_button)
        main_layout.addLayout(volume_layout)

        self.volume_slider.valueChanged.connect(self._handle_volume_change)

        self.tile_layout = QVBoxLayout()
        self.tile_layout.setContentsMargins(0, 0, 0, 0)
        self.tile_layout.setSpacing(8)
        main_layout.addLayout(self.tile_layout, 1)
        self.setCentralWidget(central_widget)
        self._rebuild_jingle_layout()

    def _rebuild_jingle_layout(self):
        for row_widget in self.row_widgets:
            self.tile_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self.row_widgets = []
        self.row_layouts = []
        self.jingle_tiles = []

        available_count = min(len(self.jingle_texts), len(self.jingle_colors))
        playing_indices = set(jingleplayer_logic.get_playing_indices())
        next_index = 0

        for row_index in range(jingleplayer_logic.DEFAULT_BUTTON_ROW_COUNT):
            row_widget = QWidget(self.centralWidget())
            row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            requested_count = self.buttons_per_row[row_index] if row_index < len(self.buttons_per_row) else 0
            try:
                requested_count = max(0, min(int(requested_count), jingleplayer_logic.DEFAULT_BUTTONS_PER_ROW_COUNT))
            except (TypeError, ValueError):
                requested_count = 0

            for _ in range(requested_count):
                if next_index >= available_count:
                    break
                tile = JingleTile(
                    next_index + 1,
                    self.jingle_texts[next_index],
                    self.jingle_colors[next_index],
                    row_widget,
                )
                tile.setMinimumHeight(48 + (self.button_height - 1) * 16)
                tile.set_playing(next_index + 1 in playing_indices)
                tile.clicked.connect(self._handle_tile_click)
                tile.edit_requested.connect(self._open_jingle_editor)
                row_layout.addWidget(tile, 1)
                self.jingle_tiles.append(tile)
                next_index += 1

            self.row_widgets.append(row_widget)
            self.row_layouts.append(row_layout)
            self.tile_layout.addWidget(row_widget, 1)

    def _handle_tile_click(self, index):
        if not 1 <= index <= len(self.jingle_tiles):
            return
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

    def _open_jingle_editor(self, index):
        list_index = index - 1
        dialog = JingleEditDialog(
            self.jingle_texts[list_index],
            self.jingle_colors[list_index],
            self.jingle_paths[list_index],
            self.jingle_volumes[list_index],
            self.last_folder,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.get_values()
        current_settings = jingleplayer_logic.get_current_settings()
        button_settings = current_settings["buttons"]
        button_settings["texts"][list_index] = values["text"]
        button_settings["colors"][list_index] = values["color"]
        button_settings["paths"][list_index] = values["path"]

        jingleplayer_logic.update_settings_data(
            button_settings["texts"],
            button_settings["colors"],
            button_settings["paths"],
            button_settings["per_row"],
            current_settings["fadeout_duration"],
            current_settings["button_height"],
            current_settings["window_size"],
            current_settings["volume"],
        )
        jingleplayer_logic.set_button_volume(index, values["volume_db"])
        if values["selected_folder"] is not None:
            jingleplayer_logic.set_last_folder(values["selected_folder"])

        updated_settings = jingleplayer_logic.get_current_settings()
        updated_buttons = updated_settings["buttons"]
        self.jingle_texts = updated_buttons["texts"]
        self.jingle_colors = updated_buttons["colors"]
        self.jingle_paths = updated_buttons["paths"]
        self.jingle_volumes = updated_buttons["volumes"]
        self.last_folder = updated_settings["last_folder"]

        self.jingle_tiles[list_index].update_content(values["text"], values["color"])
        jingleplayer_logic.save_settings(updated_settings)

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

    def _open_settings_dialog(self):
        current_settings = jingleplayer_logic.get_current_settings()
        dialog = SettingsDialog(
            current_settings["fadeout_duration"],
            current_settings["buttons"]["per_row"],
            current_settings["button_height"],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.get_values()
        self._save_application_settings(
            values["fadeout_duration"],
            values["per_row"],
            values["button_height"],
        )

    def _save_application_settings(self, fadeout_duration, per_row, button_height):
        current_settings = jingleplayer_logic.get_current_settings()
        button_settings = current_settings["buttons"]
        jingleplayer_logic.update_settings_data(
            button_settings["texts"],
            button_settings["colors"],
            button_settings["paths"],
            per_row,
            fadeout_duration,
            button_height,
            current_settings["window_size"],
            current_settings["volume"],
        )
        self.fadeout_duration = fadeout_duration
        updated_settings = jingleplayer_logic.get_current_settings()
        updated_buttons = updated_settings["buttons"]
        self.jingle_texts = updated_buttons["texts"]
        self.jingle_colors = updated_buttons["colors"]
        self.jingle_paths = updated_buttons["paths"]
        self.jingle_volumes = updated_buttons["volumes"]
        self.buttons_per_row = list(updated_buttons["per_row"])
        self.button_height = int(updated_settings["button_height"])
        jingleplayer_logic.save_settings(updated_settings)
        self._rebuild_jingle_layout()

    def _save_fadeout_duration(self, fadeout_duration):
        self._save_application_settings(
            fadeout_duration,
            self.buttons_per_row,
            self.button_height,
        )

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
