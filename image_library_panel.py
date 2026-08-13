from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from PyQt6.QtCore import (
    QFileInfo,
    QFileSystemWatcher,
    QModelIndex,
    QObject,
    QRect,
    QRunnable,
    QSortFilterProxyModel,
    QStandardPaths,
    QThreadPool,
    Qt,
    QTimer,
    QSize,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QKeySequence,
    QShortcut,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QImage,
    QImageReader,
    QGuiApplication,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QDir
from PyQt6.QtGui import QFileSystemModel


ALLOWED_EXTENSIONS: Tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
)

SCREENSHOT_SETTINGS_KEY = "screenshot_library_dir"
COLUMNS_SETTINGS_KEY = "image_library_columns"

# Thumbnail cache and delegate constants.
# Generate at 200px so previews fill the ~220px sidebar without looking like file icons.
THUMBNAIL_SIZE = 200
THUMBNAIL_MIN = 120
DATE_FORMAT = "yyMMdd HHmmss"
MAX_CACHE_SIZE = 500  # Max number of cached thumbnails
COLUMN_COUNT_MIN = 1
COLUMN_COUNT_MAX = 3
COLUMN_COUNT_DEFAULT = 1


def format_file_size(size_bytes: int) -> str:
    """Return a compact human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size_kb = size_bytes / 1024
    if size_kb < 1024:
        return f"{size_kb:.0f} KB"
    return f"{size_kb / 1024:.1f} MB"


def display_thumb_size(viewport_width: int) -> int:
    """Square tile size that spans the sidebar width, clamped to 120–200px."""
    return min(THUMBNAIL_SIZE, max(THUMBNAIL_MIN, int(viewport_width)))


def item_row_height(viewport_width: int) -> int:
    """List row height for an edge-to-edge square thumbnail (no caption)."""
    return display_thumb_size(viewport_width)


def clamp_column_count(columns: object) -> int:
    """Keep the column control on 1, 2, or 3."""
    try:
        value = int(columns)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return COLUMN_COUNT_DEFAULT
    return max(COLUMN_COUNT_MIN, min(COLUMN_COUNT_MAX, value))


def tile_size_for_columns(viewport_width: int, columns: int) -> int:
    """Square tile edge so ``columns`` thumbnails fit in ``viewport_width``."""
    cols = clamp_column_count(columns)
    available = max(1, int(viewport_width))
    if cols <= 1:
        return display_thumb_size(available)
    return max(1, available // cols)


def item_size_for_columns(viewport_width: int, columns: int) -> QSize:
    """Item size for the current column count.

    One column keeps the full-width list row. Two and three columns use a
    square tile of ``viewport_width / N`` so more thumbs fit in the sidebar.
    """
    cols = clamp_column_count(columns)
    available = max(1, int(viewport_width))
    if cols <= 1:
        return QSize(available, item_row_height(available))
    tile = tile_size_for_columns(available, cols)
    return QSize(tile, tile)


def cover_crop_rect(src_w: int, src_h: int, target: int) -> QRect:
    """Centre square cropped from an image that already cover-fills ``target``."""
    if src_w <= 0 or src_h <= 0 or target <= 0:
        return QRect(0, 0, max(1, target), max(1, target))
    return QRect(
        max(0, (src_w - target) // 2),
        max(0, (src_h - target) // 2),
        min(target, src_w),
        min(target, src_h),
    )


def cover_dest_rect(logical_w: float, logical_h: float, dest: QRect) -> QRect:
    """Destination rect that cover-fills ``dest``. The caller must clip to ``dest``."""
    if logical_w <= 0 or logical_h <= 0 or dest.width() <= 0 or dest.height() <= 0:
        return dest
    scale = max(dest.width() / logical_w, dest.height() / logical_h)
    draw_w = max(1, int(round(logical_w * scale)))
    draw_h = max(1, int(round(logical_h * scale)))
    return QRect(
        dest.left() + (dest.width() - draw_w) // 2,
        dest.top() + (dest.height() - draw_h) // 2,
        draw_w,
        draw_h,
    )


def cover_crop_image(image: QImage, target: int) -> QImage:
    """Scale with cover, then centre-crop to a ``target`` square."""
    if image.isNull() or target <= 0:
        return image
    if image.width() != target or image.height() != target:
        image = image.scaled(
            target,
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
    crop = cover_crop_rect(image.width(), image.height(), target)
    if (
        crop.x() != 0
        or crop.y() != 0
        or crop.width() != image.width()
        or crop.height() != image.height()
    ):
        image = image.copy(crop)
    return image


def library_path_tooltip(file_path: str) -> str:
    """Hover text for a library item: the absolute file path."""
    return str(Path(file_path).expanduser())


def copy_library_path_to_clipboard(path: str) -> bool:
    """Copy an absolute path to the clipboard. Returns True if the clipboard accepted it."""
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return False
    clipboard.setText(path)
    return True


class _ThumbnailSignals(QObject):
    finished = pyqtSignal(str, int, object)  # path, mtime, QImage|None


class _ThumbnailJob(QRunnable):
    def __init__(self, file_path: str, mtime: int, size: int, dpr: float, signals: _ThumbnailSignals):
        super().__init__()
        self.file_path = file_path
        self.mtime = mtime
        self.size = size
        self.dpr = max(1.0, float(dpr))
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            reader = QImageReader(self.file_path)
            if not reader.canRead():
                self.signals.finished.emit(self.file_path, self.mtime, None)
                return
            target = int(self.size * self.dpr)
            reader.setAutoTransform(True)
            native = reader.size()
            if native.isValid() and native.width() > 0 and native.height() > 0:
                scaled_size = native.scaled(
                    target, target, Qt.AspectRatioMode.KeepAspectRatioByExpanding
                )
                reader.setScaledSize(scaled_size)
            image = reader.read()
            if image.isNull():
                # Fallback: full decode then cover-crop (SVG / odd formats).
                image = QImage(self.file_path)
                if image.isNull():
                    self.signals.finished.emit(self.file_path, self.mtime, None)
                    return
            image = cover_crop_image(image, target)
            image.setDevicePixelRatio(self.dpr)
            self.signals.finished.emit(self.file_path, self.mtime, image)
        except Exception:
            self.signals.finished.emit(self.file_path, self.mtime, None)


class ThumbnailCache(QObject):
    """Background thumbnail generator with in-memory caching."""
    
    thumbnailReady = pyqtSignal(str)  # Emitted when a thumbnail is ready (file path)
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._cache: Dict[Tuple[str, int], QPixmap] = {}  # (path, mtime) -> pixmap
        self._pending: Set[str] = set()  # Paths currently being generated
        self._pool = QThreadPool.globalInstance()
        self._signals = _ThumbnailSignals(self)
        self._signals.finished.connect(self._on_job_finished)
        self._placeholder: Optional[QPixmap] = None
    
    def get_thumbnail(self, file_path: str) -> Optional[QPixmap]:
        """Get cached thumbnail or queue for background generation."""
        path = Path(file_path)
        if not path.exists():
            return None
        
        try:
            mtime = int(path.stat().st_mtime)
        except OSError:
            return None
        
        cache_key = (file_path, mtime)
        
        # Return cached thumbnail if available
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Queue for background generation if not already pending
        if file_path not in self._pending:
            self._pending.add(file_path)
            dpr = 1.0
            app = QGuiApplication.instance()
            if app is not None:
                screen = app.primaryScreen()
                if screen is not None:
                    dpr = float(screen.devicePixelRatio())
            job = _ThumbnailJob(file_path, mtime, THUMBNAIL_SIZE, dpr, self._signals)
            self._pool.start(job)
        
        return self._get_placeholder()
    
    def _get_placeholder(self) -> QPixmap:
        """Return a placeholder pixmap for loading thumbnails."""
        if self._placeholder is None:
            self._placeholder = QPixmap(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
            self._placeholder.fill(QColor(60, 60, 60))
            painter = QPainter(self._placeholder)
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.drawText(self._placeholder.rect(), Qt.AlignmentFlag.AlignCenter, "...")
            painter.end()
        return self._placeholder

    def _on_job_finished(self, file_path: str, mtime: int, image: object) -> None:
        self._pending.discard(file_path)
        if image is None or not isinstance(image, QImage) or image.isNull():
            return
        cache_key = (file_path, mtime)
        if cache_key in self._cache:
            return
        pixmap = QPixmap.fromImage(image)
        if len(self._cache) >= MAX_CACHE_SIZE:
            keys_to_remove = list(self._cache.keys())[:MAX_CACHE_SIZE // 10]
            for key in keys_to_remove:
                del self._cache[key]
        self._cache[cache_key] = pixmap
        self.thumbnailReady.emit(file_path)
    
    def clear(self) -> None:
        """Clear the thumbnail cache."""
        self._cache.clear()
        self._pending.clear()


class ImageLibraryDelegate(QStyledItemDelegate):
    """Paints an edge-to-edge cover-cropped thumbnail with no inner padding or caption."""

    def __init__(self, thumbnail_cache: ThumbnailCache, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cache = thumbnail_cache
        self._columns = COLUMN_COUNT_DEFAULT

    def set_columns(self, columns: int) -> None:
        self._columns = clamp_column_count(columns)

    def column_count(self) -> int:
        return self._columns

    def _viewport_width(self, option: QStyleOptionViewItem) -> int:
        widget = option.widget
        if widget is not None:
            return widget.viewport().width()
        return max(option.rect.width(), THUMBNAIL_SIZE)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()

        model = index.model()
        source_index = index
        if hasattr(model, "sourceModel") and hasattr(model, "mapToSource"):
            source_model = model.sourceModel()
            source_index = model.mapToSource(index)
        else:
            source_model = model

        if not isinstance(source_model, QFileSystemModel):
            super().paint(painter, option, index)
            painter.restore()
            return

        file_info = source_model.fileInfo(source_index)
        file_path = file_info.absoluteFilePath()

        tile = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.setClipRect(tile)
        thumbnail = self._cache.get_thumbnail(file_path)
        if thumbnail and not thumbnail.isNull():
            dpr = thumbnail.devicePixelRatio() or 1.0
            logical_w = max(1.0, thumbnail.width() / dpr)
            logical_h = max(1.0, thumbnail.height() / dpr)
            painter.drawPixmap(cover_dest_rect(logical_w, logical_h, tile), thumbnail)

        painter.setClipping(False)
        if selected:
            painter.setPen(QPen(QColor(42, 130, 218), 2))
            painter.drawRect(tile.adjusted(1, 1, -2, -2))
        elif hovered:
            painter.setPen(QPen(QColor(90, 90, 90), 1))
            painter.drawRect(tile.adjusted(0, 0, -1, -1))

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return item_size_for_columns(self._viewport_width(option), self._columns)


class LibrarySortFilterProxy(QSortFilterProxyModel):
    """Proxy model that provides search filtering and flexible sorting."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._search_term = ""
        self._sort_mode = "modified"
        self._sort_order = Qt.SortOrder.DescendingOrder
        self.setDynamicSortFilter(True)

    def set_search_term(self, term: str) -> None:
        lowered = term.strip().lower()
        if self._search_term == lowered:
            return
        self._search_term = lowered
        self.invalidateFilter()
        self.apply_sort()

    def set_sort_mode(self, mode: str, order: Qt.SortOrder) -> None:
        self._sort_mode = mode
        self._sort_order = order
        self.apply_sort()

    def apply_sort(self) -> None:
        self.invalidate()
        self.sort(0, self._sort_order)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            model = self.sourceModel()
            source = self.mapToSource(index)
            if isinstance(model, QFileSystemModel) and source.isValid():
                return library_path_tooltip(model.fileInfo(source).absoluteFilePath())
        return super().data(index, role)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not isinstance(model, QFileSystemModel):
            return super().lessThan(left, right)
        left_info = model.fileInfo(left)
        right_info = model.fileInfo(right)
        if self._sort_mode == "name":
            left_val = left_info.fileName().lower()
            right_val = right_info.fileName().lower()
        elif self._sort_mode == "size":
            left_val = left_info.size()
            right_val = right_info.size()
        else:
            left_val = left_info.lastModified().toSecsSinceEpoch()
            right_val = right_info.lastModified().toSecsSinceEpoch()
        if left_val == right_val:
            return left_info.absoluteFilePath().lower() < right_info.absoluteFilePath().lower()
        return left_val < right_val

    def filterAcceptsRow(  # type: ignore[override]
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        if not self._search_term:
            return True
        model = self.sourceModel()
        if not isinstance(model, QFileSystemModel):
            return True
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True
        file_name = model.fileName(index).lower()
        return self._search_term in file_name


def detect_screenshot_candidates() -> List[Path]:
    pictures_dir_str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    pictures_dir = Path(pictures_dir_str) if pictures_dir_str else Path.home() / "Pictures"
    candidates: List[Path] = []
    screen_names = ["Screenshots", "Screenshot", "ScreenShots", "screen" + "shots"]
    for name in screen_names:
        candidate = pictures_dir / name
        if candidate not in candidates:
            candidates.append(candidate)
    candidates.append(pictures_dir / "CanvasForge")
    candidates.append(pictures_dir)
    candidates.append(Path.home())
    return candidates


def detect_screenshot_folder(settings: Optional[object] = None) -> Path:
    stored: Optional[str] = None
    if settings is not None and hasattr(settings, "value"):
        stored = settings.value(SCREENSHOT_SETTINGS_KEY, type=str)
    if stored:
        path = Path(stored).expanduser()
        if path.exists():
            return path
    for candidate in detect_screenshot_candidates():
        if candidate.exists():
            return candidate
    desktop_str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    fallback = Path(desktop_str) if desktop_str else Path.home()
    return fallback if fallback.exists() else Path.home()


class ImageLibraryProperties(QWidget):
    """Displays metadata for the currently selected library item."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._name_label = QLabel("Name: --")
        self._size_label = QLabel("Size: --")
        self._modified_label = QLabel("Modified: --")
        for widget in (self._name_label, self._size_label, self._modified_label):
            widget.setStyleSheet("color: #ddd;")
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            layout.addWidget(widget)

    def update_metadata(self, file_path: Optional[Path]) -> None:
        if not file_path or not file_path.exists():
            self._name_label.setText("Name: --")
            self._size_label.setText("Size: --")
            self._modified_label.setText("Modified: --")
            return
        info = QFileInfo(str(file_path))
        self._name_label.setText(f"Name: {info.fileName()}")
        self._name_label.setToolTip(library_path_tooltip(str(file_path)))
        self._size_label.setText(f"Size: {format_file_size(info.size())}")
        self._modified_label.setText(f"Modified: {info.lastModified().toString(DATE_FORMAT)}")


class ImageLibraryPanel(QWidget):
    """Resizable panel that surfaces screenshot thumbnails for drag-to-canvas workflows."""

    assetActivated = pyqtSignal(str)
    exportRequested = pyqtSignal()
    folderChanged = pyqtSignal(str)

    def __init__(self, settings: Optional[object] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._current_root = Path()
        self._model = QFileSystemModel(self)
        self._model.setReadOnly(True)
        self._model.setNameFilters([f"*{ext}" for ext in ALLOWED_EXTENSIONS])
        self._model.setNameFilterDisables(False)
        self._model.setFilter(QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self._proxy = LibrarySortFilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.apply_sort()
        self._model.directoryLoaded.connect(lambda _path: self._apply_sort_and_root())
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._schedule_refresh)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)
        
        # Thumbnail cache for background generation
        self._thumbnail_cache = ThumbnailCache(self)
        self._thumbnail_cache.thumbnailReady.connect(self._on_thumbnail_ready)
        self._column_count = self._read_column_count()
        self._applying_layout = False

        self._build_ui()
        self._install_shortcuts()
        self._connect_signals()
        initial_root = detect_screenshot_folder(settings)
        self.set_root_path(initial_root, persist=False)
    
    def _on_thumbnail_ready(self, file_path: str) -> None:
        """Trigger a per-row update when a thumbnail finishes loading."""
        source_index = self._model.index(file_path)
        if not source_index.isValid():
            self.list_view.viewport().update()
            return
        proxy_index = self._proxy.mapFromSource(source_index)
        if proxy_index.isValid():
            self.list_view.update(proxy_index)
        else:
            self.list_view.viewport().update()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(4)
        self.folder_combo = QComboBox()
        self.folder_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.addWidget(self.folder_combo)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search screenshots…")
        header.addWidget(self.search_field)

        self.refresh_button = QPushButton("Refresh")
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self._delegate = ImageLibraryDelegate(self._thumbnail_cache, self)
        self._delegate.set_columns(self._column_count)

        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ViewMode.ListMode)
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setMovement(QListView.Movement.Static)
        self.list_view.setSpacing(6)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setWrapping(False)
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_view.setItemDelegate(self._delegate)
        self.list_view.setDragEnabled(True)
        self.list_view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setMouseTracking(True)
        self.list_view.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.setModel(self._proxy)
        layout.addWidget(self.list_view, 1)

        footer = QVBoxLayout()
        footer.setSpacing(4)

        sort_row = QHBoxLayout()
        sort_row.setSpacing(4)
        sort_row.addWidget(QLabel("Sort"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Date Modified ↓", ("modified", Qt.SortOrder.DescendingOrder))
        self.sort_combo.addItem("Date Modified ↑", ("modified", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Name A→Z", ("name", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Size ↑", ("size", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Size ↓", ("size", Qt.SortOrder.DescendingOrder))
        sort_row.addWidget(self.sort_combo, 1)

        sort_row.addWidget(QLabel("Columns"))
        self.columns_combo = QComboBox()
        self.columns_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for count in range(COLUMN_COUNT_MIN, COLUMN_COUNT_MAX + 1):
            self.columns_combo.addItem(str(count), count)
        sort_row.addWidget(self.columns_combo)
        footer.addLayout(sort_row)

        self._sync_columns_combo()
        self._apply_column_layout()

        self.properties_widget = ImageLibraryProperties()
        footer.addWidget(self.properties_widget)

        export_row = QHBoxLayout()
        self.export_button = QPushButton("Export Canvas")
        export_row.addWidget(self.export_button)
        footer.addLayout(export_row)

        layout.addLayout(footer)
        self._populate_folder_combo()

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_field.setFocus)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh)

    def _connect_signals(self) -> None:
        self.folder_combo.currentIndexChanged.connect(self._handle_folder_selection)
        self.search_field.textChanged.connect(self._proxy.set_search_term)
        self.refresh_button.clicked.connect(self.refresh)
        self.sort_combo.currentIndexChanged.connect(self._handle_sort_change)
        self.columns_combo.currentIndexChanged.connect(self._handle_columns_change)
        self.export_button.clicked.connect(self.exportRequested.emit)
        self.list_view.doubleClicked.connect(self._handle_activation)
        self.list_view.customContextMenuRequested.connect(self._show_item_context_menu)
        selection_model = self.list_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._handle_selection_changed)

    def _populate_folder_combo(self) -> None:
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        for label, path in self._folder_presets():
            self.folder_combo.addItem(label, str(path))
        self.folder_combo.addItem("Browse…", "__browse__")
        self.folder_combo.blockSignals(False)

    def _folder_presets(self) -> Sequence[Tuple[str, Path]]:
        presets = []
        seen = set()
        for candidate in detect_screenshot_candidates():
            resolved = candidate.expanduser()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            presets.append((resolved.name or key, resolved))
        return presets

    def _path_for_index(self, index: QModelIndex) -> Optional[str]:
        if not index.isValid():
            return None
        source_index = self._proxy.mapToSource(index)
        file_path = self._model.filePath(source_index)
        return file_path or None

    def _handle_selection_changed(self, *_args) -> None:
        file_path = self._path_for_index(self.list_view.currentIndex())
        self.properties_widget.update_metadata(Path(file_path) if file_path else None)

    def _handle_activation(self, index: QModelIndex) -> None:
        file_path = self._path_for_index(index)
        if file_path:
            self.assetActivated.emit(file_path)

    def _show_item_context_menu(self, pos) -> None:
        file_path = self._path_for_index(self.list_view.indexAt(pos))
        if not file_path:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy path")
        copy_action.setToolTip(library_path_tooltip(file_path))
        chosen = menu.exec(self.list_view.viewport().mapToGlobal(pos))
        if chosen == copy_action:
            copy_library_path_to_clipboard(file_path)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_column_layout()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_column_layout()

    def _handle_sort_change(self, idx: int) -> None:
        data = self.sort_combo.itemData(idx)
        if not data:
            return
        mode, order = data
        self._proxy.set_sort_mode(mode, order)

    def _read_column_count(self) -> int:
        if self.settings is None or not hasattr(self.settings, "value"):
            return COLUMN_COUNT_DEFAULT
        raw = self.settings.value(COLUMNS_SETTINGS_KEY, COLUMN_COUNT_DEFAULT)
        return clamp_column_count(raw)

    def column_count(self) -> int:
        return self._column_count

    def set_column_count(self, columns: int, persist: bool = True) -> None:
        value = clamp_column_count(columns)
        self._column_count = value
        self._delegate.set_columns(value)
        self._sync_columns_combo()
        self._apply_column_layout()
        if persist and self.settings is not None and hasattr(self.settings, "setValue"):
            self.settings.setValue(COLUMNS_SETTINGS_KEY, value)

    def _sync_columns_combo(self) -> None:
        idx = self.columns_combo.findData(self._column_count)
        if idx < 0:
            idx = self.columns_combo.findData(COLUMN_COUNT_DEFAULT)
        if idx < 0:
            return
        self.columns_combo.blockSignals(True)
        self.columns_combo.setCurrentIndex(idx)
        self.columns_combo.blockSignals(False)

    def _handle_columns_change(self, idx: int) -> None:
        data = self.columns_combo.itemData(idx)
        if data is None:
            return
        self.set_column_count(int(data), persist=True)

    def _apply_column_layout(self) -> None:
        if self._applying_layout or not hasattr(self, "list_view"):
            return
        self._applying_layout = True
        try:
            columns = clamp_column_count(self._column_count)
            viewport_width = max(1, self.list_view.viewport().width())
            size = item_size_for_columns(viewport_width, columns)
            self._delegate.set_columns(columns)
            if columns <= 1:
                self.list_view.setViewMode(QListView.ViewMode.ListMode)
                self.list_view.setWrapping(False)
                self.list_view.setSpacing(6)
                self.list_view.setGridSize(QSize())
            else:
                self.list_view.setViewMode(QListView.ViewMode.IconMode)
                self.list_view.setFlow(QListView.Flow.LeftToRight)
                self.list_view.setWrapping(True)
                self.list_view.setSpacing(0)
                self.list_view.setGridSize(size)
                self.list_view.setIconSize(size)
            self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
            self.list_view.setMovement(QListView.Movement.Static)
            self.list_view.setUniformItemSizes(True)
            self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.list_view.doItemsLayout()
        finally:
            self._applying_layout = False

    def _handle_folder_selection(self, index: int) -> None:
        data = self.folder_combo.itemData(index)
        if data == "__browse__":
            folder = QFileDialog.getExistingDirectory(self, "Choose Screenshot Folder", str(self._current_root))
            if folder:
                self.set_root_path(Path(folder), persist=True)
            else:
                self._sync_combo_with_current()
            return
        if data:
            self.set_root_path(Path(str(data)), persist=True)

    def _sync_combo_with_current(self) -> None:
        current_str = str(self._current_root)
        for idx in range(self.folder_combo.count()):
            if str(self.folder_combo.itemData(idx)) == current_str:
                self.folder_combo.setCurrentIndex(idx)
                return
        self.folder_combo.setCurrentIndex(0)

    def set_root_path(self, path: Path, persist: bool = True) -> None:
        normalized = path.expanduser()
        normalized.mkdir(parents=True, exist_ok=True)
        if normalized == self._current_root:
            return
        self._current_root = normalized
        directories = self._watcher.directories()
        if directories:
            self._watcher.removePaths(directories)
        self._watcher.addPath(str(self._current_root))
        root_index = self._model.setRootPath(str(self._current_root))
        self._apply_sort_and_root(root_index)
        self.folderChanged.emit(str(self._current_root))
        if persist and self.settings is not None and hasattr(self.settings, "setValue"):
            self.settings.setValue(SCREENSHOT_SETTINGS_KEY, str(self._current_root))
        self.refresh()
        self._sync_combo_with_current()

    def refresh(self) -> None:
        if not self._current_root:
            return
        # QFileSystemModel has no explicit refresh; toggle root path to force reload
        current = str(self._current_root)
        self._model.setRootPath("")
        root_index = self._model.setRootPath(current)
        self._apply_sort_and_root(root_index)
        self._handle_selection_changed()

    def _apply_sort_and_root(self, root_index: Optional[QModelIndex] = None) -> None:
        """Re-sort and keep the view anchored to the selected library folder."""
        if not self._current_root:
            return
        source_root = root_index if root_index is not None else self._model.index(str(self._current_root))
        self._proxy.apply_sort()
        self.list_view.setRootIndex(self._proxy.mapFromSource(source_root))

    def _schedule_refresh(self, _path: str) -> None:
        self._refresh_timer.start()

    def current_root_path(self) -> Path:
        return self._current_root

    def list_view_widget(self) -> QListView:
        return self.list_view

    def _sync_properties(self) -> None:
        self._handle_selection_changed()
