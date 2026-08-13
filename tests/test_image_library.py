from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage
from PyQt6.QtWidgets import QStyleOptionViewItem

from image_library_panel import (
    SCREENSHOT_SETTINGS_KEY,
    THUMBNAIL_SIZE,
    ImageLibraryDelegate,
    ImageLibraryPanel,
    ThumbnailCache,
    copy_library_path_to_clipboard,
    cover_crop_image,
    cover_crop_rect,
    cover_dest_rect,
    display_thumb_size,
    item_row_height,
    library_path_tooltip,
)


def test_thumbnail_generation_size_is_full_preview():
    assert 120 <= THUMBNAIL_SIZE <= 200


def test_display_thumb_fills_default_sidebar_width():
    assert display_thumb_size(220) == 200
    assert display_thumb_size(160) == 160
    assert display_thumb_size(80) == 120


def test_item_row_is_square_tile_without_caption():
    assert item_row_height(220) == display_thumb_size(220)
    assert item_row_height(220) == 200


def test_cover_crop_rect_is_centred_square():
    assert cover_crop_rect(400, 200, 200) == QRect(100, 0, 200, 200)
    assert cover_crop_rect(200, 400, 200) == QRect(0, 100, 200, 200)
    assert cover_crop_rect(200, 200, 200) == QRect(0, 0, 200, 200)


def test_cover_dest_rect_covers_the_tile():
    dest = QRect(0, 0, 200, 200)
    landscape = cover_dest_rect(400, 200, dest)
    assert landscape.contains(dest)
    portrait = cover_dest_rect(200, 400, dest)
    assert portrait.contains(dest)
    assert cover_dest_rect(200, 200, dest) == dest


def test_cover_crop_image_is_square_and_filled():
    source = QImage(400, 200, QImage.Format.Format_RGB32)
    source.fill(QColor(200, 40, 40))
    cropped = cover_crop_image(source, 200)
    assert cropped.width() == 200
    assert cropped.height() == 200
    assert cropped.pixelColor(0, 0) == QColor(200, 40, 40)


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
