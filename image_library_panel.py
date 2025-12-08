from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PyQt6.QtCore import (
    QFileInfo,
    QFileSystemWatcher,
    QModelIndex,
    QSortFilterProxyModel,
    QStandardPaths,
    Qt,
    QTimer,
    QSize,
    pyqtSignal,
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QListView,
    QPushButton,
    QSlider,
    QSizePolicy,
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

    def set_sort_mode(self, mode: str, order: Qt.SortOrder) -> None:
        if self._sort_mode == mode and self._sort_order == order:
            return
        self._sort_mode = mode
        self._sort_order = order
        self.invalidate()

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
            return False
        if self._sort_order == Qt.SortOrder.AscendingOrder:
            return left_val < right_val
        return left_val > right_val

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
            layout.addWidget(widget)

    def update_metadata(self, file_path: Optional[Path]) -> None:
        if not file_path or not file_path.exists():
            self._name_label.setText("Name: --")
            self._size_label.setText("Size: --")
            self._modified_label.setText("Modified: --")
            return
        info = QFileInfo(str(file_path))
        self._name_label.setText(f"Name: {info.fileName()}")
        size_kb = max(1, info.size() // 1024)
        self._size_label.setText(f"Size: {size_kb} KB")
        self._modified_label.setText(f"Modified: {info.lastModified().toString('yyyy-MM-dd HH:mm')}")


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
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._schedule_refresh)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)

        self._build_ui()
        self._install_shortcuts()
        self._connect_signals()
        initial_root = detect_screenshot_folder(settings)
        self.set_root_path(initial_root, persist=False)

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

        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setMovement(QListView.Movement.Static)
        self.list_view.setSpacing(8)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setWrapping(True)
        self.list_view.setIconSize(QSize(120, 120))
        self.list_view.setDragEnabled(True)
        self.list_view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setModel(self._proxy)
        layout.addWidget(self.list_view, 1)

        footer = QVBoxLayout()
        footer.setSpacing(4)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Sort"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Date Modified ↓", ("modified", Qt.SortOrder.DescendingOrder))
        self.sort_combo.addItem("Date Modified ↑", ("modified", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Name A→Z", ("name", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Size ↑", ("size", Qt.SortOrder.AscendingOrder))
        self.sort_combo.addItem("Size ↓", ("size", Qt.SortOrder.DescendingOrder))
        sort_row.addWidget(self.sort_combo)

        sort_row.addWidget(QLabel("Zoom"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(60, 200)
        self.zoom_slider.setValue(120)
        sort_row.addWidget(self.zoom_slider)
        footer.addLayout(sort_row)

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
        self.zoom_slider.valueChanged.connect(self._handle_zoom_change)
        self.export_button.clicked.connect(self.exportRequested.emit)
        self.list_view.doubleClicked.connect(self._handle_activation)
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

    def _handle_selection_changed(self, *_args) -> None:
        index = self.list_view.currentIndex()
        if not index.isValid():
            self.properties_widget.update_metadata(None)
            return
        source_index = self._proxy.mapToSource(index)
        path = Path(self._model.filePath(source_index))
        self.properties_widget.update_metadata(path)

    def _handle_activation(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        file_path = self._model.filePath(source_index)
        if file_path:
            self.assetActivated.emit(file_path)

    def _handle_sort_change(self, idx: int) -> None:
        data = self.sort_combo.itemData(idx)
        if not data:
            return
        mode, order = data
        self._proxy.set_sort_mode(mode, order)
        self._proxy.invalidate()

    def _handle_zoom_change(self, value: int) -> None:
        size = QSize(value, value)
        self.list_view.setIconSize(size)
        self.list_view.update()

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
        self.list_view.setRootIndex(self._proxy.mapFromSource(root_index))
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
        self.list_view.setRootIndex(self._proxy.mapFromSource(root_index))
        self._handle_selection_changed()

    def _schedule_refresh(self, _path: str) -> None:
        self._refresh_timer.start()

    def current_root_path(self) -> Path:
        return self._current_root

    def list_view_widget(self) -> QListView:
        return self.list_view

    def _sync_properties(self) -> None:
        self._handle_selection_changed()