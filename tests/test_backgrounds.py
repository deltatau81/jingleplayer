"""Preset image model, real Qt rendering and package compatibility regressions."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest

import jingleplayer_gui_pyside6 as gui
import jingleplayer_logic as logic
import jingleplayer_packages as packages
import jingleplayer_presets as presets
import jingleplayer_preset_storage as storage
from test_portable_gui import context, make_package, select_import, select_export, drain


def image_file(tmp_path, name="Hintergrund 音楽.png", color="red", format=None):
    path = tmp_path / name
    image = QImage(120, 60, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    assert image.save(str(path), format)
    return path


def active(document):
    return next(p for p in document["presets"] if UUID(p["id"]) == UUID(document["active_preset_id"]))


def select_image(context, monkeypatch, path):
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    context.window._choose_background()


def test_old_schema3_without_background_remains_identical(context):
    token = storage.load_preset_settings(context.active)
    storage.save_preset_settings(context.active, token.data, expected=token)
    context.window._reload_after_import()
    before = context.active.read_bytes()
    original = logic.get_preset_settings()
    assert "background_image" not in active(original)
    assert presets.validate_schema3_settings(original) == original
    assert presets.migrate_settings_to_schema3(original) == original
    assert context.window.background_canvas.pixmap.isNull()
    assert not context.window.remove_background_action.isEnabled()
    assert logic.save_settings(logic.get_current_settings())["skipped"]
    assert context.active.read_bytes() == before and json.loads(before)["schema_version"] == 3


@pytest.mark.parametrize("value", [None, 1, True, {}, [], b"image bytes", "bad\0.png", "\ud800"])
def test_background_configuration_only_allows_path_strings(context, value):
    document = logic.get_preset_settings()
    active(document)["background_image"] = value
    with pytest.raises(presets.PresetValidationError):
        presets.validate_schema3_settings(document)


@pytest.mark.parametrize("format,name", [("PNG", "背景.png"), ("JPEG", "Grüße.jpg"), ("JPEG", "space name.JPEG")])
def test_choose_image_is_visible_persisted_and_restored(context, tmp_path, monkeypatch, format, name):
    path = image_file(tmp_path, name, format=format)
    before = logic.get_current_settings()
    original_bytes = path.read_bytes()
    select_image(context, monkeypatch, path)
    document = storage.load_preset_settings(context.active).data
    assert active(document)["background_image"] == str(path)
    assert not context.window.background_canvas.pixmap.isNull()
    assert str(path) in context.window.background_info.text()
    assert context.window.remove_background_action.isEnabled()
    assert logic.get_current_settings() == before
    assert path.read_bytes() == original_bytes and not context.stops
    context.window.background_canvas.set_background(QPixmap())
    context.window._background_key = None
    context.window._reload_after_import()
    assert not context.window.background_canvas.pixmap.isNull()
    assert len(logic.get_current_settings()["buttons"]["paths"]) == 50


def test_duplicate_and_new_and_preset_switch_backgrounds(context, tmp_path, monkeypatch):
    context.window.show()
    red = image_file(tmp_path)
    select_image(context, monkeypatch, red)
    original = logic.get_preset_settings()
    original_id = original["active_preset_id"]
    assert logic.manage_presets("duplicate", original_id, "Copy", activate=True)["success"]
    assert active(logic.get_preset_settings())["background_image"] == str(red)
    copied_id = logic.get_preset_settings()["active_preset_id"]
    assert logic.manage_presets("rename", copied_id, "Renamed copy")["success"]
    assert active(logic.get_preset_settings())["background_image"] == str(red)
    assert logic.manage_presets("create", "Blank", activate=True)["success"]
    context.window._reload_after_import()
    assert context.window.background_canvas.pixmap.isNull()
    blue = image_file(tmp_path, "blue.png", "blue")
    select_image(context, monkeypatch, blue)
    blue_id = logic.get_preset_settings()["active_preset_id"]
    assert logic.manage_presets("switch", original_id)["success"]
    context.window._reload_after_import()
    assert context.window.background_canvas.pixmap.toImage().pixelColor(0, 0) == QColor("red")
    assert context.window.background_canvas.grab().toImage().pixelColor(0, 0) == QColor("red")
    assert logic.manage_presets("switch", blue_id)["success"]
    context.window._reload_after_import()
    assert context.window.background_canvas.pixmap.toImage().pixelColor(0, 0) == QColor("blue")
    assert context.window.background_canvas.grab().toImage().pixelColor(0, 0) == QColor("blue")
    assert active(original)["background_image"] == str(red)
    assert len(logic.get_preset_settings()["presets"]) == 3


def test_cancel_and_remove_only_changes_current_background(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    assert logic.manage_presets("duplicate", logic.get_preset_settings()["active_preset_id"], "Other")["success"]
    document = logic.get_preset_settings()
    before = context.active.read_bytes()
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    context.window._choose_background()
    assert context.active.read_bytes() == before
    context.window.remove_background_action.trigger()
    after = logic.get_preset_settings()
    assert active(after)["background_image"] == ""
    assert after["presets"][1] == document["presets"][1]
    assert context.window.background_canvas.pixmap.isNull()
    assert not context.window.remove_background_action.isEnabled()
    assert path.is_file()


def test_delete_preset_preserves_external_image(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    source_id = logic.get_preset_settings()["active_preset_id"]
    assert logic.manage_presets("create", "Other", activate=True)["success"]
    assert logic.manage_presets("delete", source_id)["success"]
    assert path.is_file()


@pytest.mark.parametrize("kind", ["missing", "corrupt", "unsupported"])
def test_unavailable_images_fall_back_without_startup_or_settings_failure(context, tmp_path, kind):
    path = tmp_path / "bad.png"
    if kind == "corrupt":
        path.write_bytes(b"not an image")
    elif kind == "unsupported":
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    document = logic.get_preset_settings()
    active(document)["background_image"] = str(path)
    assert logic.save_settings(document)["success"]
    before = context.active.read_bytes()
    context.window._reload_after_import()
    assert context.window.background_canvas.pixmap.isNull()
    assert active(logic.get_preset_settings())["background_image"] == str(path)
    assert context.active.read_bytes() == before
    assert not logic.get_settings_persistence_status()["write_blocked"]
    assert "nicht verfügbar" in context.window.statusBar().currentMessage()


def test_invalid_selected_file_keeps_previous_image_and_settings(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    before = context.active.read_bytes()
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"bad jpeg")
    select_image(context, monkeypatch, corrupt)
    assert context.active.read_bytes() == before
    assert active(logic.get_preset_settings())["background_image"] == str(path)
    assert context.window.background_canvas.pixmap.toImage().pixelColor(0, 0) == QColor("red")
    assert context.messages[-1][0] == "critical"


def test_regular_flat_board_saves_preserve_background(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    context.window._handle_volume_change(17)
    context.window._save_application_settings(900, [1, 0, 0, 0, 0], 4)
    context.window._reload_after_import()
    assert active(logic.get_preset_settings())["background_image"] == str(path)
    assert logic.get_current_settings()["volume"] == 17
    assert not context.window.background_canvas.pixmap.isNull()


def test_resize_main_window_does_not_reload_cached_background(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    monkeypatch.setattr(gui, "load_background_image", lambda *a: pytest.fail("image reread on resize"))
    context.window.show()
    for width, height in ((1000, 600), (1200, 700), (800, 500)):
        context.window.resize(width, height)
        context.app.processEvents()
        assert not context.window.background_canvas.grab().isNull()
    assert active(logic.get_preset_settings())["background_image"] == str(path)


def test_oversized_image_header_rejected_before_decoding(context, tmp_path, monkeypatch):
    from types import SimpleNamespace
    path = image_file(tmp_path)
    reader = SimpleNamespace(setDecideFormatFromContent=lambda *a: None, setAutoTransform=lambda *a: None,
                             canRead=lambda: True, format=lambda: b"png", size=lambda: QSize(16385, 1),
                             read=lambda: pytest.fail("oversized image must not be decoded"))
    monkeypatch.setattr(gui, "QImageReader", lambda *a: reader)
    with pytest.raises(ValueError, match="Bildgröße"):
        gui.load_background_image(path)


def test_playing_indicator_contrasts_with_light_button(context):
    tile = gui.JingleTile(1, "White", "#ffffff")
    tile.set_playing(True)
    assert "background-color: rgba(15, 18, 22, 90)" in tile.styleSheet()
    assert "6px double #ffffff" in tile.styleSheet()
    tile.close()


def test_extreme_aspect_ratio_render_cache_stays_viewport_sized(context):
    image = QImage(16000, 1, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    canvas = gui.BackgroundCanvas()
    canvas.set_background(QPixmap.fromImage(image))
    canvas.resize(100, 100)
    rendered = canvas.grab().toImage()
    assert rendered.pixelColor(rendered.width() // 2, rendered.height() // 2) == QColor("red")
    assert canvas._scaled.size() == canvas.size() * canvas.devicePixelRatioF()
    canvas.close()


def test_failed_save_never_changes_image_or_mutates_document(context, tmp_path, monkeypatch):
    path = image_file(tmp_path)
    before = deepcopy(logic.get_preset_settings())
    monkeypatch.setattr(logic, "save_settings", lambda *a: {"success": False, "error": "write denied"})
    select_image(context, monkeypatch, path)
    assert logic.get_preset_settings() == before
    assert context.window.background_canvas.pixmap.isNull()
    assert context.messages[-1][1] == "Hintergrundbild nicht gespeichert"


def test_cover_center_crop_and_resize_use_cached_image(context, tmp_path, monkeypatch):
    # 2:1 image: red/green/blue bands, with the middle half green.
    image = QImage(200, 100, QImage.Format.Format_RGB32)
    image.fill(QColor("green"))
    painter = QPainter(image)
    painter.fillRect(0, 0, 50, 100, QColor("red"))
    painter.fillRect(150, 0, 50, 100, QColor("blue"))
    painter.end()
    path = tmp_path / "bands.png"
    assert image.save(str(path))
    canvas = gui.BackgroundCanvas()
    canvas.set_background(gui.load_background_image(path))
    monkeypatch.setattr(gui, "load_background_image", lambda *a: pytest.fail("must not reload on resize"))
    canvas.resize(100, 100)
    rendered = canvas.grab().toImage()
    assert rendered.pixelColor(rendered.width() // 2, rendered.height() // 2) == QColor("green")
    assert rendered.pixelColor(1, rendered.height() // 2) == QColor("green")
    canvas.resize(200, 50)
    rendered = canvas.grab().toImage()
    assert rendered.pixelColor(1, rendered.height() // 2) == QColor("red")
    assert rendered.pixelColor(rendered.width() - 2, rendered.height() // 2) == QColor("blue")
    assert canvas._scaled.width() >= canvas.width() and canvas._scaled.height() >= canvas.height()
    assert canvas.pixmap.size() == image.size()
    canvas.close()


def test_image_is_below_translucent_clickable_tiles_and_outside_toolbar(context, tmp_path, monkeypatch):
    path = image_file(tmp_path, color="yellow")
    select_image(context, monkeypatch, path)
    window = context.window
    window.show()
    context.app.processEvents()
    assert window.volume_slider.parentWidget() == window.centralWidget()
    assert all(row.parentWidget() == window.background_canvas for row in window.row_widgets)
    tile = window.jingle_tiles[0]
    image = window.background_canvas.grab().toImage()
    origin = tile.mapTo(window.background_canvas, tile.rect().topLeft())
    ratio = window.background_canvas.devicePixelRatioF()
    pixel = image.pixelColor(round((origin.x() + 10) * ratio), round((origin.y() + 10) * ratio))
    # Neutral overlay over the yellow image, independent of the saved color.
    for actual, tint, background in zip(pixel.getRgb()[:3], (15, 18, 22), (255, 255, 0)):
        assert abs(actual - (tint * 90 / 255 + background * 165 / 255)) <= 2
    calls = []
    monkeypatch.setattr(logic, "play_jingle", lambda *a: calls.append(a) or {"success": True})
    QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
    assert calls and tile.playing
    assert "6px double" in tile.styleSheet()
    assert tile.isVisible() and window.settings_button.isEnabled()


@pytest.mark.parametrize("sizes", [((300, 100), (100, 300)), ((257, 173), (401, 199))])
def test_cover_preserves_circle_geometry_across_resize(context, sizes):
    image = QImage(400, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("black"))
    painter.drawEllipse(170, 170, 60, 60)
    painter.end()
    canvas = gui.BackgroundCanvas(context.window)
    canvas.set_background(QPixmap.fromImage(image))
    for width, height in sizes:
        canvas.resize(width, height)
        rendered = canvas.grab().toImage()
        points = [(x, y) for y in range(rendered.height()) for x in range(rendered.width())
                  if rendered.pixelColor(x, y).red() < 50]
        xs, ys = zip(*points)
        diameter_x = max(xs) - min(xs) + 1
        diameter_y = max(ys) - min(ys) + 1
        assert abs(diameter_x - diameter_y) <= 2
        expected = 60 * max(width / 400, height / 400) * canvas.devicePixelRatioF()
        assert abs(diameter_x - expected) <= 2
        assert abs((max(xs) + min(xs)) / 2 - rendered.width() / 2) <= 2
        assert abs((max(ys) + min(ys)) / 2 - rendered.height() / 2) <= 2


def test_resize_and_rebuild_use_actual_canvas_and_hide_old_rows(context, tmp_path, monkeypatch):
    select_image(context, monkeypatch, image_file(tmp_path))
    window = context.window
    window.show()
    context.app.processEvents()
    monkeypatch.setattr(gui, "load_background_image", lambda *a: pytest.fail("unexpected disk read"))
    old_rows = list(window.row_widgets)
    window._rebuild_jingle_layout()
    assert all(row.isHidden() for row in old_rows)
    for size in ((1100, 650), (800, 800), (1200, 500)):
        window.resize(*size)
        context.app.processEvents()
        canvas = window.background_canvas
        assert canvas.height() < window.height()
        assert not canvas.grab().isNull()
        assert canvas._scaled_for == (canvas.size(), canvas.devicePixelRatioF())
        assert canvas._scaled.size() == canvas.size() * canvas.devicePixelRatioF()
        assert all(not row.autoFillBackground() for row in window.row_widgets)


def test_neutral_fill_and_custom_borders_preserve_values_and_controls(context):
    tile = gui.JingleTile(49, "Hidden number retained", "SystemButtonFace", context.window)
    assert tile.jingle_index == 49
    assert tile.jingle_color == "SystemButtonFace"
    assert "rgba(15, 18, 22, 90)" in tile.styleSheet()
    assert "border: 3px solid #555555" in tile.styleSheet()
    assert tile.label.styleSheet().startswith("color: #ffffff")
    assert tile.text_shadow.color() == QColor("black")
    assert tile.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert ":hover" in tile.styleSheet() and ":focus" in tile.styleSheet()
    tile.update_content("Custom", "#FFFF00")
    assert tile.jingle_color == "#FFFF00"
    assert "rgba(15, 18, 22, 90)" in tile.styleSheet()
    assert "border: 3px solid #ffff00" in tile.styleSheet()
    assert tile.label.styleSheet().startswith("color: #ffffff")
    assert tile.text_shadow.color() == QColor("black")
    clicked, edited = [], []
    tile.clicked.connect(clicked.append)
    tile.edit_requested.connect(edited.append)
    tile.show()
    QTest.mousePress(tile, Qt.MouseButton.LeftButton)
    assert tile._pressed and "rgba(15, 18, 22, 140)" in tile.styleSheet()
    QTest.mouseRelease(tile, Qt.MouseButton.LeftButton)
    assert not tile._pressed and clicked == [49]
    QTest.mouseClick(tile, Qt.MouseButton.RightButton)
    assert edited == [49] and clicked == [49]
    tile.set_playing(True)
    assert "border: 6px double #ffff73" in tile.styleSheet()
    tile.set_playing(False)
    assert "border: 3px solid #ffff00" in tile.styleSheet()


@pytest.mark.parametrize("background", ["white", "black", "blue"])
@pytest.mark.parametrize("saved_color", ["SystemButtonFace", "#ffff00", "#123456", "#80ff0000"])
def test_real_canvas_composites_neutral_fill_with_colored_border(context, background, saved_color):
    window = context.window
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor(background))
    window.background_canvas.set_background(QPixmap.fromImage(image))
    tile = window.jingle_tiles[0]
    tile.update_content("Readable", saved_color)
    window.show()
    context.app.processEvents()
    window.settings_button.setFocus()
    QTest.mouseMove(window.settings_button, window.settings_button.rect().center())
    context.app.processEvents()
    rendered = window.background_canvas.grab().toImage()
    origin = tile.mapTo(window.background_canvas, tile.rect().topLeft())
    ratio = window.background_canvas.devicePixelRatioF()
    pixel = rendered.pixelColor(round((origin.x() + 10) * ratio), round((origin.y() + 10) * ratio))
    for actual, tint, base in zip(pixel.getRgb()[:3], (15, 18, 22), QColor(background).getRgb()[:3]):
        assert abs(actual - (tint * 90 / 255 + base * 165 / 255)) <= 2
    assert tile.jingle_color == saved_color
    border = rendered.pixelColor(round((origin.x() + tile.width() / 2) * ratio), round((origin.y() + 1) * ratio))
    assert border == QColor(tile.display_color.name())  # Stored alpha never makes the border translucent.


@pytest.mark.parametrize("finish", ["stop", "natural_end"])
def test_focused_button_returns_to_solid_border_immediately(context, monkeypatch, finish):
    window = context.window
    window.show()
    window.activateWindow()
    context.app.processEvents()
    tile = window.jingle_tiles[0]
    tile.setFocus()
    tile.set_playing(True)
    assert tile.hasFocus() and "6px dashed" in tile.styleSheet()
    if finish == "stop":
        context.playing.append(1)
        window._handle_tile_click(1)
    else:
        monkeypatch.setattr(logic, "check_sound_end", lambda: [{"index": 1, "playing": False}])
        window._poll_sound_end()
    assert not tile.playing and tile.hasFocus()
    assert "dashed" not in tile.styleSheet()
    # Render immediately, without a second button click or focus change.
    image = tile.grab().toImage()
    ratio = tile.devicePixelRatioF()
    expected = QColor(tile.display_color.lighter(160).name())
    for x in range(15, tile.width() - 15):
        assert image.pixelColor(round(x * ratio), round(ratio)) == expected


def test_rendered_border_states_and_pressed_fill(context, monkeypatch):
    window = context.window
    tile = window.jingle_tiles[0]
    tile.update_content("States", "#2468ac")
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    window.background_canvas.set_background(QPixmap.fromImage(image))
    window.show()
    window.activateWindow()
    context.app.processEvents()
    monkeypatch.setattr(logic, "play_jingle", lambda *a: {"success": True})

    def pixel(x, y):
        rendered = window.background_canvas.grab().toImage()
        origin = tile.mapTo(window.background_canvas, tile.rect().topLeft())
        ratio = window.background_canvas.devicePixelRatioF()
        return rendered.pixelColor(round((origin.x() + x) * ratio), round((origin.y() + y) * ratio))

    def leave_tile():
        window.settings_button.setFocus()
        QTest.mouseMove(window.settings_button, window.settings_button.rect().center())
        context.app.processEvents()

    leave_tile()
    normal = pixel(tile.width() / 2, 1)
    assert normal == QColor("#2468ac")
    normal_fill = pixel(10, 10)
    QTest.mouseMove(tile, tile.rect().center())
    context.app.processEvents()
    assert tile.underMouse()
    assert pixel(tile.width() / 2, 1) == QColor(QColor("#2468ac").lighter(125).name())
    # Hover increases width as well as brightness.
    assert pixel(tile.width() / 2, 3) != normal_fill
    hovered = window.background_canvas.grab().toImage()
    tile.setFocus()
    context.app.processEvents()
    assert tile.hasFocus()
    focused = window.background_canvas.grab().toImage()
    assert focused != hovered
    assert "3px solid" in tile.styleSheet()
    assert pixel(tile.width() / 2, 1) != normal
    QTest.mousePress(tile, Qt.MouseButton.LeftButton)
    assert tile._pressed
    assert pixel(10, 10).lightness() < normal_fill.lightness()
    QTest.mouseRelease(tile, Qt.MouseButton.LeftButton)
    assert not tile._pressed
    tile.set_playing(True)
    assert "6px dashed" in tile.styleSheet()
    leave_tile()
    assert pixel(tile.width() / 2, 1) == QColor(QColor("#2468ac").lighter(145).name())
    # The double border has a visible gap, independently of its color.
    assert pixel(tile.width() / 2, 2) != pixel(tile.width() / 2, 1)
    tile.set_playing(False)
    assert pixel(tile.width() / 2, 1) == normal
    assert tile.jingle_color == "#2468ac"


def test_relative_image_path_uses_settings_directory_not_cwd(context, monkeypatch):
    path = image_file(context.active.parent)
    document = logic.get_preset_settings()
    active(document)["background_image"] = path.name
    assert logic.save_settings(document)["success"]
    monkeypatch.chdir(context.active.parent.parent)
    context.window._reload_after_import()
    assert not context.window.background_canvas.pixmap.isNull()
    assert active(logic.get_preset_settings())["background_image"] == path.name


@pytest.mark.parametrize("mode", ["new", "replace"])
def test_package_import_excludes_background_and_preserves_other_presets(context, tmp_path, monkeypatch, mode):
    path = image_file(tmp_path)
    select_image(context, monkeypatch, path)
    assert logic.manage_presets("duplicate", logic.get_preset_settings()["active_preset_id"], "Other")["success"]
    before = deepcopy(logic.get_preset_settings())
    package = make_package(tmp_path)
    select_import(monkeypatch, package)
    monkeypatch.setattr(gui.QInputDialog, "getItem", lambda *a, **k:
                        ("Als neues Preset" if mode == "new" else "Aktives Preset ersetzen", True))
    monkeypatch.setattr(gui.QInputDialog, "getText", lambda *a, **k: ("Imported", True))
    context.window._import_soundboard()
    drain(context)
    document = logic.get_preset_settings()
    assert document["presets"][1] == before["presets"][1]
    assert active(document).get("background_image", "") == ""
    if mode == "new":
        assert document["presets"][:2] == before["presets"]
    assert context.window.background_canvas.pixmap.isNull()
    # Export a preset that still HAS an image: only audio/board format 1/2.
    assert logic.manage_presets("switch", before["presets"][1]["id"])["success"]
    context.window._reload_after_import()
    target = tmp_path / "export-without-image"
    select_export(monkeypatch, target)
    context.window._export_legacy_soundboard()
    drain(context)
    exported = packages.validate_package_directory(target)
    assert exported.settings["schema_version"] == 2 and "background_image" not in exported.settings
    assert not list(target.rglob("*.png"))
    assert active(logic.get_preset_settings())["background_image"] == str(path)
    assert path.is_file()
