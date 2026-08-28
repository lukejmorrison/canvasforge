"""Close / SIP-teardown must not fire scene selection slots into dying widgets.

Closing CanvasForge with pixmap items on the unparented QGraphicsScene has
aborted via PyQt's pyqt6_err_print (SIGABRT). See GitHub issue #48.
"""

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QSettings, QThreadPool
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication

from main import MainWindow, RasterItem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def main_window(qapp, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "cache").mkdir()
    empty_library = tmp_path / "library"
    empty_library.mkdir()
    settings = QSettings("CanvasForge", "CanvasForge")
    settings.setValue("screenshot_library_dir", str(empty_library))
    settings.sync()
    window = MainWindow()
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone(2000)


def _tiny_pixmap():
    pix = QPixmap(16, 16)
    pix.fill(QColor("#cc0000"))
    return pix


def _selection_slot_connected(window) -> bool:
    scene = getattr(window, "scene", None)
    if scene is None:
        return False
    try:
        scene.selectionChanged.disconnect(window.on_scene_selection_changed)
    except TypeError:
        return False
    except RuntimeError:
        return False
    scene.selectionChanged.connect(window.on_scene_selection_changed)
    return True


def test_scene_is_parented_to_the_main_window(main_window):
    assert main_window.scene.parent() is main_window


def test_scene_selection_slot_ignores_deleted_layer_list(main_window):
    sip.delete(main_window.layer_list)
    main_window.on_scene_selection_changed()


def test_close_disconnects_scene_selection_before_teardown(main_window):
    item = RasterItem(_tiny_pixmap())
    main_window.scene.addItem(item)
    item.setSelected(True)
    assert _selection_slot_connected(main_window) is True

    main_window.close()

    assert _selection_slot_connected(main_window) is False


def test_close_with_selected_pixmap_does_not_raise(main_window, qapp):
    item = RasterItem(_tiny_pixmap())
    main_window.scene.addItem(item)
    item.setSelected(True)
    main_window.close()
    qapp.processEvents()
