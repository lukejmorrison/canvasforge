from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QStyleOptionViewItem

from image_library_panel import (
    SCREENSHOT_SETTINGS_KEY,
    THUMBNAIL_SIZE,
    ImageLibraryDelegate,
    ImageLibraryPanel,
    ThumbnailCache,
    copy_library_path_to_clipboard,
    display_thumb_size,
    item_row_height,
    library_path_tooltip,
)


def test_thumbnail_generation_size_is_full_preview():
    assert 120 <= THUMBNAIL_SIZE <= 200


def test_display_thumb_fills_default_sidebar_width():
    assert display_thumb_size(220) == 200
    assert display_thumb_size(160) == 144
    assert display_thumb_size(80) == 120


def test_item_row_is_taller_than_old_list_rows():
    assert item_row_height(220) >= 200


def test_library_path_tooltip_is_full_path(tmp_path):
    path = tmp_path / "Screenshots" / "shot.png"
    assert library_path_tooltip(str(path)) == str(path)


def test_copy_library_path_to_clipboard(qapp, tmp_path):
    path = str(tmp_path / "example.png")
    assert copy_library_path_to_clipboard(path) is True
    assert QGuiApplication.clipboard().text() == path


def test_delegate_size_hint_is_large_thumbnail(qapp):
    delegate = ImageLibraryDelegate(ThumbnailCache())
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 220, 20)
    hint = delegate.sizeHint(option, QModelIndex())
    assert hint == QSize(220, item_row_height(220))
    assert hint.height() >= 200


class _LibrarySettings:
    def __init__(self, root: str) -> None:
        self._root = root

    def value(self, key, type=str):
        if key == SCREENSHOT_SETTINGS_KEY:
            return self._root
        return None

    def setValue(self, key, value) -> None:
        return None


def test_panel_offers_copy_path_context_menu(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    assert panel.list_view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
