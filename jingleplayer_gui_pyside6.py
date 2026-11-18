"""Minimal parallel PySide6 entry point for Jingleplayer."""

import sys
import stat
import os
import re
import unicodedata
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QInputDialog,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import jingleplayer_logic
import jingleplayer_packages

MAX_FADEOUT_DURATION_MS = 2_147_483_647
MIN_BUTTON_HEIGHT = 1
MAX_BUTTON_HEIGHT = 10


class PackageJob(QThread):
    """Filesystem work only; results are handled via finished on the GUI thread."""

    def __init__(self, work, parent):
        super().__init__(parent)
        self.work = work
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.work()
        except Exception as error:
            self.error = error


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


class HelpDialog(QDialog):
    """Display the bundled user manual without requiring an external app."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hilfe")
        self.resize(700, 600)

        self.text_browser = QTextBrowser(self)
        help_path = resource_path("HELP.md")
        try:
            help_text = help_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            QMessageBox.warning(
                self,
                "Hilfe konnte nicht geladen werden",
                f"Die Hilfedatei konnte nicht gelesen werden: {error}",
            )
        else:
            self.text_browser.setMarkdown(help_text)

        self.close_button = QPushButton("Schließen", self)
        self.close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_browser, 1)
        layout.addWidget(self.close_button)


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

        self.help_button = QPushButton("Hilfe", self)
        self.help_button.clicked.connect(self._open_help_dialog)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.addWidget(audio_group)
        dialog_layout.addWidget(layout_group)
        dialog_layout.addWidget(self.help_button)
        dialog_layout.addWidget(self.button_box)

    def _open_help_dialog(self):
        HelpDialog(self).exec()

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
        self._package_busy = False
        self._settings_writes_blocked = False
        self._restart_required = False
        self._package_job = None
        self._package_progress = None
        self._prepared_path = None

        window_size = current_settings["window_size"]
        self._persisted_window_size = (int(window_size[0]), int(window_size[1]))
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
        menu = self.menuBar().addMenu("Presets")
        for text, op in (("Neu…", "create"), ("Duplizieren…", "duplicate"), ("Umbenennen…", "rename"), ("Löschen…", "delete")):
            menu.addAction(text).triggered.connect(lambda checked=False, operation=op: self._manage_preset(operation))
        self._refresh_preset_selector()

        self.sound_end_timer = QTimer(self)
        self.sound_end_timer.setInterval(jingleplayer_logic.FADEOUT_CHECK_INTERVAL_MS)
        self.sound_end_timer.timeout.connect(self._poll_sound_end)
        self.sound_end_timer.start()
        package_menu = self.menuBar().addMenu("Soundboard")
        self.export_action = QAction("Soundboard exportieren...", self)
        self.import_action = QAction("Soundboard importieren...", self)
        package_menu.addActions([self.export_action, self.import_action])
        self.export_action.triggered.connect(self._export_soundboard)
        self.import_action.triggered.connect(self._import_soundboard)

    def _refresh_preset_selector(self):
        blocked = self.preset_combo.blockSignals(True)
        try:
            self.preset_combo.clear()
            document = jingleplayer_logic.get_preset_settings()
            for preset in document["presets"]:
                self.preset_combo.addItem(preset["name"], preset["id"])
            self.preset_combo.setCurrentIndex(next(i for i, p in enumerate(document["presets"])
                                                   if UUID(p["id"]) == UUID(document["active_preset_id"])))
        finally:
            self.preset_combo.blockSignals(blocked)

    def _manage_preset(self, operation):
        if not self._begin_package_operation():
            return
        committed = False
        try:
            document = jingleplayer_logic.get_preset_settings()
            active = document["active_preset_id"]
            selected = next(p for p in document["presets"] if UUID(p["id"]) == UUID(active))
            kwargs = {}
            if operation == "switch":
                target = self.preset_combo.currentData()
                if target is None or target == active:
                    return
                args = (target,)
            elif operation == "delete":
                if len(document["presets"]) == 1:
                    raise ValueError("Das letzte Preset darf nicht gelöscht werden.")
                if QMessageBox.question(self, "Preset löschen?", f"Preset „{selected['name']}“ löschen? Audiodateien bleiben erhalten.",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
                other = [p for p in document["presets"] if p["id"] != active]
                name, ok = QInputDialog.getItem(self, "Nachfolger", "Aktives Preset danach:", [p["name"] for p in other], 0, False)
                if not ok:
                    return
                args = (active,)
                kwargs["successor_id"] = next(p["id"] for p in other if p["name"] == name)
            else:
                name, ok = QInputDialog.getText(self, "Preset", "Presetname:")
                if not ok:
                    return
                args = (name,) if operation == "create" else (active, name)
                if operation in ("create", "duplicate"):
                    kwargs["activate"] = True
            self.sound_end_timer.stop()
            result = jingleplayer_logic.manage_presets(operation, *args, **kwargs)
            if not result["success"]:
                raise RuntimeError(result["error"])
            committed = True
            self._reload_after_import()
        except Exception as error:
            if committed or jingleplayer_logic.get_settings_persistence_status()["write_blocked"]:
                self._settings_writes_blocked = self._restart_required = True
            QMessageBox.critical(self, "Preset konnte nicht geändert werden",
                                 ("Änderung gespeichert, aber Anzeige nicht geladen. Bitte neu starten.\n"
                                  if committed else "") + str(error))
        finally:
            self._refresh_preset_selector()
            playing = set(jingleplayer_logic.get_playing_indices())
            for index, tile in enumerate(self.jingle_tiles, 1):
                tile.set_playing(index in playing)
            if not self._restart_required:
                self.sound_end_timer.start()
            self._finish_package_operation()

    def _begin_package_operation(self):
        if self._package_busy or self._restart_required:
            return False
        if any(dialog.isVisible() for dialog in self.findChildren(QDialog)):
            self.statusBar().showMessage("Bitte zuerst den geöffneten Dialog speichern oder schließen.", 6000)
            return False
        self._package_busy = True
        self._prepared_path = None
        self.export_action.setEnabled(False)
        self.import_action.setEnabled(False)
        self.centralWidget().setEnabled(False)
        return True

    def _finish_package_operation(self):
        if self._package_progress is not None:
            self._package_progress.close()
            self._package_progress.deleteLater()
            self._package_progress = None
        self._package_busy = False
        self.export_action.setEnabled(not self._restart_required)
        self.import_action.setEnabled(not self._restart_required)
        self.centralWidget().setEnabled(not self._restart_required)

    def _run_package_job(self, text, work, done):
        """No widget/global audio access in work. Keep window alive until finished.

        No cancellation once filesystem work starts: backend operations cannot be
        safely interrupted. Qt remains responsive; closing is refused while busy.
        """
        if self._package_progress is not None:
            self._package_progress.close()
            self._package_progress.deleteLater()
        progress = QProgressDialog(text, "", 0, 0, self)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self._package_progress = progress
        job = PackageJob(work, self)
        self._package_job = job

        def finished():
            self._package_job = None
            progress.close()
            job.deleteLater()
            try:
                done(job.result, job.error)
            except Exception as error:
                # A callback failure after activation must never enable stale saves.
                if self._settings_writes_blocked:
                    self._restart_required = True
                    self.sound_end_timer.stop()
                QMessageBox.critical(self, "Soundboard-Vorgang fehlgeschlagen",
                                     "Bitte den Zustand prüfen und Jingleplayer gegebenenfalls neu starten.\n" +
                                     str(error) + self._retained_preparation_text())
                self._finish_package_operation()

        job.finished.connect(finished)
        job.start()

    def _package_error_text(self, error):
        if (isinstance(error, FileExistsError) or isinstance(getattr(error, "__cause__", None), FileExistsError)
                or getattr(error, "code", "") == "destination"):
            reason = "Das Exportziel existiert bereits. Bitte einen neuen Paketnamen wählen."
        elif isinstance(error, jingleplayer_packages.PackageValidationError):
            reason = ("Paket oder Audiodatei ungültig, beschädigt oder nicht verfügbar. "
                      "Bitte Dateien, Dateinamen und Prüfsummen prüfen.")
        else:
            reason = "Vorgang fehlgeschlagen. Bitte Zugriffsrechte und freien Speicherplatz prüfen."
        return reason + "\n\nDetails (auch Zugriffsrechte und Speicherplatz prüfen):\n" + str(error)

    def _export_soundboard(self):
        if not self._begin_package_operation():
            return
        try:
            # Accepted edits already update runtime, even if their save failed.
            # Modal editors must be saved/closed before invoking this operation.
            snapshot = jingleplayer_logic.get_current_settings()
            snapshot["window_size"] = [self.width(), self.height()]
            parent = QFileDialog.getExistingDirectory(self, "Übergeordneten Ordner für den Export auswählen")
            if not parent:
                self._finish_package_operation()
                return
            name, accepted = QInputDialog.getText(self, "Neues Soundboard-Paket", "Name des neuen Paketordners:")
            if not accepted:
                self._finish_package_operation()
                return
            destination = self._export_destination(Path(parent), name)
            base = None
            if any(p and not Path(p).is_absolute() for p in snapshot["buttons"]["paths"]):
                QMessageBox.information(self, "Relative Audiodateien", "Bitte den Basisordner der relativen "
                                        "Audiozuweisungen auswählen. Er wird nur für diesen Export verwendet.")
                folder = QFileDialog.getExistingDirectory(self, "Basisordner der relativen Audiodateien")
                if not folder:
                    self._finish_package_operation()
                    return
                base = Path(folder)

            def done(result, error):
                if error is None:
                    QMessageBox.information(self, "Soundboard exportiert", f"Paket gespeichert:\n{destination}")
                else:
                    QMessageBox.critical(self, "Export fehlgeschlagen", self._package_error_text(error))
                self._finish_package_operation()

            def preflight_done(result, error):
                if error is not None:
                    done(None, error)
                    return
                missing, blocked = result
                if blocked:
                    QMessageBox.critical(self, "Audiodateien können nicht exportiert werden",
                                         "Diese Zuweisungen sind nicht sicher lesbar oder ungültig. "
                                         "Bitte über die Tasteneinstellungen prüfen und neu zuweisen.\n\n" +
                                         "\n\n".join(blocked + list(missing.values())))
                    self._finish_package_operation()
                    return
                if missing:
                    if not self._confirm_missing_export(missing):
                        self.statusBar().showMessage("Export abgebrochen.", 5000)
                        self._finish_package_operation()
                        return
                    for index in missing:
                        snapshot["buttons"]["paths"][index] = ""
                self._run_package_job("Soundboard wird exportiert …",
                                      lambda: jingleplayer_packages.export_package_directory(
                                          snapshot, destination, source_base=base), done)

            self._run_package_job("Alle 50 Audiozuweisungen werden geprüft …",
                                  lambda: self._preflight_export(snapshot, base), preflight_done)
        except Exception as error:
            QMessageBox.critical(self, "Export fehlgeschlagen", self._package_error_text(error))
            self._finish_package_operation()

    @staticmethod
    def _export_destination(parent, name):
        """Accept exactly one portable directory component, never normalize input."""
        if (not isinstance(name, str) or not name or name in (".", "..") or
                name.endswith((".", " ")) or
                any(c in '/\\<>:"|?*' or unicodedata.category(c).startswith("C") for c in name) or
                re.fullmatch(r"CON|PRN|AUX|NUL|CLOCK\$|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³]",
                             name.split(".")[0].rstrip(" ").upper()) or
                len(name.encode("utf-8")) > 200):
            raise ValueError("Ungültiger Paketname. Bitte einen kurzen Namen ohne Pfadzeichen, "
                             "reservierte Windows-Namen oder abschließende Punkte/Leerzeichen eingeben.")
        if not parent.is_absolute() or not parent.is_dir():
            raise ValueError("Bitte einen vorhandenen übergeordneten Ordner auswählen.")
        destination = parent / name
        if os.path.lexists(destination):
            raise FileExistsError(f"Das Exportziel existiert bereits: {destination}")
        return destination

    @staticmethod
    def _preflight_export(snapshot, base):
        """Read-only advisory check, not a replacement for backend validation.

        Only FileNotFoundError is omittable. Access errors, links/reparse points,
        nonregular/unsupported sources and malformed paths block export. Inspect
        every assignment, including aliases/hidden slots, and never infer CWD.
        Readability is not codec validation; existing files are never omitted for
        decoding/validation errors. Backend rechecks all retained sources later.
        """
        paths = snapshot["buttons"]["paths"]
        if len(paths) != 50:
            raise ValueError("Der Export benötigt genau 50 persistente Tastenplätze.")
        missing, blocked = {}, []
        for index, value in enumerate(paths):
            description = f"Taste {index + 1}: {snapshot['buttons']['texts'][index]}\n{value}"
            try:
                if not isinstance(value, str):
                    raise ValueError("Ungültiger Audiopfad")
                if not value:
                    continue
                if "\0" in value:
                    raise ValueError("Ungültiger Audiopfad")
                path = Path(value)
                if ".." in path.parts:
                    raise ValueError("Übergeordnete Pfadkomponenten sind nicht erlaubt")
                if not path.is_absolute():
                    if base is None or not base.is_absolute() or path.drive or path.root:
                        raise ValueError("Relativer Audiopfad benötigt einen expliziten Basisordner")
                    path = base / path
                    description += f"\nAufgelöster Pfad: {path}"
                if path.suffix.lower() not in (".mp3", ".wav"):
                    raise ValueError("Nur MP3 und WAV werden unterstützt")
                for ancestor in reversed(path.parents):
                    info = ancestor.lstat()
                    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                            getattr(info, "st_file_attributes", 0) & 0x400):
                        raise ValueError("Unsicherer Audioordner (Link oder kein regulärer Ordner)")
                info = path.lstat()
                if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                        getattr(info, "st_file_attributes", 0) & 0x400):
                    raise ValueError("Kein reguläres Audiofile oder Link/Reparse-Punkt")
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                with os.fdopen(os.open(path, flags), "rb") as stream:
                    stream.read(1)
            except FileNotFoundError:
                missing[index] = description + "\nDatei oder Audioordner fehlt."
            except (OSError, ValueError) as error:
                blocked.append(description + "\n" + str(error))
        return missing, blocked

    def _confirm_missing_export(self, missing):
        box = QMessageBox(self)
        box.setWindowTitle("Fehlende Audiodateien")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText("Folgende Audiozuweisungen fehlen (einschließlich ausgeblendeter Tasten):\n\n" +
                    "\n\n".join(missing.values()))
        box.setInformativeText("Ohne diese Dateien exportieren? Nur im exportierten Paket werden diese "
                               "Audiozuweisungen geleert. Ihre aktuellen Tasten bleiben unverändert. "
                               "Zum Neuzuweisen: Export abbrechen und die vorhandenen Tasteneinstellungen verwenden.")
        proceed = box.addButton("Ohne fehlende Dateien exportieren", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Export abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() == proceed

    def _import_soundboard(self):
        if not self._begin_package_operation():
            return
        folder = QFileDialog.getExistingDirectory(self, "Soundboard-Paketordner auswählen")
        if not folder:
            self.statusBar().showMessage("Import abgebrochen.", 5000)
            self._finish_package_operation()
            return
        source = Path(folder)

        def preview(validated, error):
            if error is not None:
                QMessageBox.critical(self, "Ungültiges Soundboard-Paket", self._package_error_text(error))
                self._finish_package_operation()
                return
            assigned = sum(bool(p) for p in validated.settings["buttons"]["paths"])
            answer = QMessageBox.question(
                self, "Soundboard importieren?",
                f"{len(validated.assets)} Audiodateien, {assigned} zugewiesene Tasten (von 50, einschließlich "
                "ausgeblendeter Tasten).\n\nIm nächsten Schritt wählen Sie ein neues Preset oder ausdrücklich "
                "das Ersetzen des aktiven Presets. Andere Presets bleiben erhalten. "
                "Lokale Fenstergröße und Gesamtlautstärke bleiben erhalten. "
                "Vor dem Wechsel wird die Wiedergabe gestoppt und eine Wiederherstellungskopie angelegt.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("Import abgebrochen.", 5000)
                self._finish_package_operation()
                return
            settings_path = Path(jingleplayer_logic.settings_file)
            mode, ok = QInputDialog.getItem(self, "Importziel", "Soundboard übernehmen:",
                                           ["Als neues Preset", "Aktives Preset ersetzen"], 0, False)
            if not ok:
                self._finish_package_operation()
                return
            preset_mode = "new" if mode == "Als neues Preset" else "replace"
            preset_name = None
            if preset_mode == "new":
                preset_name, ok = QInputDialog.getText(self, "Importiertes Preset", "Presetname:")
                if not ok:
                    self._finish_package_operation()
                    return
            saved = jingleplayer_logic.save_settings(jingleplayer_logic.get_current_settings())
            if not saved["success"]:
                self._import_failed(RuntimeError(saved["error"]))
                return
            expected = jingleplayer_logic.get_settings_storage_token()

            def prepare():
                roots = self._managed_package_roots(settings_path)
                prepared = jingleplayer_packages.prepare_package_import(source, roots[0])
                return prepared, roots

            def prepared_done(result, prepare_error):
                if prepare_error is not None:
                    self._import_failed(prepare_error)
                    return
                prepared, roots = result
                self._prepared_path = prepared.preparation_directory
                # Recheck preview against prepared metadata; confirmation must
                # never authorize a different board changed while preparing.
                if prepared.source_package != validated:
                    self._import_failed(ValueError("Das Paket wurde nach der Vorschau verändert."))
                    return
                try:
                    self.sound_end_timer.stop()
                    for index in list(jingleplayer_logic.get_playing_indices()):
                        jingleplayer_logic.stop_jingle(index, 0)
                    if jingleplayer_logic.get_playing_indices():
                        raise RuntimeError("Audiowiedergabe konnte nicht vollständig gestoppt werden.")
                    jingleplayer_logic.stop_all_playback()
                    for tile in self.jingle_tiles:
                        tile.set_playing(False)
                except Exception as stop_error:
                    self._import_failed(stop_error)
                    return
                self._settings_writes_blocked = True
                self._run_package_job("Soundboard wird aktiviert …", lambda:
                    jingleplayer_packages.activate_prepared_import(
                        prepared, settings_path, roots[1], roots[2], preset_mode=preset_mode,
                        preset_name=preset_name, expected=expected),
                    self._activation_done)

            self._run_package_job("Soundboard wird vorbereitet …", prepare, prepared_done)

        self._run_package_job("Soundboard-Paket wird geprüft …",
                              lambda: jingleplayer_packages.validate_package_directory(source), preview)

    @staticmethod
    def _managed_package_roots(settings_path):
        """Only create managed roots; backend performs all package/file validation."""
        if not settings_path.is_absolute() or not settings_path.is_file():
            raise ValueError("Die aktive Settingsdatei fehlt. Bitte zuerst Einstellungen speichern.")
        directory = settings_path.parent
        roots = tuple(directory / name for name in ("import-staging", "library", "import-recovery"))
        for root in roots:
            for part in reversed((root, *root.parents)):
                if part == root and not part.exists() and not part.is_symlink():
                    part.mkdir(mode=0o700)
                info = part.lstat()
                if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                        getattr(info, "st_file_attributes", 0) & 0x400):
                    raise ValueError(f"Unsicherer verwalteter Ordner: {part}")
        return roots

    def _retained_preparation_text(self):
        return (f"\nVorbereitungsdaten bleiben erhalten:\n{self._prepared_path}"
                if self._prepared_path is not None else "")

    def _import_failed(self, error):
        QMessageBox.critical(self, "Import nicht aktiviert", self._package_error_text(error) +
                             self._retained_preparation_text())
        self.sound_end_timer.start()
        self._finish_package_operation()

    def _activation_done(self, result, error):
        self._settings_writes_blocked = True
        outcome = getattr(error if error is not None else result, "outcome", "indeterminate")
        recovery = getattr(error if error is not None else result, "recovery_directory", None)
        details = (f"\nWiederherstellung:\n{recovery}" if recovery else "")
        details += self._retained_preparation_text()
        if error is not None:
            retained = getattr(error, "retained_paths", ())
            if retained:
                details += "\nErhaltene Daten:\n" + "\n".join(map(str, retained))
        if outcome == "indeterminate":
            self._restart_required = True
            QMessageBox.critical(self, "Importstatus unklar", "Der Import kann bereits auf dem Datenträger aktiv sein. "
                                 "Es erfolgt keine automatische Wiederherstellung. Speichern ist gesperrt. "
                                 "Bitte Jingleplayer schließen und den Zustand vor dem Neustart prüfen." + details)
        elif outcome in ("committed", "not_committed"):
            try:
                self._reload_after_import()
                self._settings_writes_blocked = False
                self.sound_end_timer.start()
            except Exception as reload_error:
                self._restart_required = True
                message = ("Der Import wurde auf dem Datenträger aktiviert, aber die Oberfläche konnte nicht "
                           "neu geladen werden." if outcome == "committed" else
                           "Der Import wurde nicht aktiviert. Die aktuellen Einstellungen konnten nicht neu geladen werden.")
                QMessageBox.critical(self, "Neustart erforderlich", message + " Speichern bleibt gesperrt. "
                                     "Bitte Jingleplayer schließen und neu starten.\n" + str(reload_error) + details)
            else:
                if outcome == "committed":
                    QMessageBox.information(self, "Soundboard importiert", "Soundboard wurde aktiviert." + details)
                else:
                    QMessageBox.critical(self, "Import nicht aktiviert", "Die Einstellungen wurden durch den Import "
                                         "nicht ersetzt.\n" + self._package_error_text(error) + details)
        else:
            self._restart_required = True
            QMessageBox.critical(self, "Importstatus unklar", "Unbekannter Aktivierungsstatus. Speichern bleibt "
                                 "gesperrt; bitte schließen und den Zustand prüfen." + details)
        self._finish_package_operation()

    def _reload_after_import(self):
        """GUI thread only. Reload persistence bookkeeping before allowing saves.

        Installed paths are unique, so existing cached sounds cannot shadow them.
        Do not edit private engine caches/events; stop_jingle releases event maps.
        """
        jingleplayer_logic.initialize_settings()
        status = jingleplayer_logic.get_settings_persistence_status()
        if status["write_blocked"]:
            raise RuntimeError(status.get("error") or "Einstellungen konnten nicht gelesen werden.")
        current = jingleplayer_logic.get_current_settings()
        buttons = current["buttons"]
        self.jingle_texts = buttons["texts"]
        self.jingle_colors = buttons["colors"]
        self.jingle_paths = buttons["paths"]
        self.jingle_volumes = buttons["volumes"]
        self.buttons_per_row = list(buttons["per_row"])
        self.last_folder = current["last_folder"]
        self.fadeout_duration = current["fadeout_duration"]
        self.button_height = int(current["button_height"])
        self._persisted_window_size = tuple(current["window_size"])
        previous = self.volume_slider.blockSignals(True)
        try:
            self.volume_slider.setValue(int(current["volume"]))
            self.volume_value_label.setText(f"{int(current['volume'])} %")
        finally:
            self.volume_slider.blockSignals(previous)
        self._rebuild_jingle_layout()
        self._refresh_preset_selector()

    def _build_main_layout(self, current_settings):
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        volume_layout = QHBoxLayout()
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(8)
        self.preset_combo = QComboBox(central_widget)
        self.preset_combo.setAccessibleName("Aktives Preset")
        self.preset_combo.currentIndexChanged.connect(lambda _: self._manage_preset("switch"))
        volume_layout.addWidget(self.preset_combo)

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
        if self._package_busy or self._restart_required:
            return
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
        elif result and result.get("error"):
            tile.set_playing(False)
            QMessageBox.critical(
                self,
                "Jingle konnte nicht abgespielt werden",
                result["error"],
            )

    def _open_jingle_editor(self, index):
        if self._package_busy or self._restart_required:
            return
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
        self._save_settings_with_feedback(
            updated_settings,
            "Jingle konnte nicht gespeichert werden",
        )

    def _poll_sound_end(self):
        indicator_updates = jingleplayer_logic.check_sound_end()
        for update in indicator_updates or []:
            index = update["index"]
            if 1 <= index <= len(self.jingle_tiles):
                self.jingle_tiles[index - 1].set_playing(update["playing"])

    def _handle_volume_change(self, volume_percent):
        if self._package_busy or self._settings_writes_blocked:
            return
        self.volume_value_label.setText(f"{volume_percent} %")
        jingleplayer_logic.set_volume_logic(volume_percent)
        self._save_settings_with_feedback(
            jingleplayer_logic.get_current_settings(),
            "Lautstärke konnte nicht gespeichert werden",
        )

    def _save_settings_with_feedback(self, current_settings, title):
        if self._package_busy or self._settings_writes_blocked:
            return False
        result = jingleplayer_logic.save_settings(current_settings)
        if result.get("success"):
            return True
        if jingleplayer_logic.get_settings_persistence_status()["write_blocked"]:
            self._settings_writes_blocked = self._restart_required = True
        QMessageBox.critical(
            self,
            title,
            result.get("error") or "Die Einstellungen konnten nicht gespeichert werden.",
        )
        return False

    def _open_settings_dialog(self):
        if self._package_busy or self._restart_required:
            return
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
        if self._package_busy or self._settings_writes_blocked:
            return
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
        if self._save_settings_with_feedback(
            updated_settings,
            "Einstellungen konnten nicht gespeichert werden",
        ):
            self._rebuild_jingle_layout()

    def _save_fadeout_duration(self, fadeout_duration):
        self._save_application_settings(
            fadeout_duration,
            self.buttons_per_row,
            self.button_height,
        )

    def closeEvent(self, event):
        if self._package_busy:
            self.statusBar().showMessage("Bitte warten, bis der Soundboard-Vorgang abgeschlossen ist.", 5000)
            event.ignore()
            return
        self.sound_end_timer.stop()
        if self._settings_writes_blocked:
            super().closeEvent(event)
            return
        current_size = (self.width(), self.height())
        if current_size != self._persisted_window_size:
            current_settings = jingleplayer_logic.get_current_settings()
            current_settings["window_size"] = list(current_size)
            if self._save_settings_with_feedback(
                current_settings,
                "Fenstergröße konnte nicht gespeichert werden",
            ):
                self._persisted_window_size = current_size
        super().closeEvent(event)


def create_main_window():
    """Initialize settings once and create the PySide6 main window."""
    jingleplayer_logic.initialize_settings()
    persistence_status = jingleplayer_logic.get_settings_persistence_status()
    if persistence_status["write_blocked"]:
        error = persistence_status.get("error") or "Unbekannter Fehler"
        QMessageBox.critical(
            None,
            "Einstellungen konnten nicht geladen werden",
            f"{error}\n\nDie vorhandene Settingsdatei wurde nicht verändert.",
        )
        return None
    current_settings = jingleplayer_logic.get_current_settings()
    window = JingleplayerMainWindow(current_settings)

    return window


def main():
    app = QApplication(sys.argv)
    window = create_main_window()
    if window is None:
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
