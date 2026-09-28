import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from jingleplayer_gui_pyside6 import create_main_window, resource_path  # noqa: E402


def test_main_window_can_be_constructed_and_closed():
    app = QApplication.instance() or QApplication([])
    window = create_main_window()

    assert window.windowTitle() == "Jingleplayer"
    assert resource_path("assets/jingleplayer.ico").is_file()
    assert not window.windowIcon().isNull()

    window.show()
    app.processEvents()
    assert window.isVisible()

    window.close()
    app.processEvents()
    assert not window.isVisible()
