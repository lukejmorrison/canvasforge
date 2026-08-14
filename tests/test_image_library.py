from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage
from PyQt6.QtWidgets import QListView, QStyleOptionViewItem

from image_library_panel import (
    COLUMN_COUNT_DEFAULT,
    COLUMNS_SETTINGS_KEY,
    SCREENSHOT_SETTINGS_KEY,
    THUMBNAIL_SIZE,
    ImageLibraryDelegate,
    ImageLibraryPanel,
    ThumbnailCache,
    clamp_column_count,
    copy_library_path_to_clipboard,
    cover_crop_image,
    cover_crop_rect,
    cover_dest_rect,
    display_thumb_size,
    item_row_height,
    item_size_for_columns,
    library_path_tooltip,
    tile_size_for_columns,
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
    assert hint == item_size_for_columns(220, 1)
    assert hint.width() == hint.height()
    assert hint.width() == tile_size_for_columns(220, 1)
    assert hint.width() == 219


def test_clamp_column_count_stays_in_one_to_three():
    assert clamp_column_count(1) == 1
    assert clamp_column_count(2) == 2
    assert clamp_column_count(3) == 3
    assert clamp_column_count(0) == 1
    assert clamp_column_count(9) == 3
    assert clamp_column_count("2") == 2
    assert clamp_column_count(None) == COLUMN_COUNT_DEFAULT
    assert clamp_column_count("nope") == COLUMN_COUNT_DEFAULT


def test_tile_size_tracks_viewport_divided_by_columns():
    assert tile_size_for_columns(220, 1) == 219
    assert item_size_for_columns(220, 1) == QSize(219, 219)
    assert tile_size_for_columns(220, 2) == 109
    assert item_size_for_columns(220, 2) == QSize(109, 109)
    assert tile_size_for_columns(220, 3) == 73
    assert item_size_for_columns(220, 3) == QSize(73, 73)
    assert tile_size_for_columns(300, 1) == 299
    assert tile_size_for_columns(300, 2) == 149
    assert tile_size_for_columns(300, 3) == 99
    assert tile_size_for_columns(220, 1) == 219
    assert tile_size_for_columns(220, 2) * 2 <= 219
    assert tile_size_for_columns(220, 3) * 3 <= 219


def test_delegate_size_hint_follows_column_count(qapp):
    delegate = ImageLibraryDelegate(ThumbnailCache())
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 220, 20)
    delegate.set_columns(1)
    assert delegate.sizeHint(option, QModelIndex()) == QSize(219, 219)
    delegate.set_columns(2)
    assert delegate.sizeHint(option, QModelIndex()) == QSize(109, 109)
    delegate.set_columns(3)
    assert delegate.sizeHint(option, QModelIndex()) == QSize(73, 73)


class _LibrarySettings:
    def __init__(self, root: str, columns=None) -> None:
        self._store = {SCREENSHOT_SETTINGS_KEY: root}
        if columns is not None:
            self._store[COLUMNS_SETTINGS_KEY] = columns

    def value(self, key, defaultValue=None, type=None):
        if key in self._store:
            val = self._store[key]
            if type is not None and val is not None:
                try:
                    return type(val)
                except (TypeError, ValueError):
                    return val
            return val
        return defaultValue

    def setValue(self, key, value) -> None:
        self._store[key] = value


def test_panel_offers_copy_path_context_menu(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    assert panel.list_view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_panel_defaults_to_one_column(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    assert panel.column_count() == 1
    assert panel.columns_combo.currentData() == 1
    assert [panel.columns_combo.itemData(i) for i in range(panel.columns_combo.count())] == [1, 2, 3]
    assert panel.list_view.viewMode() == QListView.ViewMode.IconMode
    assert panel.list_view.isWrapping() is False
    assert panel.list_view.flow() == QListView.Flow.TopToBottom


def test_panel_switches_to_wrapping_grid_for_two_and_three_columns(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    panel.resize(260, 640)
    panel.show()
    qapp.processEvents()

    panel.set_column_count(2)
    assert panel.column_count() == 2
    assert panel.list_view.viewMode() == QListView.ViewMode.IconMode
    assert panel.list_view.isWrapping() is True
    viewport = panel.list_view.viewport().width()
    tile = panel.list_view.gridSize().width()
    assert tile * 2 <= viewport - 1

    panel.set_column_count(3)
    assert panel.column_count() == 3
    viewport = panel.list_view.viewport().width()
    tile = panel.list_view.gridSize().width()
    assert tile * 3 <= viewport - 1

    panel.set_column_count(1)
    qapp.processEvents()
    assert panel.list_view.viewMode() == QListView.ViewMode.IconMode
    assert panel.list_view.isWrapping() is False
    assert panel.list_view.flow() == QListView.Flow.TopToBottom
    one_col_viewport = panel.list_view.viewport().width()
    one_col_tile = panel.list_view.gridSize().width()
    assert one_col_tile == tile_size_for_columns(one_col_viewport, 1)
    assert one_col_tile == one_col_viewport - 1
    assert panel.list_view.gridSize().height() == one_col_tile

    panel.set_column_count(2)
    qapp.processEvents()
    assert panel.list_view.isWrapping() is True
    assert panel.list_view.viewMode() == QListView.ViewMode.IconMode
    assert panel.list_view.gridSize().width() > 0


def test_panel_recalculates_tile_size_on_resize(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    panel.set_column_count(2)
    panel.show()
    qapp.processEvents()
    panel._apply_column_layout()
    viewport = panel.list_view.viewport().width()
    tile = panel.list_view.gridSize().width()
    assert tile > 0
    assert tile * 2 <= viewport - 1
    assert panel.list_view.isWrapping() is True


def test_panel_one_column_tiles_fill_viewport_on_resize(qapp, tmp_path):
    panel = ImageLibraryPanel(settings=_LibrarySettings(str(tmp_path)))
    panel.resize(240, 640)
    panel.show()
    panel.set_column_count(1)
    qapp.processEvents()
    viewport_narrow = panel.list_view.viewport().width()
    tile_narrow = panel.list_view.gridSize().width()
    assert tile_narrow == tile_size_for_columns(viewport_narrow, 1)
    assert tile_narrow == viewport_narrow - 1
    assert panel.list_view.gridSize().height() == tile_narrow
    assert panel.list_view.isWrapping() is False
    assert panel.list_view.flow() == QListView.Flow.TopToBottom

    panel.resize(420, 640)
    qapp.processEvents()
    viewport_wide = panel.list_view.viewport().width()
    tile_wide = panel.list_view.gridSize().width()
    assert tile_wide > tile_narrow
    assert tile_wide == tile_size_for_columns(viewport_wide, 1)
    assert tile_wide == viewport_wide - 1


def test_column_count_persists_in_settings(qapp, tmp_path):
    settings = _LibrarySettings(str(tmp_path))
    panel = ImageLibraryPanel(settings=settings)
    assert panel.column_count() == 1
    panel.set_column_count(3)
    assert settings._store[COLUMNS_SETTINGS_KEY] == 3

    restored = ImageLibraryPanel(settings=settings)
    assert restored.column_count() == 3
    assert restored.columns_combo.currentData() == 3
    assert restored.list_view.viewMode() == QListView.ViewMode.IconMode
