import sys
import tempfile
import subprocess
import os
import time
import math

# Force X11 backend on Wayland+NVIDIA to prevent compositor lockups
# See: featurerequest/ProblemLog_WaylandCosmicLockup.md
if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
    try:
        result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=5)
        if 'NVIDIA' in result.stdout:
            os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
    except Exception:
        pass  # Fall through to default behavior

from enum import Enum, auto
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
             QGraphicsPixmapItem, QListWidget,
             QToolBar, QFileDialog, QVBoxLayout, QWidget, QDockWidget,
             QGraphicsRectItem, QGraphicsEllipseItem, QListWidgetItem, QLabel,
             QAbstractItemView, QGraphicsItem, QGraphicsTextItem, QMenu, QSplitter,
             QDialog, QDialogButtonBox, QTabWidget, QFormLayout, QLineEdit,
             QPushButton, QHBoxLayout, QGroupBox, QFrame, QComboBox, QCheckBox,
             QToolButton, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
             QMessageBox)
import shutil

__version__ = "1.5.0"
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer
from PyQt6 import sip
from PyQt6.QtGui import (QPixmap, QImageReader, QAction, QPainter, QIcon, QPen, QColor, QBrush,
                     QFont, QTransform, QClipboard, QImage, QKeySequence, QTextCursor, QPalette,
                     QFontMetrics)
from PyQt6.QtCore import (Qt, QTimer, QPointF, QPoint, pyqtSignal, QRectF, QSize, QSettings, 
                          QByteArray, QMimeData, QBuffer, QIODevice, QSizeF, QUrl)
from pathlib import Path
import datetime
from image_library_panel import ImageLibraryPanel
from undo_manager import UndoManager
from plugin_manager import PluginManager


class ToolType(Enum):
    SELECT = auto()
    MOVE = auto()
    ROTATE = auto()
    SCALE = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()
    ALIGN_GRID = auto()
    SELECTION = auto()


class FillMode(Enum):
    TRANSPARENT = auto()
    AUTO_FILL = auto()


class FlowLayout(QVBoxLayout):
    """
    A simple flow layout implementation that arranges widgets horizontally
    and wraps to new rows when there's not enough space.
    """
    def __init__(self, parent=None, margin=5, h_spacing=5, v_spacing=5):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        self._row_layouts = []  # Track row layouts for cleanup
        self._last_width = 0
        
    def addWidget(self, widget):
        """Add a widget to the flow layout."""
        self._items.append(widget)
        widget.setParent(self.parentWidget())
        
    def clear(self):
        """Clear all widgets - actually deletes them."""
        # First remove from rows
        self._remove_row_layouts()
        # Then delete widgets
        for widget in self._items:
            widget.setParent(None)
            widget.deleteLater()
        self._items.clear()
    
    def _remove_row_layouts(self):
        """Remove row layouts without deleting the widgets."""
        for row_layout in self._row_layouts:
            # Remove widgets from row (but don't delete them)
            while row_layout.count() > 0:
                item = row_layout.takeAt(0)
                # Just remove, don't delete the widget
        
        # Remove row layouts from this layout
        while self.count() > 0:
            item = self.takeAt(0)
            # Delete the layout wrapper, not widgets
        
        self._row_layouts.clear()
    
    def rebuild(self, available_width):
        """Rebuild the layout for the given width."""
        # Skip if width hasn't changed significantly
        if abs(available_width - self._last_width) < 10:
            return
        self._last_width = available_width
        
        # Remove existing row layouts (keep widgets)
        self._remove_row_layouts()
        
        if not self._items:
            return
            
        # Create rows of widgets
        current_row = QHBoxLayout()
        current_row.setSpacing(self._h_spacing)
        self._row_layouts.append(current_row)
        current_width = 0
        margin = self.contentsMargins().left() + self.contentsMargins().right()
        max_width = max(100, available_width - margin - 20)  # 20px buffer, minimum 100
        
        for widget in self._items:
            if not widget or not hasattr(widget, 'sizeHint'):
                continue
            widget_width = widget.sizeHint().width()
            
            if current_width + widget_width > max_width and current_width > 0:
                # Start new row
                current_row.addStretch()
                super().addLayout(current_row)
                current_row = QHBoxLayout()
                current_row.setSpacing(self._h_spacing)
                self._row_layouts.append(current_row)
                current_width = 0
            
            current_row.addWidget(widget)
            current_width += widget_width + self._h_spacing
        
        # Add last row
        if current_row.count() > 0:
            current_row.addStretch()
            super().addLayout(current_row)


class WrappingToolBar(QWidget):
    """A toolbar widget that wraps buttons to new rows when space is limited."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = FlowLayout(self, margin=5, h_spacing=2, v_spacing=2)
        self._buttons = []
        self._separators = []
        self._icon_size = QSizeF(48, 48).toSize()
        self._button_style = Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        self._button_min_width = 116
        self._button_height = 94
        self.setStyleSheet(
            """
            QToolButton {
                font-size: 10pt;
                font-weight: bold;
                padding: 2px;
            }
            """
        )

    def _update_button_geometry(self):
        if not self._buttons:
            return
        font = self._buttons[0].font()
        metrics = QFontMetrics(font)
        max_text_width = self._button_min_width
        for btn in self._buttons:
            text = btn.text() or ""
            text_width = metrics.horizontalAdvance(text) + 18
            max_text_width = max(max_text_width, text_width)

        for btn in self._buttons:
            btn.setFixedWidth(max_text_width)
            btn.setFixedHeight(self._button_height)

        for sep in self._separators:
            sep.setFixedHeight(self._button_height - 10)
        
    def setIconSize(self, size):
        self._icon_size = size
        for btn in self._buttons:
            btn.setIconSize(self._icon_size)
        self._update_button_geometry()
    
    def iconSize(self):
        return self._icon_size
    
    def setToolButtonStyle(self, style):
        self._button_style = style
        for btn in self._buttons:
            btn.setToolButtonStyle(self._button_style)
        self._update_button_geometry()
    
    def addAction(self, action):
        """Add an action as a tool button."""
        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setIconSize(self._icon_size)
        btn.setToolButtonStyle(self._button_style)
        btn.setAutoRaise(False)
        self._buttons.append(btn)
        self._layout.addWidget(btn)
        self._update_button_geometry()
        return btn
    
    def addSeparator(self):
        """Add a visual separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(2)
        sep.setFixedHeight(self._button_height - 10)
        self._separators.append(sep)
        self._layout.addWidget(sep)
    
    def clear(self):
        """Clear all buttons and separators."""
        self._layout.clear()
        self._buttons.clear()
        self._separators.clear()
    
    def resizeEvent(self, event):
        """Rebuild layout when resized."""
        super().resizeEvent(event)
        self._layout.rebuild(self.width())


class ResizeHandle(QGraphicsRectItem):
    def __init__(self, handles, cursor):
        size = handles.handle_size
        super().__init__(-size / 2, -size / 2, size, size)
        self.handles = handles
        self.parent_item = handles.parent_item
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(cursor)
        self.setZValue(self.parent_item.zValue() + 1.5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        handle_color = QColor("blue")
        handle_color.setAlpha(128)
        self.setPen(QPen(QColor("blue"), 2))
        self.setBrush(QBrush(handle_color))
        self._start_center = None
        self._start_vector = None
        self._start_scale = 1.0

    def cleanup(self):
        if self.scene():
            self.scene().removeItem(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.parent_item, 'handle_resize_press'):
                self.parent_item.handle_resize_press(self, event.scenePos())
                event.accept()
                return
            rect = self.parent_item.boundingRect()
            self._start_center = self.parent_item.mapToScene(rect.center())
            self._start_vector = event.scenePos() - self._start_center
            self._start_scale = self.parent_item.scale()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_vector is None:
            if hasattr(self.parent_item, 'handle_resize_drag'):
                self.parent_item.handle_resize_drag(self, event.scenePos())
                event.accept()
                return
            super().mouseMoveEvent(event)
            return
        start_length = math.hypot(self._start_vector.x(), self._start_vector.y())
        if start_length == 0:
            return
        current_vector = event.scenePos() - self._start_center
        current_length = math.hypot(current_vector.x(), current_vector.y())
        if current_length == 0:
            return
        factor = max(0.1, min(10.0, current_length / start_length))
        self.parent_item.setScale(self._start_scale * factor)
        self.handles.update_handles()
        event.accept()

    def mouseReleaseEvent(self, event):
        if hasattr(self.parent_item, 'handle_resize_release'):
            self.parent_item.handle_resize_release(self, event.scenePos())
            self.handles.update_handles()
            self._start_vector = None
            self._start_center = None
            event.accept()
            return
        self._start_vector = None
        self._start_center = None
        self.handles.update_handles()
        event.accept()


class RotateHandle(QGraphicsEllipseItem):
    def __init__(self, handles):
        size = handles.handle_size
        super().__init__(-size / 2, -size / 2, size, size)
        self.handles = handles
        self.parent_item = handles.parent_item
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(self.parent_item.zValue() + 1.5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        handle_color = QColor("blue")
        handle_color.setAlpha(128)
        self.setPen(QPen(QColor("blue"), 2))
        self.setBrush(QBrush(handle_color))
        self._start_center = None
        self._start_vector = None
        self._start_rotation = 0.0

    def cleanup(self):
        if self.scene():
            self.scene().removeItem(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.parent_item.boundingRect()
            self._start_center = self.parent_item.mapToScene(rect.center())
            self._start_vector = event.scenePos() - self._start_center
            self._start_rotation = self.parent_item.rotation()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_vector is None:
            super().mouseMoveEvent(event)
            return
        start_angle = math.degrees(math.atan2(self._start_vector.y(), self._start_vector.x()))
        current_vector = event.scenePos() - self._start_center
        current_angle = math.degrees(math.atan2(current_vector.y(), current_vector.x()))
        delta = current_angle - start_angle
        self.parent_item.setRotation(self._start_rotation + delta)
        self.handles.update_handles()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._start_vector = None
        self._start_center = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.handles.update_handles()
        event.accept()


class SelectionHandles:
    """Manages resize/rotate handles for a parent item."""

    def __init__(self, parent):
        self.parent_item = parent
        self.handle_size = 12
        self.resize_handles = []
        self.rotate_handle = None
        self._create_handles()
        self.update_handles()

    def _create_handles(self):
        scene = self.parent_item.scene()
        if not scene:
            return
        cursors = [
            Qt.CursorShape.SizeFDiagCursor,
            Qt.CursorShape.SizeBDiagCursor,
            Qt.CursorShape.SizeFDiagCursor,
            Qt.CursorShape.SizeBDiagCursor,
            Qt.CursorShape.SizeVerCursor,
            Qt.CursorShape.SizeHorCursor,
            Qt.CursorShape.SizeVerCursor,
            Qt.CursorShape.SizeHorCursor,
        ]
        self.resize_handles = []
        for cursor in cursors:
            handle = ResizeHandle(self, cursor)
            handle.handle_index = len(self.resize_handles)
            scene.addItem(handle)
            self.resize_handles.append(handle)
        if getattr(self.parent_item, 'supports_rotation_handles', True):
            self.rotate_handle = RotateHandle(self)
            scene.addItem(self.rotate_handle)
        else:
            self.rotate_handle = None

    def update_handles(self):
        if not self.parent_item.scene():
            return
        rect = self.parent_item.boundingRect()
        if rect.isEmpty():
            return
        points = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomRight(),
            rect.bottomLeft(),
            rect.topLeft() + QPointF(rect.width() / 2, 0),
            rect.topLeft() + QPointF(rect.width(), rect.height() / 2),
            rect.bottomLeft() + QPointF(rect.width() / 2, 0),
            rect.bottomLeft() + QPointF(0, -rect.height() / 2),
        ]
        for handle, point in zip(self.resize_handles, points):
            scene_point = self.parent_item.mapToScene(point)
            handle.setPos(scene_point)
            handle.setZValue(self.parent_item.zValue() + 2)
        if self.rotate_handle:
            rot_point = rect.topLeft() + QPointF(rect.width() / 2, -20)
            scene_rot = self.parent_item.mapToScene(rot_point)
            self.rotate_handle.setPos(scene_rot)
            self.rotate_handle.setZValue(self.parent_item.zValue() + 2)

    def cleanup(self):
        for handle in self.resize_handles:
            handle.cleanup()
        self.resize_handles.clear()
        if self.rotate_handle:
            self.rotate_handle.cleanup()
            self.rotate_handle = None



def _normalize_screen_point(screen_pos):
    """Returns a QPoint for various QPoint/QPointF-returning APIs."""
    if screen_pos is None:
        return QPoint()
    if isinstance(screen_pos, QPoint):
        return screen_pos
    if hasattr(screen_pos, 'toPoint'):
        return screen_pos.toPoint()
    if hasattr(screen_pos, 'x') and hasattr(screen_pos, 'y'):
        return QPoint(int(screen_pos.x()), int(screen_pos.y()))
    return QPoint()


class ContextMenuForwarder:
    def _forward_context_menu(self, event):
        scene = self.scene()
        if not scene:
            return False
        views = scene.views()
        if not views:
            return False
        view = views[0]
        if hasattr(view, '_show_context_menu'):
            global_pos = _normalize_screen_point(event.screenPos())
            if view._show_context_menu(global_pos, event.scenePos(), clicked_items=[self]):
                event.accept()
                return True
        return False


class CanvasRectItem(ContextMenuForwarder, QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasEllipseItem(ContextMenuForwarder, QGraphicsEllipseItem):
    def __init__(self, rect):
        super().__init__(rect)

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasTextItem(ContextMenuForwarder, QGraphicsTextItem):
    def __init__(self, text):
        super().__init__(text)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.document().contentsChanged.connect(self._update_transform_origin)
        self._update_transform_origin()

    def _update_transform_origin(self):
        rect = self.boundingRect()
        if rect.isEmpty():
            return
        self.setTransformOriginPoint(rect.center())

    def enter_edit_mode(self, select_all=False):
        if self._editing:
            return
        self._editing = True
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        if select_all:
            cursor.select(QTextCursor.SelectionType.Document)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def leave_edit_mode(self):
        if not self._editing:
            return
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def is_editing(self):
        return self._editing

    def mouseDoubleClickEvent(self, event):
        self.enter_edit_mode()
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.leave_edit_mode()

    def contextMenuEvent(self, event):
        if self._editing:
            super().contextMenuEvent(event)
            return
        if self._forward_context_menu(event):
            return
        event.accept()

    def keyPressEvent(self, event):
        if self._editing and event.key() == Qt.Key.Key_Escape:
            self.leave_edit_mode()
            self.clearFocus()
            event.accept()
            return
        super().keyPressEvent(event)


class SelectionOverlay(QGraphicsRectItem):
    supports_rotation_handles = False

    def __init__(self, owner):
        super().__init__(0, 0, 0, 0)
        self.owner = owner
        pen = QPen(QColor("yellow"), 2, Qt.PenStyle.DashLine)
        self.supports_rotation_handles = False
        self.setPen(pen)
        fill = QColor("yellow")
        fill.setAlpha(50)
        self.setBrush(QBrush(fill))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setZValue(owner.zValue() + 5)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setVisible(True)
        self._active_handle_index = None
        self._drag_start_rect = QRectF()

    def contextMenuEvent(self, event):
        scene = self.scene()
        if scene:
            views = scene.views()
            if views and hasattr(views[0], '_show_context_menu'):
                global_pos = _normalize_screen_point(event.screenPos())
                if views[0]._show_context_menu(global_pos, event.scenePos(), clicked_items=[self]):
                    event.accept()
                    return
        super().contextMenuEvent(event)

    def set_scene_rect(self, rect: QRectF):
        norm = rect.normalized()
        self.prepareGeometryChange()
        self.setRect(0, 0, norm.width(), norm.height())
        self.setPos(norm.topLeft())
        if hasattr(self, 'handles') and self.handles:
            self.handles.update_handles()

    def scene_rect(self) -> QRectF:
        rect = self.rect()
        top_left = self.scenePos()
        return QRectF(top_left, QSizeF(rect.width(), rect.height()))

    def handle_resize_press(self, handle, scene_pos):
        self._active_handle_index = getattr(handle, 'handle_index', None)
        self._drag_start_rect = self.scene_rect()

    def handle_resize_drag(self, handle, scene_pos):
        if self._active_handle_index is None:
            return
        rect = QRectF(self._drag_start_rect)
        idx = self._active_handle_index
        if idx in (0, 3, 7):
            rect.setLeft(scene_pos.x())
        if idx in (1, 2, 5):
            rect.setRight(scene_pos.x())
        if idx in (0, 1, 4):
            rect.setTop(scene_pos.y())
        if idx in (2, 3, 6):
            rect.setBottom(scene_pos.y())
        rect = rect.normalized()
        self.set_scene_rect(rect)

    def handle_resize_release(self, handle, scene_pos):
        self._active_handle_index = None
        self._drag_start_rect = QRectF()


class RasterItem(ContextMenuForwarder, QGraphicsPixmapItem):
    def __init__(self, pixmap):
        pixmap = self._ensure_argb_pixmap(pixmap)
        super().__init__(pixmap)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        self.image_bytes = bytes(ba)
        self.handles = None
        self._selection_overlay = None
        self._selection_start_scene = None

    @staticmethod
    def _ensure_argb_pixmap(pixmap: QPixmap) -> QPixmap:
        image = pixmap.toImage()
        if image.format() not in (
                QImage.Format.Format_ARGB32,
                QImage.Format.Format_ARGB32_Premultiplied,
        ):
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            return QPixmap.fromImage(image)
        return pixmap

    def startSelectionOverlay(self, scene_pos):
        self.clearSelectionOverlay()
        if not self.scene():
            return None
        self._selection_start_scene = scene_pos
        self._selection_overlay = SelectionOverlay(self)
        self.scene().addItem(self._selection_overlay)
        self._selection_overlay.set_scene_rect(QRectF(scene_pos, scene_pos))
        self._selection_overlay.setZValue(self.zValue() + 5)
        self._selection_overlay.setSelected(True)
        self._selection_overlay.setFocus()
        return self._selection_overlay

    def updateSelectionOverlay(self, scene_pos):
        if not self._selection_overlay or self._selection_start_scene is None:
            return
        rect_scene = QRectF(self._selection_start_scene, scene_pos).normalized()
        self._selection_overlay.set_scene_rect(rect_scene)

    def lockSelectionOverlay(self):
        self._selection_start_scene = None

    def selectionOverlay(self):
        return self._selection_overlay

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)

    def hasSelectionOverlay(self):
        return self._selection_overlay is not None

    def activateSelectionOverlay(self):
        if self._selection_overlay:
            self._selection_overlay.setZValue(self.zValue() + 5)
            self._selection_overlay.setSelected(True)
            self._selection_overlay.setFocus()

    def clearSelectionOverlay(self):
        if self._selection_overlay and self._selection_overlay.scene():
            if self._selection_overlay.isSelected():
                self._selection_overlay.setSelected(False)
            self._selection_overlay.scene().removeItem(self._selection_overlay)
        self._selection_overlay = None
        self._selection_start_scene = None

    def _selection_rects(self):
        if not self._selection_overlay:
            return None, None
        scene_rect = self._selection_overlay.scene_rect()
        top_left_local = self.mapFromScene(scene_rect.topLeft())
        bottom_right_local = self.mapFromScene(scene_rect.bottomRight())
        local_rect = QRectF(top_left_local, bottom_right_local).normalized()
        pix_rect = QRectF(0, 0, self.pixmap().width(), self.pixmap().height())
        clipped = local_rect.intersected(pix_rect)
        if clipped.isEmpty():
            return None, scene_rect
        return clipped, scene_rect

    def endSelection(self, target_center_scene_pos=None, fill_mode=FillMode.TRANSPARENT, remove_original=True):
        local_rect, scene_rect = self._selection_rects()
        if not local_rect:
            self.clearSelectionOverlay()
            return None

        select_rect_int = local_rect.toAlignedRect()
        cropped_image = self.pixmap().toImage().copy(select_rect_int)
        cropped_image = cropped_image.convertToFormat(QImage.Format.Format_ARGB32)
        cropped_pixmap = QPixmap.fromImage(cropped_image)

        if remove_original:
            base_image = self.pixmap().toImage().convertToFormat(QImage.Format.Format_ARGB32)
            painter = QPainter(base_image)
            if fill_mode == FillMode.TRANSPARENT:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillRect(select_rect_int, Qt.GlobalColor.transparent)
            elif fill_mode == FillMode.AUTO_FILL:
                avg_color = self.pixmap().toImage().pixelColor(local_rect.center().toPoint())
                painter.fillRect(select_rect_int, avg_color)
            painter.end()

            self.setPixmap(QPixmap.fromImage(base_image))
            self.updateImageBytes()

        new_item = RasterItem(cropped_pixmap)
        new_item.setScale(self.scale())
        new_item.setRotation(self.rotation())
        center_scene = target_center_scene_pos if target_center_scene_pos is not None else scene_rect.center()
        new_item.setPos(self._scene_pos_for_center(new_item, center_scene))

        self.clearSelectionOverlay()
        return new_item

    @staticmethod
    def _scene_pos_for_center(item, center_scene_pos):
        center_vec = QPointF(item.pixmap().width() / 2, item.pixmap().height() / 2)
        scale = item.scale()
        theta = math.radians(item.rotation())
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        rotated = QPointF(
            (center_vec.x() * cos_t - center_vec.y() * sin_t) * scale,
            (center_vec.x() * sin_t + center_vec.y() * cos_t) * scale,
        )
        return center_scene_pos - rotated

    def updateImageBytes(self):
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.pixmap().save(buffer, "PNG")
        buffer.close()
        self.image_bytes = bytes(ba)

    def itemChange(self, change, value):
        geometry_changes = {
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged,
        }
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                if not self.handles:
                    self.handles = SelectionHandles(self)
            else:
                if self.handles:
                    self.handles.cleanup()
                    self.handles = None
                self.clearSelectionOverlay()
        elif change in geometry_changes:
            if self.handles:
                self.handles.update_handles()
        elif change == QGraphicsItem.GraphicsItemChange.ItemZValueHasChanged:
            if self._selection_overlay:
                self._selection_overlay.setZValue(value + 5)
        elif change == QGraphicsItem.GraphicsItemChange.ItemSceneChange and value is None:
            self.clearSelectionOverlay()
        return super().itemChange(change, value)



class VectorItem(ContextMenuForwarder, QGraphicsSvgItem):
    def __init__(self, renderer):
        super().__init__()
        self.setSharedRenderer(renderer)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.renderer = renderer
        rect = self.boundingRect()
        self.setTransformOriginPoint(rect.width() / 2, rect.height() / 2)
        self.handles = None

    def itemChange(self, change, value):
        geometry_changes = {
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged,
        }
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                if not self.handles:
                    self.handles = SelectionHandles(self)
            else:
                if self.handles:
                    self.handles.cleanup()
                    self.handles = None
        elif change in geometry_changes:
            if self.handles:
                self.handles.update_handles()
        return super().itemChange(change, value)

        def contextMenuEvent(self, event):
            if self._forward_context_menu(event):
                return
            super().contextMenuEvent(event)

    def edit_with_inkscape(self):
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as temp_file:
            temp_path = temp_file.name
            rect = self.boundingRect()
            with open(temp_path, 'w') as f:
                f.write(
                    f'<svg width="{rect.width()}" height="{rect.height()}" '
                    'xmlns="http://www.w3.org/2000/svg"><rect width="100%" '
                    'height="100%" fill="red"/></svg>'
                )

        try:
            proc = subprocess.Popen(['inkscape', temp_path])
            while proc.poll() is None:
                QApplication.processEvents()
                time.sleep(0.1)

            if os.path.exists(temp_path):
                new_renderer = QSvgRenderer(temp_path)
                if new_renderer.isValid():
                    self.setSharedRenderer(new_renderer)
                    self.renderer = new_renderer
                os.unlink(temp_path)
        except FileNotFoundError:
            print("Inkscape not found")
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def add_handles_support(item_class):
    original_item_change = item_class.itemChange

    def new_item_change(self, change, value):
        geometry_changes = {
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged,
        }
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                if not hasattr(self, 'handles') or not self.handles:
                    self.handles = SelectionHandles(self)
            else:
                if hasattr(self, 'handles') and self.handles:
                    self.handles.cleanup()
                    self.handles = None
        elif change in geometry_changes:
            if hasattr(self, 'handles') and self.handles:
                self.handles.update_handles()
        return original_item_change(self, change, value) if original_item_change else value

    item_class.itemChange = new_item_change
    return item_class


add_handles_support(CanvasRectItem)
add_handles_support(CanvasEllipseItem)
add_handles_support(CanvasTextItem)


class ArtifactList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)


class LayerList(QListWidget):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.update_z_orders()

    def update_z_orders(self):
        count = self.count()
        for i in range(count):
            item = self.item(i)
            graphics_item = item.data(Qt.ItemDataRole.UserRole)
            if graphics_item:
                graphics_item.setZValue(count - i)
        self.scene.update()

    def graphics_items(self):
        items = []
        for i in range(self.count()):
            list_item = self.item(i)
            graphics_item = list_item.data(Qt.ItemDataRole.UserRole)
            if graphics_item:
                items.append(graphics_item)
        return items

    def remove_graphics_items(self, graphics_items):
        if not graphics_items:
            return
        removed = False
        for i in reversed(range(self.count())):
            list_item = self.item(i)
            graphics_item = list_item.data(Qt.ItemDataRole.UserRole)
            if graphics_item in graphics_items:
                self.takeItem(i)
                removed = True
        if removed:
            self.update_z_orders()


class CanvasView(QGraphicsView):
    itemAdded = pyqtSignal(object)
    cursorMoved = pyqtSignal(object)

    def __init__(self, scene, artifact_list, main_window):
        super().__init__(scene)
        self.artifact_list = artifact_list
        self.main_window = main_window
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.current_tool = ToolType.SELECT
        self._drawing_item = None
        self._interacting_item = None
        self._start_pos = None
        self._start_rotation = 0
        self._start_scale = 1.0
        self._active_plugin_tool = None  # Plugin that handles mouse events
        self.snap_grid = False
        self._zoom_factor = 1.0
        self._selection_host = None
        self._selection_creating = False
        self._selection_drop_active = False
        self._selection_drop_pos = None

    def set_tool(self, tool):
        if self.current_tool == ToolType.SELECTION and tool != ToolType.SELECTION:
            self._cancel_selection_mode()
        self.current_tool = tool
        if tool == ToolType.SELECT:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._apply_cursor()

    def fit_all_items(self):
        """Zoom and pan to fit all items in the scene."""
        items = [item for item in self.scene().items() if item.isVisible() and item.boundingRect().isValid()]
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        # Add some padding
        padding = 50
        rect.adjust(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # Update internal zoom factor to match
        transform = self.transform()
        self._zoom_factor = transform.m11()

    def fit_item(self, item):
        """Zoom and pan to fit a specific item."""
        if not item or not item.isVisible():
            return
        rect = item.sceneBoundingRect()
        # Add some padding
        padding = 50
        rect.adjust(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # Update internal zoom factor to match
        transform = self.transform()
        self._zoom_factor = transform.m11()

    def pan_to_item(self, item):
        """Pan to center on a specific item without changing zoom."""
        if not item or not item.isVisible():
            return
        self.centerOn(item)

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._zoom_factor *= factor
        self._zoom_factor = max(0.1, min(10.0, self._zoom_factor))
        cursor_pos = self.mapToScene(event.position().toPoint())
        self.setTransform(QTransform().scale(self._zoom_factor, self._zoom_factor))
        self.centerOn(cursor_pos)

    def set_active_plugin_tool(self, plugin_instance):
        """Set the active plugin tool that receives mouse events."""
        self._active_plugin_tool = plugin_instance

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)
            return

        # Delegate to active plugin tool first
        if self._active_plugin_tool and hasattr(self._active_plugin_tool, '_on_view_mouse_press'):
            if self._active_plugin_tool._on_view_mouse_press(event):
                return

        scene_pos = self.mapToScene(event.pos())
        clicked_item = self.itemAt(event.pos())

        if self.current_tool == ToolType.SELECTION:
            self._handle_selection_press(event, scene_pos, clicked_item)
            return

        if self.current_tool in (ToolType.RECTANGLE, ToolType.ELLIPSE):
            self._start_pos = scene_pos
            if self.current_tool == ToolType.RECTANGLE:
                self._drawing_item = CanvasRectItem(QRectF(scene_pos, scene_pos))
            else:
                self._drawing_item = CanvasEllipseItem(QRectF(scene_pos, scene_pos))
            if self._drawing_item:
                self._drawing_item.setPen(QPen(Qt.GlobalColor.black, 2))
                self._drawing_item.setBrush(QBrush(QColor(100, 100, 255, 100)))
                self.scene().addItem(self._drawing_item)
            return
        elif self.current_tool == ToolType.TEXT:
            text_item = CanvasTextItem("Text")
            text_item.setPos(scene_pos)
            text_item.setFont(QFont("Arial", 12))
            text_item._update_transform_origin()
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            self.scene().addItem(text_item)
            self.itemAdded.emit(text_item)
            text_item.enter_edit_mode(select_all=True)
            return
        elif self.current_tool in (ToolType.ROTATE, ToolType.SCALE):
            item = self.scene().itemAt(scene_pos, self.transform())
            if item:
                self._interacting_item = item
                self._start_pos = scene_pos
                if self.current_tool == ToolType.ROTATE:
                    self._start_rotation = item.rotation()
                else:
                    self._start_scale = item.scale()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            super().mouseMoveEvent(event)
            return

        scene_pos = self.mapToScene(event.pos())
        self.cursorMoved.emit(scene_pos)

        # Delegate to active plugin tool first
        if self._active_plugin_tool and hasattr(self._active_plugin_tool, '_on_view_mouse_move'):
            if self._active_plugin_tool._on_view_mouse_move(event):
                return

        if self.current_tool == ToolType.SELECTION:
            if self._selection_creating and self._selection_host:
                self._selection_host.updateSelectionOverlay(scene_pos)
                return
            if self._selection_drop_active:
                self._selection_drop_pos = scene_pos
                return
            super().mouseMoveEvent(event)
            return

        if self._drawing_item:
            rect = QRectF(self._start_pos, scene_pos).normalized()
            self._drawing_item.setRect(rect)
            return
        if self._interacting_item:
            if self.current_tool == ToolType.ROTATE:
                center = self._interacting_item.sceneBoundingRect().center()
                start_vec = self._start_pos - center
                curr_vec = scene_pos - center
                angle_start = math.atan2(start_vec.y(), start_vec.x())
                angle_curr = math.atan2(curr_vec.y(), curr_vec.x())
                delta_angle = math.degrees(angle_curr - angle_start)
                self._interacting_item.setRotation(self._start_rotation + delta_angle)
            else:
                center = self._interacting_item.sceneBoundingRect().center()
                start_dist = (self._start_pos - center).manhattanLength()
                curr_dist = (scene_pos - center).manhattanLength()
                if start_dist > 0:
                    scale_factor = curr_dist / start_dist
                    self._interacting_item.setScale(self._start_scale * scale_factor)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag if self.current_tool != ToolType.SELECT
                else QGraphicsView.DragMode.RubberBandDrag
            )
            super().mouseReleaseEvent(event)
            return

        # Delegate to active plugin tool first
        if self._active_plugin_tool and hasattr(self._active_plugin_tool, '_on_view_mouse_release'):
            if self._active_plugin_tool._on_view_mouse_release(event):
                return

        scene_pos = self.mapToScene(event.pos())

        if self.current_tool == ToolType.SELECTION:
            if self._selection_creating:
                self._selection_creating = False
                if self._selection_host and self._selection_host.hasSelectionOverlay():
                    self._selection_host.lockSelectionOverlay()
                    self._selection_host.activateSelectionOverlay()
                self._apply_cursor()
                return
            if self._selection_drop_active:
                target_pos = self._selection_drop_pos or scene_pos
                self._selection_drop_active = False
                self._selection_drop_pos = None
                self._finalize_selection(target_pos)
                self._apply_cursor()
                return
            super().mouseReleaseEvent(event)
            return

        if self._drawing_item:
            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            rect = self._drawing_item.rect()
            self._drawing_item.setTransformOriginPoint(rect.center())
            self.itemAdded.emit(self._drawing_item)
            self._drawing_item = None
            self._start_pos = None
            return
        if self._interacting_item:
            self._interacting_item = None
            self._start_pos = None
            return

        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist') or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist') or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.source() == self.artifact_list:
            for item in self.artifact_list.selectedItems():
                pos = self.mapToScene(event.position().toPoint())
                user_data = item.data(Qt.ItemDataRole.UserRole)
                new_item = None
                if isinstance(user_data, RasterItem):
                    pixmap = QPixmap()
                    pixmap.loadFromData(user_data.image_bytes)
                    new_item = RasterItem(pixmap)
                    new_item.image_bytes = user_data.image_bytes
                elif isinstance(user_data, VectorItem):
                    renderer = user_data.renderer
                    new_item = VectorItem(renderer)
                if new_item:
                    new_item.setPos(pos)
                    self.itemAdded.emit(new_item)
            event.acceptProposedAction()
        elif event.mimeData().hasUrls():
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._try_paste_from_urls(event.mimeData(), scene_pos):
                event.acceptProposedAction()
                return
            super().dropEvent(event)
        else:
            super().dropEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if not self._show_context_menu(event.globalPos(), scene_pos):
            super().contextMenuEvent(event)

    def _show_context_menu(self, global_pos, scene_pos, clicked_items=None):
        from functools import partial
        menu = QMenu(self)
        actions_present = False
        overlay = self._current_overlay()
        overlay_active = (
            self.current_tool == ToolType.SELECTION and
            overlay and
            not self._selection_creating
        )
        if overlay_active:
            grab_action = QAction("Grab Selection", self)
            grab_action.triggered.connect(lambda: self._finalize_selection(None))
            menu.addAction(grab_action)
            copy_action = QAction("Copy Selection", self)
            copy_action.triggered.connect(self._copy_selection)
            menu.addAction(copy_action)
            cancel_action = QAction("Cancel Selection", self)
            cancel_action.triggered.connect(self._cancel_selection_mode)
            menu.addAction(cancel_action)
            actions_present = True

        if isinstance(scene_pos, QPoint):
            scene_point = QPointF(scene_pos)
        else:
            scene_point = scene_pos
        layer_items = set(self.main_window.layer_list.graphics_items())
        selected_layer_items = [item for item in self.scene().selectedItems() if item in layer_items]
        if clicked_items:
            target_layer_items = [item for item in clicked_items if item in layer_items]
            if target_layer_items and not all(item in selected_layer_items for item in target_layer_items):
                self.scene().clearSelection()
                for target in target_layer_items:
                    target.setSelected(True)
                selected_layer_items = target_layer_items.copy()

        if selected_layer_items:
            if actions_present:
                menu.addSeparator()
            copy_label = "Copy Item" if len(selected_layer_items) == 1 else "Copy Items"
            copy_items_action = QAction(copy_label, self)
            copy_items_action.triggered.connect(self._copy_selection_or_items)
            menu.addAction(copy_items_action)
            delete_action = QAction("Delete Selection", self)
            delete_action.triggered.connect(self.main_window.delete_selected_items)
            menu.addAction(delete_action)
            if len(selected_layer_items) == 1 and isinstance(selected_layer_items[0], VectorItem):
                vector_item = selected_layer_items[0]
                edit_action = QAction("Edit Vector in Inkscape", self)
                edit_action.triggered.connect(vector_item.edit_with_inkscape)
                menu.addAction(edit_action)
            actions_present = True

        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        can_paste = (
            mime_data.hasText() or
            mime_data.hasImage() or
            mime_data.hasFormat('image/svg+xml') or
            mime_data.hasUrls()
        )
        if can_paste:
            if actions_present:
                menu.addSeparator()
            paste_action = QAction("Paste", self)
            viewport_pos = self.mapFromScene(scene_point)
            paste_action.triggered.connect(partial(self.paste_at_position, viewport_pos))
            menu.addAction(paste_action)

        if menu.isEmpty():
            return False
        if isinstance(global_pos, QPointF):
            global_point = global_pos.toPoint()
        else:
            global_point = global_pos
        menu.exec(global_point)
        return True

    def paste_at_position(self, pos):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        scene_pos = self.mapToScene(pos)
        if self._try_paste_from_urls(mime_data, scene_pos):
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if mime_data.hasFormat('image/svg+xml'):
            svg_data = mime_data.data('image/svg+xml')
            log_path = f"pasted_logs/svg_{timestamp}.svg"
            with open(log_path, 'wb') as f:
                f.write(svg_data)
            print(f"Logged SVG to {log_path}")
            renderer = QSvgRenderer(svg_data)
            item = VectorItem(renderer)
            item.setPos(scene_pos)
            self.itemAdded.emit(item)
            self.main_window.add_artifact(log_path)
            return
        if mime_data.hasImage():
            image = mime_data.imageData()
            pixmap = QPixmap.fromImage(image)
            log_path = f"pasted_logs/image_{timestamp}.png"
            pixmap.save(log_path)
            print(f"Logged image to {log_path}")
            item = RasterItem(pixmap)
            item.setPos(scene_pos)
            self.itemAdded.emit(item)
            self.main_window.add_artifact(log_path)
            return
        if mime_data.hasText():
            text = mime_data.text()
            if self._try_paste_path_from_text(text, scene_pos):
                return
            log_path = f"pasted_logs/text_{timestamp}.txt"
            with open(log_path, 'w') as f:
                f.write(text)
            print(f"Logged text to {log_path}")
            text_item = CanvasTextItem(text)
            text_item.setPos(scene_pos)
            text_item.setFont(QFont("Arial", 12))
            text_item._update_transform_origin()
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            self.scene().addItem(text_item)
            self.itemAdded.emit(text_item)
            text_item.enter_edit_mode(select_all=True)
            list_item = QListWidgetItem()
            list_item.setText(f"Text: {text[:20]}...")
            list_item.setData(Qt.ItemDataRole.UserRole, text_item)
            self.artifact_list.addItem(list_item)
            return

    def _try_paste_from_urls(self, mime_data, scene_pos):
        if not mime_data.hasUrls():
            return False
        offset_step = QPointF(25, 25)
        handled = False
        for index, url in enumerate(mime_data.urls()):
            path = url.toLocalFile()
            if not path:
                continue
            pos = scene_pos + QPointF(offset_step.x() * index, offset_step.y() * index)
            if self._paste_file_path(path, pos):
                handled = True
        return handled

    def _try_paste_path_from_text(self, text, scene_pos):
        if not text:
            return False
        candidate = text.strip().splitlines()[0].strip().strip('"')
        if not candidate:
            return False
        if candidate.startswith('file://'):
            candidate = QUrl(candidate).toLocalFile()
        return self._paste_file_path(candidate, scene_pos)

    def _paste_file_path(self, path, scene_pos):
        if not path:
            return False
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return False
        lower = path.lower()
        item = None
        if lower.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
            pixmap = QPixmap(path)
            if pixmap.isNull():
                return False
            # Check if we should scale large images
            scale_large = self.main_window.settings.value("canvas/scale_large_images", False, type=bool)
            if scale_large:
                viewport_size = self.viewport().size()
                max_width = viewport_size.width() * 0.9
                max_height = viewport_size.height() * 0.9
                if pixmap.width() > max_width or pixmap.height() > max_height:
                    pixmap = pixmap.scaled(
                        int(max_width), int(max_height),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
            item = RasterItem(pixmap)
        elif lower.endswith('.svg'):
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                return False
            item = VectorItem(renderer)
        if not item:
            return False
        item.setPos(scene_pos)
        self.itemAdded.emit(item)
        self.main_window.add_artifact(path)
        return True

    def mouseDoubleClickEvent(self, event):
        if (self.current_tool == ToolType.SELECTION and
                event.button() == Qt.MouseButton.LeftButton and
                self._selection_host and
                self._selection_host.hasSelectionOverlay() and
                not self._selection_creating):
            self._finalize_selection(None)
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self._is_text_editing_active():
            super().keyPressEvent(event)
            return
        
        # Delegate to active plugin tool first
        if self._active_plugin_tool and hasattr(self._active_plugin_tool, '_on_key_press'):
            if self._active_plugin_tool._on_key_press(event):
                return
        
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.main_window.delete_selected_items()
            return
        if event.key() == Qt.Key.Key_C:
            if self._copy_selection_or_items():
                return
        if self.current_tool == ToolType.SELECTION and event.key() in (Qt.Key.Key_G, Qt.Key.Key_Return):
            self._finalize_selection(None)
            return
        super().keyPressEvent(event)

    def _handle_selection_press(self, event, scene_pos, clicked_item):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        overlay = self._current_overlay()
        if self._is_overlay_related_item(clicked_item, overlay):
            super().mousePressEvent(event)
            return
        if isinstance(clicked_item, RasterItem):
            if self._selection_host and self._selection_host is not clicked_item:
                self._selection_host.clearSelectionOverlay()
            elif overlay:
                self._selection_host.clearSelectionOverlay()
            self._selection_host = clicked_item
            self.scene().clearSelection()
            self._selection_host.startSelectionOverlay(scene_pos)
            self._selection_creating = True
            event.accept()
            self._apply_cursor()
            return
        if overlay:
            self._selection_drop_active = True
            self._selection_drop_pos = scene_pos
            event.accept()
            self._apply_cursor()
            return
        self._selection_host = None
        event.ignore()
        self._apply_cursor()

    def _is_overlay_related_item(self, item, overlay):
        if not overlay or not item:
            return False
        if item is overlay:
            return True
        if isinstance(item, (ResizeHandle, RotateHandle)):
            return getattr(item, 'parent_item', None) is overlay
        return False

    def _current_overlay(self):
        return self._selection_host.selectionOverlay() if self._selection_host else None

    def _finalize_selection(self, drop_center_scene_pos, remove_original=True):
        if not self._selection_host or not self._selection_host.hasSelectionOverlay():
            return
        overlay = self._current_overlay()
        center_pos = drop_center_scene_pos or (overlay.scene_rect().center() if overlay else None)
        new_item = self._selection_host.endSelection(center_pos, self.main_window.fill_mode, remove_original)
        if new_item:
            self.itemAdded.emit(new_item)
            self.set_tool(ToolType.MOVE)
        self._selection_host = None
        self._selection_creating = False
        self._selection_drop_active = False
        self._selection_drop_pos = None
        self._apply_cursor()

    def _copy_selection(self):
        if not self._selection_host or not self._selection_host.hasSelectionOverlay():
            return
        self._finalize_selection(None, remove_original=False)

    def _copy_selection_or_items(self):
        overlay_active = (
            self.current_tool == ToolType.SELECTION and
            self._selection_host and
            self._selection_host.hasSelectionOverlay() and
            not self._selection_creating
        )
        if overlay_active:
            self._copy_selection()
            return True
        layer_items = set(self.main_window.layer_list.graphics_items())
        selected_items = [
            item for item in self.scene().selectedItems()
            if item in layer_items
        ]
        if not selected_items:
            return False
        clones = []
        for item in selected_items:
            clone = self._clone_item(item)
            if clone:
                clones.append(clone)
        if not clones:
            return False
        for clone in clones:
            self.itemAdded.emit(clone)
        self.scene().clearSelection()
        for clone in clones:
            clone.setSelected(True)
        return True

    def _clone_item(self, item):
        if isinstance(item, SelectionOverlay):
            return None
        if isinstance(item, RasterItem):
            clone = RasterItem(item.pixmap().copy())
        elif isinstance(item, VectorItem):
            clone = VectorItem(item.renderer)
        elif isinstance(item, QGraphicsRectItem) and not isinstance(item, SelectionOverlay):
            clone = CanvasRectItem(item.rect())
            clone.setPen(item.pen())
            clone.setBrush(item.brush())
        elif isinstance(item, QGraphicsEllipseItem):
            clone = CanvasEllipseItem(item.rect())
            clone.setPen(item.pen())
            clone.setBrush(item.brush())
        elif isinstance(item, QGraphicsTextItem):
            clone = CanvasTextItem(item.toPlainText())
            clone.setFont(item.font())
            clone.setDefaultTextColor(item.defaultTextColor())
            clone._update_transform_origin()
        else:
            return None
        clone.setFlags(item.flags())
        clone.setTransformOriginPoint(item.transformOriginPoint())
        clone.setPos(item.scenePos() + QPointF(15, 15))
        clone.setRotation(item.rotation())
        clone.setScale(item.scale())
        return clone

    def _cancel_selection_mode(self):
        if self._selection_host:
            self._selection_host.clearSelectionOverlay()
        self._selection_host = None
        self._selection_creating = False
        self._selection_drop_active = False
        self._selection_drop_pos = None
        self._apply_cursor()

    def _apply_cursor(self):
        if self.current_tool == ToolType.SELECTION:
            if self._selection_creating or self._selection_drop_active or not self._selection_host:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self.current_tool == ToolType.SELECT:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _is_text_editing_active(self):
        focus_item = self.scene().focusItem()
        return isinstance(focus_item, CanvasTextItem) and focus_item.is_editing()

    def active_selection_host(self):
        return self._selection_host

    def handle_items_deleted(self, deleted_items):
        if not deleted_items:
            return
        if self._selection_host and self._selection_host in deleted_items:
            self._cancel_selection_mode()
        if self._interacting_item and self._interacting_item in deleted_items:
            self._interacting_item = None
        if self._drawing_item and self._drawing_item in deleted_items:
            self._drawing_item = None


def apply_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    
    # Fix menu bar spacing
    app.setStyleSheet("""
        QMenuBar {
            background-color: #353535;
            color: white;
            padding: 2px;
            font-size: 13px;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 6px 10px;
            margin: 0px 2px;
            border-radius: 4px;
        }
        QMenuBar::item:selected {
            background-color: #2a82da;
        }
    """)


class PreferencesDialog(QDialog):
    """Preferences dialog with organized settings sections."""
    
    def __init__(self, parent=None, settings=None, current_save_dir=None, current_library_dir=None, plugin_manager=None):
        super().__init__(parent)
        self.settings = settings
        self.plugin_manager = plugin_manager
        self.main_window = parent
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(550)
        self.setMinimumHeight(450)
        
        # Store current values
        self._save_dir = str(current_save_dir) if current_save_dir else ""
        self._library_dir = str(current_library_dir) if current_library_dir else ""
        
        # Track if values changed
        self._save_dir_changed = False
        self._library_dir_changed = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create tab widget for organized sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Add tabs
        self.tab_widget.addTab(self._create_folders_tab(), "Folders")
        self.tab_widget.addTab(self._create_canvas_tab(), "Canvas")
        self.tab_widget.addTab(self._create_appearance_tab(), "Appearance")
        self.tab_widget.addTab(self._create_toolbar_tab(), "Toolbar")
        self.tab_widget.addTab(self._create_window_tab(), "Window")
        self.tab_widget.addTab(self._create_plugins_tab(), "Plugins")
        self.tab_widget.addTab(self._create_about_tab(), "About")
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_folders_tab(self):
        """Create the Folders settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # Export Settings Group
        export_group = QGroupBox("Export Settings")
        export_layout = QFormLayout(export_group)
        export_layout.setSpacing(10)
        
        # Save folder
        save_folder_widget = QWidget()
        save_folder_layout = QHBoxLayout(save_folder_widget)
        save_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.save_folder_edit = QLineEdit(self._save_dir)
        self.save_folder_edit.setReadOnly(True)
        self.save_folder_edit.setPlaceholderText("Default: ~/Pictures/CanvasForge")
        save_folder_layout.addWidget(self.save_folder_edit)
        save_folder_btn = QPushButton("Browse...")
        save_folder_btn.clicked.connect(self._browse_save_folder)
        save_folder_layout.addWidget(save_folder_btn)
        export_layout.addRow("Save canvas to:", save_folder_widget)
        
        # Add description
        save_desc = QLabel("Where File > Save exports your canvas images (PNG format)")
        save_desc.setStyleSheet("color: #888; font-size: 11px;")
        export_layout.addRow("", save_desc)
        
        layout.addWidget(export_group)
        
        # Image Library Group
        library_group = QGroupBox("Image Library")
        library_layout = QFormLayout(library_group)
        library_layout.setSpacing(10)
        
        # Library folder
        library_folder_widget = QWidget()
        library_folder_layout = QHBoxLayout(library_folder_widget)
        library_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.library_folder_edit = QLineEdit(self._library_dir)
        self.library_folder_edit.setReadOnly(True)
        self.library_folder_edit.setPlaceholderText("Default: ~/Pictures/Screenshots")
        library_folder_layout.addWidget(self.library_folder_edit)
        library_folder_btn = QPushButton("Browse...")
        library_folder_btn.clicked.connect(self._browse_library_folder)
        library_folder_layout.addWidget(library_folder_btn)
        library_layout.addRow("Screenshot folder:", library_folder_widget)
        
        # Add description
        library_desc = QLabel("Source folder for the screenshot browser in the left sidebar")
        library_desc.setStyleSheet("color: #888; font-size: 11px;")
        library_layout.addRow("", library_desc)
        
        layout.addWidget(library_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return widget
    
    def _create_canvas_tab(self):
        """Create the Canvas settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # Image Import Group
        import_group = QGroupBox("Image Import Behavior")
        import_layout = QFormLayout(import_group)
        import_layout.setSpacing(10)
        
        # After adding image dropdown
        self.import_behavior_combo = QComboBox()
        self.import_behavior_combo.addItem("Keep current view", "keep")
        self.import_behavior_combo.addItem("Pan to show new image", "pan_to_new")
        self.import_behavior_combo.addItem("Zoom to fit all items", "fit_all")
        self.import_behavior_combo.addItem("Zoom to fit new item only", "fit_new")
        
        # Load saved preference
        saved_behavior = self.settings.value("canvas/import_behavior", "keep") if self.settings else "keep"
        idx = self.import_behavior_combo.findData(saved_behavior)
        if idx >= 0:
            self.import_behavior_combo.setCurrentIndex(idx)
        
        import_layout.addRow("After adding image:", self.import_behavior_combo)
        
        # Description
        import_desc = QLabel(
            "• Keep current view: Image added at viewport center, no zoom change\n"
            "• Pan to show new image: Scroll to center on the new image\n"
            "• Zoom to fit all items: Zoom out to show entire canvas\n"
            "• Zoom to fit new item only: Zoom to show just the new image"
        )
        import_desc.setStyleSheet("color: #888; font-size: 11px;")
        import_desc.setWordWrap(True)
        import_layout.addRow("", import_desc)
        
        layout.addWidget(import_group)
        
        # Image Sizing Group
        sizing_group = QGroupBox("Image Sizing")
        sizing_layout = QFormLayout(sizing_group)
        sizing_layout.setSpacing(10)
        
        self.scale_large_checkbox = QCheckBox("Scale down images larger than viewport")
        saved_scale = self.settings.value("canvas/scale_large_images", False, type=bool) if self.settings else False
        self.scale_large_checkbox.setChecked(saved_scale)
        sizing_layout.addRow(self.scale_large_checkbox)
        
        scale_desc = QLabel("When enabled, imported images larger than the current viewport will be scaled down to fit.")
        scale_desc.setStyleSheet("color: #888; font-size: 11px;")
        scale_desc.setWordWrap(True)
        sizing_layout.addRow("", scale_desc)
        
        layout.addWidget(sizing_group)
        layout.addStretch()
        
        return widget
    
    def _create_appearance_tab(self):
        """Create Appearance settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # Icon Theme
        theme_group = QGroupBox("Icon Theme")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Default", "default")
        
        # Scan for other themes in assets/toolbar_icons
        base_dir = Path(__file__).parent / "assets" / "toolbar_icons"
        if base_dir.exists():
            for item in base_dir.iterdir():
                if item.is_dir():
                    self.theme_combo.addItem(item.name.capitalize(), item.name)
        
        current_theme = self.settings.value("appearance/icon_theme", "default")
        idx = self.theme_combo.findData(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
            
        theme_row = QHBoxLayout()
        theme_row.addWidget(self.theme_combo)
        
        new_theme_btn = QPushButton("New Theme...")
        new_theme_btn.setToolTip("Create a new icon theme based on the current one")
        new_theme_btn.clicked.connect(self._create_new_theme)
        theme_row.addWidget(new_theme_btn)
        
        theme_layout.addRow("Theme:", theme_row)
        layout.addWidget(theme_group)
        
        # Info
        info = QLabel(
            "Icon themes are stored in 'assets/toolbar_icons/'. "
            "You can customize toolbar icons by selecting a custom theme and using the Toolbar tab."
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        return widget

    def _create_new_theme(self):
        """Create a new icon theme directory."""
        name, ok = QInputDialog.getText(self, "New Theme", "Enter new theme name:")
        if not ok or not name:
            return
            
        # Sanitize name
        safe_name = "".join(x for x in name if x.isalnum() or x in ('_','-')).strip()
        if not safe_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid directory name.")
            return
            
        base_dir = Path(__file__).parent / "assets" / "toolbar_icons"
        new_theme_dir = base_dir / safe_name
        
        if new_theme_dir.exists():
            QMessageBox.warning(self, "Exists", f"Theme '{safe_name}' already exists.")
            return
            
        try:
            new_theme_dir.mkdir(parents=True)
            
            # Copy default icons if current is default, or copy current theme items
            current_theme = self.theme_combo.currentData()
            src_dir = base_dir
            if current_theme != "default":
                src_dir = base_dir / current_theme
                
            # Copy files (simple shallow copy of images)
            # We copy all .png and .svg files
            count = 0
            for item in src_dir.iterdir():
                if item.is_file() and item.suffix.lower() in ('.png', '.svg'):
                    shutil.copy2(item, new_theme_dir / item.name)
                    count += 1
            
            QMessageBox.information(self, "Theme Created", f"Created theme '{safe_name}' with {count} icons.")
            
            # Add to combo and select
            self.theme_combo.addItem(safe_name.capitalize(), safe_name)
            idx = self.theme_combo.findData(safe_name)
            self.theme_combo.setCurrentIndex(idx)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create theme: {e}")

    def get_icon_theme(self):
        return self.theme_combo.currentData()

    
    def _create_toolbar_tab(self):
        """Create the Toolbar customization tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Toolbar Order Group
        order_group = QGroupBox("Toolbar Icons & Order")
        order_layout = QVBoxLayout(order_group)
        
        # Instructions
        instructions = QLabel(
            "Reorder items using Move Up/Down. Change icons by selecting an item and clicking 'Change Icon'."
        )
        instructions.setStyleSheet("color: #888; font-size: 11px;")
        instructions.setWordWrap(True)
        order_layout.addWidget(instructions)
        
        # Table Widget
        self.toolbar_table = QTableWidget()
        self.toolbar_table.setColumnCount(3)
        self.toolbar_table.setHorizontalHeaderLabels(["Icon", "Tool", "Source Path"])
        self.toolbar_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.toolbar_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.toolbar_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.toolbar_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.toolbar_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.toolbar_table.setMinimumHeight(300)
        self.toolbar_table.setIconSize(QSize(32, 32))
        order_layout.addWidget(self.toolbar_table)
        
        # Buttons
        button_row = QHBoxLayout()
        
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self._move_toolbar_item_up)
        button_row.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self._move_toolbar_item_down)
        button_row.addWidget(move_down_btn)
        
        change_icon_btn = QPushButton("Change Icon...")
        change_icon_btn.clicked.connect(self._change_toolbar_icon)
        button_row.addWidget(change_icon_btn)
        
        button_row.addStretch()
        
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_toolbar_order)
        button_row.addWidget(reset_btn)
        
        order_layout.addLayout(button_row)
        layout.addWidget(order_group)
        
        # Populate
        self._populate_toolbar_order_list()
        
        layout.addStretch()
        return widget

    def _resolve_icon_path(self, icon_name):
        """Helper to find the actual path of an icon based on current theme."""
        theme = self.theme_combo.currentData()
        base_dir = Path(__file__).parent / "assets" / "toolbar_icons"
        
        # Theme search
        if theme != "default":
            theme_dir = base_dir / theme
            if theme_dir.exists():
                svg = theme_dir / f"{icon_name}.svg"
                if svg.exists(): return str(svg)
                png = theme_dir / f"{icon_name}.png"
                if png.exists(): return str(png)
        
        # Default fallback
        svg = base_dir / f"{icon_name}.svg"
        if svg.exists(): return str(svg)
        png = base_dir / f"{icon_name}.png"
        if png.exists(): return str(png)
        
        return "Built-in / Missing"

    def _populate_toolbar_order_list(self):
        """Populate the toolbar table."""
        self.toolbar_table.setRowCount(0)
        
        if not self.main_window or not hasattr(self.main_window, '_toolbar_action_defs'):
            return
        
        order = self.main_window._get_toolbar_order()
        action_defs = self.main_window._toolbar_action_defs
        
        for action_id in order:
            if action_id not in action_defs:
                continue
            
            action_def = action_defs[action_id]
            row = self.toolbar_table.rowCount()
            self.toolbar_table.insertRow(row)
            
            if action_def.get("is_separator"):
                # Separator
                item_name = QTableWidgetItem("── Separator ──")
                item_name.setForeground(QColor("#888"))
                item_name.setData(Qt.ItemDataRole.UserRole, action_id)
                self.toolbar_table.setItem(row, 1, item_name)
            else:
                # Tool
                text = action_def.get("text", action_id)
                is_core = action_def.get("is_core", False)
                prefix = "⚙️ " if is_core else "🔌 "
                
                # Icon Item
                icon_item = QTableWidgetItem()
                action = action_def.get("action")
                if action and not action.icon().isNull():
                    icon_item.setIcon(action.icon())
                self.toolbar_table.setItem(row, 0, icon_item)
                
                # Name Item
                name_item = QTableWidgetItem(f"{prefix}{text}")
                name_item.setData(Qt.ItemDataRole.UserRole, action_id)
                self.toolbar_table.setItem(row, 1, name_item)
                
                # Path Item
                icon_name = action_def.get("icon_name", "")
                if icon_name:
                    path = self._resolve_icon_path(icon_name)
                    path_item = QTableWidgetItem(path)
                    path_item.setToolTip(path)
                    self.toolbar_table.setItem(row, 2, path_item)
                else:
                    self.toolbar_table.setItem(row, 2, QTableWidgetItem("-"))

    def _change_toolbar_icon(self):
        """Change icon for selected toolbar item."""
        row = self.toolbar_table.currentRow()
        if row < 0:
            return
            
        # Get action ID
        item_name = self.toolbar_table.item(row, 1)
        action_id = item_name.data(Qt.ItemDataRole.UserRole)
        
        if not action_id or action_id.startswith("---"):
            return
            
        # Check theme
        current_theme = self.theme_combo.currentData()
        if current_theme == "default":
            reply = QMessageBox.question(
                self, "Default Theme",
                "You are using the default theme. You must create a custom theme to edit icons.\n\n"
                "Create new theme now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._create_new_theme()
                # If they cancelled theme creation or it failed, we're still on default
                if self.theme_combo.currentData() == "default":
                    return
                # Refresh table to update paths (now pointing to new theme)
                self._populate_toolbar_order_list()
            else:
                return

        # Double check theme (it should be custom now)
        current_theme = self.theme_combo.currentData()
        
        # Select file
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon", str(Path.home()), "Images (*.svg *.png)"
        )
        
        if path:
            # Copy to theme folder
            action_defs = self.main_window._toolbar_action_defs
            if action_id in action_defs:
                icon_name = action_defs[action_id].get("icon_name")
                if not icon_name:
                    # Fallback if no icon name defined
                    icon_name = f"toolbar_icon_{action_id}"
                
                theme_dir = Path(__file__).parent / "assets" / "toolbar_icons" / current_theme
                theme_dir.mkdir(parents=True, exist_ok=True)
                
                src_path = Path(path)
                # Enforce lowercase extension for destination
                scaling_ext = src_path.suffix.lower()
                dest_path = theme_dir / f"{icon_name}{scaling_ext}"
                
                try:
                    shutil.copy2(src_path, dest_path)
                    
                    # If we switched extensions (e.g. png to svg), remove the old one to avoid conflict priorities
                    other_ext = ".png" if scaling_ext == ".svg" else ".svg"
                    other_path = theme_dir / f"{icon_name}{other_ext}"
                    if other_path.exists():
                        other_path.unlink()
                        
                    # Update UI
                    self.main_window._setup_toolbar_actions() # Reloads icons in main window
                    self._populate_toolbar_order_list() # Reloads table
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save icon: {e}")

    def _move_toolbar_item_up(self):
        """Move selected toolbar item up."""
        row = self.toolbar_table.currentRow()
        if row <= 0: return
        
        self._swap_rows(row, row - 1)
        self.toolbar_table.selectRow(row - 1)

    def _move_toolbar_item_down(self):
        """Move selected toolbar item down."""
        row = self.toolbar_table.currentRow()
        count = self.toolbar_table.rowCount()
        if row < 0 or row >= count - 1: return
        
        self._swap_rows(row, row + 1)
        self.toolbar_table.selectRow(row + 1)
        
    def _swap_rows(self, row1, row2):
        """Helper to swap two rows in the table."""
        # Simple data swap for QTableWidget is annoying, easier to reconstruct
        # But we need to save the order to settings anyway
        # Let's just manipulate the underlying order list and repopulate
        # This is inefficient but safe
        
        # Get current order from table
        current_order = []
        for i in range(self.toolbar_table.rowCount()):
            item = self.toolbar_table.item(i, 1)
            current_order.append(item.data(Qt.ItemDataRole.UserRole))
            
        # Swap
        current_order[row1], current_order[row2] = current_order[row2], current_order[row1]
        
        # Save temp order to settings so _populate reads it? 
        # Or just update self.settings directly
        self.settings.setValue("toolbar/order", current_order)
        self.main_window._reorder_toolbar(current_order)
        self._populate_toolbar_order_list()

    def _reset_toolbar_order(self):
        """Reset toolbar order to default."""
        if self.main_window and hasattr(self.main_window, '_toolbar_action_defs'):
            self.settings.setValue("toolbar/order", None)
            self.main_window._reorder_toolbar(None)
            self.main_window._setup_toolbar_actions()
            self._populate_toolbar_order_list()
    
    def get_toolbar_order(self):
        """Get the new toolbar order from the table."""
        order = []
        for i in range(self.toolbar_table.rowCount()):
            item = self.toolbar_table.item(i, 1)
            action_id = item.data(Qt.ItemDataRole.UserRole)
            if action_id:
                order.append(action_id)
        return order
    
    def _create_window_tab(self):
        """Create the Window settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # Window Startup Group
        window_group = QGroupBox("Startup Behavior")
        window_layout = QFormLayout(window_group)
        window_layout.setSpacing(10)
        
        # Startup Mode
        self.startup_mode_combo = QComboBox()
        self.startup_mode_combo.addItem("Restore Last Session", "last")
        self.startup_mode_combo.addItem("Open on Specific Monitor", "monitor")
        self.startup_mode_combo.addItem("Open on Screen with Mouse", "mouse")
        
        saved_mode = self.settings.value("window/startup_mode", "last")
        idx = self.startup_mode_combo.findData(saved_mode)
        if idx >= 0:
            self.startup_mode_combo.setCurrentIndex(idx)
        
        window_layout.addRow("On Startup:", self.startup_mode_combo)
        
        # Monitor Selection (Dynamic)
        self.monitor_combo = QComboBox()
        screens = QApplication.screens()
        for i, screen in enumerate(screens):
            name = screen.name()
            self.monitor_combo.addItem(f"Monitor {i+1}: {name}", i)
            
        saved_monitor = self.settings.value("window/startup_monitor", 0, type=int)
        if saved_monitor < self.monitor_combo.count():
            self.monitor_combo.setCurrentIndex(saved_monitor)
            
        # Only enable monitor selection if "monitor" mode is chosen
        self.monitor_combo.setEnabled(saved_mode == "monitor")
        self.startup_mode_combo.currentIndexChanged.connect(
            lambda i: self.monitor_combo.setEnabled(self.startup_mode_combo.currentData() == "monitor")
        )
        
        window_layout.addRow("Target Monitor:", self.monitor_combo)
        
        # Window State
        self.window_state_combo = QComboBox()
        self.window_state_combo.addItem("Normal", "normal")
        self.window_state_combo.addItem("Maximized", "maximized")
        self.window_state_combo.addItem("Full Screen", "fullscreen")
        
        saved_state = self.settings.value("window/startup_state_pref", "normal")
        idx = self.window_state_combo.findData(saved_state)
        if idx >= 0:
            self.window_state_combo.setCurrentIndex(idx)
            
        window_layout.addRow("Window State:", self.window_state_combo)
        
        layout.addWidget(window_group)
        
        # Info
        info_lbl = QLabel(
            "Note: 'Restoring Last Session' will try to place the window exactly where it was, "
            "including its size and maximized state."
        )
        info_lbl.setStyleSheet("color: #888; font-size: 11px;")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)
        
        layout.addStretch()
        return widget

    def get_window_settings(self):
        """Return a dict of window settings."""
        return {
            "mode": self.startup_mode_combo.currentData(),
            "monitor": self.monitor_combo.currentData(),
            "state": self.window_state_combo.currentData()
        }
    
    def get_import_behavior(self):
        """Return the selected import behavior setting."""
        return self.import_behavior_combo.currentData()
    
    def get_scale_large_images(self):
        """Return whether to scale large images."""
        return self.scale_large_checkbox.isChecked()
    
    def accept(self):
        """Save settings when dialog is accepted."""
        if self.settings:
            self.settings.setValue("canvas/import_behavior", self.get_import_behavior())
            self.settings.setValue("canvas/scale_large_images", self.get_scale_large_images())
            win_settings = self.get_window_settings()
            self.settings.setValue("window/startup_mode", win_settings["mode"])
            self.settings.setValue("window/startup_monitor", win_settings["monitor"])
            self.settings.setValue("window/startup_state_pref", win_settings["state"])
            self.settings.setValue("plugins/editor_path", self.get_editor_path())
            self.settings.setValue("appearance/icon_theme", self.get_icon_theme())
        super().accept()
    
    def _create_plugins_tab(self):
        """Create the Plugins settings tab."""
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QTextEdit
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Plugins Group
        plugins_group = QGroupBox("Installed Plugins")
        plugins_layout = QVBoxLayout(plugins_group)
        
        # Plugin list
        self.plugin_list = QListWidget()
        self.plugin_list.setMaximumHeight(150)
        self.plugin_list.itemSelectionChanged.connect(self._on_plugin_selected)
        plugins_layout.addWidget(self.plugin_list)
        
        # Plugin details
        self.plugin_details = QTextEdit()
        self.plugin_details.setReadOnly(True)
        self.plugin_details.setMaximumHeight(100)
        self.plugin_details.setPlaceholderText("Select a plugin to see details")
        plugins_layout.addWidget(self.plugin_details)
        
        # Button row
        button_row = QHBoxLayout()
        
        self.reload_plugin_btn = QPushButton("Reload Plugin")
        self.reload_plugin_btn.clicked.connect(self._reload_selected_plugin)
        self.reload_plugin_btn.setEnabled(False)
        button_row.addWidget(self.reload_plugin_btn)
        
        self.enable_plugin_btn = QPushButton("Enable/Disable")
        self.enable_plugin_btn.clicked.connect(self._toggle_plugin_enabled)
        self.enable_plugin_btn.setEnabled(False)
        button_row.addWidget(self.enable_plugin_btn)
        
        button_row.addStretch()
        
        open_folder_btn = QPushButton("Open Plugins Folder")
        open_folder_btn.clicked.connect(self._open_plugins_folder)
        button_row.addWidget(open_folder_btn)
        
        plugins_layout.addLayout(button_row)
        layout.addWidget(plugins_group)
        
        # Editor settings
        editor_group = QGroupBox("Plugin Development")
        editor_layout = QFormLayout(editor_group)
        
        editor_widget = QWidget()
        editor_row = QHBoxLayout(editor_widget)
        editor_row.setContentsMargins(0, 0, 0, 0)
        
        self.editor_path_edit = QLineEdit()
        saved_editor = self.settings.value("plugins/editor_path", "code") if self.settings else "code"
        self.editor_path_edit.setText(saved_editor)
        self.editor_path_edit.setPlaceholderText("code (VS Code)")
        editor_row.addWidget(self.editor_path_edit)
        
        editor_browse_btn = QPushButton("Browse...")
        editor_browse_btn.clicked.connect(self._browse_editor)
        editor_row.addWidget(editor_browse_btn)
        
        editor_layout.addRow("Editor command:", editor_widget)
        
        editor_desc = QLabel("Command used to open plugin files for editing (e.g., 'code', 'subl', 'gedit')")
        editor_desc.setStyleSheet("color: #888; font-size: 11px;")
        editor_layout.addRow("", editor_desc)
        
        layout.addWidget(editor_group)
        
        # Populate plugin list
        self._populate_plugin_list()
        
        layout.addStretch()
        return widget
    
    def _populate_plugin_list(self):
        """Populate the plugin list with discovered plugins."""
        self.plugin_list.clear()
        
        if not self.plugin_manager:
            return
        
        # Get all discovered plugins
        for manifest in self.plugin_manager.discover_plugins():
            item = QListWidgetItem()
            loaded = self.plugin_manager.get_plugin(manifest.id)
            
            status = "✓" if loaded and loaded.enabled and not loaded.error else "✗"
            item.setText(f"{status} {manifest.name} v{manifest.version}")
            item.setData(Qt.ItemDataRole.UserRole, manifest.id)
            
            self.plugin_list.addItem(item)
    
    def _on_plugin_selected(self):
        """Handle plugin selection in the list."""
        selected = self.plugin_list.selectedItems()
        if not selected:
            self.plugin_details.clear()
            self.reload_plugin_btn.setEnabled(False)
            self.enable_plugin_btn.setEnabled(False)
            return
        
        plugin_id = selected[0].data(Qt.ItemDataRole.UserRole)
        loaded = self.plugin_manager.get_plugin(plugin_id) if self.plugin_manager else None
        
        if loaded:
            manifest = loaded.manifest
            status = "Enabled" if loaded.enabled else "Disabled"
            if loaded.error:
                status = f"Error: {loaded.error}"
            
            details = (
                f"<b>{manifest.name}</b> v{manifest.version}<br>"
                f"<i>{manifest.description}</i><br><br>"
                f"Author: {manifest.author or 'Unknown'}<br>"
                f"Status: {status}<br>"
                f"Path: {loaded.path}"
            )
            self.plugin_details.setHtml(details)
            self.reload_plugin_btn.setEnabled(True)
            self.enable_plugin_btn.setEnabled(True)
            self.enable_plugin_btn.setText("Disable" if loaded.enabled else "Enable")
        else:
            # Plugin discovered but not loaded
            for manifest in self.plugin_manager.discover_plugins():
                if manifest.id == plugin_id:
                    details = (
                        f"<b>{manifest.name}</b> v{manifest.version}<br>"
                        f"<i>{manifest.description}</i><br><br>"
                        f"Author: {manifest.author or 'Unknown'}<br>"
                        f"Status: Not loaded"
                    )
                    self.plugin_details.setHtml(details)
                    self.reload_plugin_btn.setEnabled(True)
                    self.enable_plugin_btn.setEnabled(True)
                    self.enable_plugin_btn.setText("Enable")
                    break
    
    def _reload_selected_plugin(self):
        """Reload the selected plugin."""
        selected = self.plugin_list.selectedItems()
        if not selected or not self.plugin_manager:
            return
        
        plugin_id = selected[0].data(Qt.ItemDataRole.UserRole)
        if self.plugin_manager.reload_plugin(plugin_id):
            self._populate_plugin_list()
            # Re-select the item
            for i in range(self.plugin_list.count()):
                item = self.plugin_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == plugin_id:
                    item.setSelected(True)
                    break
    
    def _toggle_plugin_enabled(self):
        """Enable or disable the selected plugin."""
        selected = self.plugin_list.selectedItems()
        if not selected or not self.plugin_manager:
            return
        
        plugin_id = selected[0].data(Qt.ItemDataRole.UserRole)
        loaded = self.plugin_manager.get_plugin(plugin_id)
        
        if loaded:
            new_state = not loaded.enabled
        else:
            new_state = True  # Enable if not loaded
        
        self.plugin_manager.enable_plugin(plugin_id, new_state)
        self._populate_plugin_list()
        
        # Re-select the item
        for i in range(self.plugin_list.count()):
            item = self.plugin_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == plugin_id:
                item.setSelected(True)
                break
    
    def _open_plugins_folder(self):
        """Open the user plugins folder in file manager."""
        import subprocess
        if self.plugin_manager:
            folder = str(self.plugin_manager.user_plugin_dir)
            try:
                subprocess.Popen(['xdg-open', folder])
            except Exception:
                pass
    
    def _browse_editor(self):
        """Browse for editor executable."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Editor", "", "All Files (*)"
        )
        if path:
            self.editor_path_edit.setText(path)
    
    def get_editor_path(self):
        """Return the configured editor path."""
        return self.editor_path_edit.text() or "code"

    def _create_about_tab(self):
        """Create the About tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # App info
        title = QLabel(f"CanvasForge v{__version__}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        description = QLabel(
            "A canvas utility for remixing screenshots and UI snippets.\n\n"
            "Features:\n"
            "• Infinite canvas with pan and zoom\n"
            "• Drag and drop images from the library\n"
            "• Text annotations and shapes\n"
            "• Layer management\n"
            "• Export to PNG"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Credits
        credits = QLabel("Created by Luke Morrison")
        credits.setStyleSheet("color: #888;")
        layout.addWidget(credits)
        
        layout.addStretch()
        
        return widget
    
    def _browse_save_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Save Folder", self._save_dir or str(Path.home())
        )
        if folder:
            self._save_dir = folder
            self.save_folder_edit.setText(folder)
            self._save_dir_changed = True
    
    def _browse_library_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Screenshot Folder", self._library_dir or str(Path.home())
        )
        if folder:
            self._library_dir = folder
            self.library_folder_edit.setText(folder)
            self._library_dir_changed = True
    
    def get_save_folder(self):
        """Return the save folder path if changed, else None."""
        return Path(self._save_dir) if self._save_dir_changed else None
    
    def get_library_folder(self):
        """Return the library folder path if changed, else None."""
        return Path(self._library_dir) if self._library_dir_changed else None
    
    def get_import_behavior(self):
        """Return the selected import behavior setting."""
        return self.import_behavior_combo.currentData()
    
    def get_scale_large_images(self):
        """Return whether to scale large images."""
        return self.scale_large_checkbox.isChecked()
    
    def accept(self):
        """Save settings when dialog is accepted."""
        if self.settings:
            self.settings.setValue("canvas/import_behavior", self.get_import_behavior())
            self.settings.setValue("canvas/scale_large_images", self.get_scale_large_images())
            win_settings = self.get_window_settings()
            self.settings.setValue("window/startup_mode", win_settings["mode"])
            self.settings.setValue("window/startup_monitor", win_settings["monitor"])
            self.settings.setValue("window/startup_state_pref", win_settings["state"])
            self.settings.setValue("plugins/editor_path", self.get_editor_path())
            self.settings.setValue("appearance/icon_theme", self.get_icon_theme())
        super().accept()


class MainWindow(QMainWindow):

    def get_icon_resource(self, name):
        """
        Get an icon by name, respecting theme settings and prioritizing SVG.
        Falls back to placeholder if missing.
        """
        icon_aliases = {
            "toolbar_icon_pointer": "toolbar_icon_pointer_cartoon",
            "toolbar_icon_selection": "toolbar_icon_selection_cartoon",
            "toolbar_icon_move": "toolbar_icon_move_cartoon",
            "toolbar_icon_rotate": "toolbar_icon_rotate_cartoon",
            "toolbar_icon_scale": "toolbar_icon_scale_cartoon",
            "toolbar_icon_eraser": "toolbar_icon_eraser_cartoon",
            "toolbar_icon_snap_grid": "toolbar_icon_snap_grid_cartoon",
            "toolbar_icon_bring_forward": "toolbar_icon_bring_forward_cartoon",
            "toolbar_icon_send_backward": "toolbar_icon_send_backward_cartoon",
            "toolbar_icon_flatten_selected": "toolbar_icon_flatten_selected_cartoon",
            "toolbar_icon_flatten_all": "toolbar_icon_flatten_all_cartoon",
            "toolbar_icon_rectangle": "toolbar_icon_rectangle_cartoon",
            "toolbar_icon_ellipse": "toolbar_icon_ellipse_cartoon",
            "toolbar_icon_text": "toolbar_icon_text_cartoon",
            "toolbar_icon_crop": "toolbar_icon_crop_cartoon",
            "toolbar_icon_open": "toolbar_icon_open_cartoon",
            "toolbar_icon_paste": "toolbar_icon_paste_cartoon",
            "toolbar_icon_save_as": "toolbar_icon_save_as_cartoon",
            "toolbar_icon_undo": "toolbar_icon_undo_cartoon",
            "toolbar_icon_redo": "toolbar_icon_redo_cartoon",
        }
        resolved_name = icon_aliases.get(name, name)

        # Theme support
        theme = self.settings.value("appearance/icon_theme", "default")
        base_dir = Path(__file__).parent / "assets" / "toolbar_icons"
        
        # If using a theme, try that subfolder first
        if theme != "default":
            theme_dir = base_dir / theme
            if theme_dir.exists():
                # Try SVG (prioritized as per user request)
                svg_path = theme_dir / f"{resolved_name}.svg"
                if svg_path.exists():
                    return QIcon(str(svg_path))
                # Try PNG
                png_path = theme_dir / f"{resolved_name}.png"
                if png_path.exists():
                    return QIcon(str(png_path))
        
        # Fallback to default assets
        # Try SVG first
        svg_path = base_dir / f"{resolved_name}.svg"
        if svg_path.exists():
            return QIcon(str(svg_path))
        
        # Try PNG
        png_path = base_dir / f"{resolved_name}.png"
        if png_path.exists():
            return QIcon(str(png_path))
            
        # Placeholder generation
        return self._create_placeholder_icon(name)

    def _create_placeholder_icon(self, text):
        """Generate a placeholder icon with the filename/text."""
        size = 48
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("transparent"))
        painter = QPainter(pixmap)
        
        # Draw dashed border
        pen = QPen(QColor(255, 0, 0, 128))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(0, 0, size-1, size-1)
        
        # Draw text
        painter.setPen(QColor("red"))
        font = painter.font()
        font.setPixelSize(8)
        painter.setFont(font)
        
        # If user text is "toolbar_icon_crop", just show "crop"
        display_text = text.replace("toolbar_icon_", "")
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, display_text)
        
        painter.end()
        return QIcon(pixmap)

    def __init__(self):
        super().__init__()


        self.setWindowTitle("CanvasForge")
        app_icon_path = Path(__file__).parent / "assets" / "app_icons" / "canvasForge_app_icon.png"
        if app_icon_path.exists():
            self.setWindowIcon(QIcon(str(app_icon_path)))
        self.fill_mode = FillMode.TRANSPARENT
        self.settings = QSettings("CanvasForge", "CanvasForge")
        self._restore_window_geometry()
        default_pictures = Path.home() / "Pictures" / "CanvasForge"
        saved_dir = self.settings.value("default_save_dir", str(default_pictures))
        self.default_save_dir = Path(saved_dir)
        self._ensure_save_directory()
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("Cursor: x=0.0, y=0.0")
        
        # Initialize Undo Manager
        self.undo_manager = UndoManager()

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self._splitter)

        self.scene = QGraphicsScene()
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)

        self.artifact_list = ArtifactList()
        self.view = CanvasView(self.scene, self.artifact_list, self)
        self.view.cursorMoved.connect(self.update_cursor_status)
        self.view.itemAdded.connect(self.add_item_to_canvas)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Repository"))
        right_layout.addWidget(self.artifact_list)
        right_layout.addWidget(QLabel("Layers"))
        self.layer_list = LayerList(self.scene)
        self.layer_list.itemSelectionChanged.connect(self.on_layer_selection_changed)
        right_layout.addWidget(self.layer_list)

        self.library_panel = ImageLibraryPanel(settings=self.settings, parent=self)
        self.library_panel.assetActivated.connect(self._import_library_asset)
        self.library_panel.exportRequested.connect(self._export_canvas_to_library)
        self.library_panel.folderChanged.connect(self._on_library_folder_changed)

        self._splitter.addWidget(self.library_panel)
        self._splitter.addWidget(self.view)
        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setStretchFactor(2, 1)
        self._restore_splitter_sizes()
        
        # Initialize Plugin Manager (after layer_list is created)
        self.plugin_manager = PluginManager(self, self.undo_manager)

        # Create wrapping toolbar
        self.toolbar = WrappingToolBar(self)
        self.toolbar.setIconSize(QSizeF(48, 48).toSize())
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Create a dock widget for the toolbar so it can wrap
        toolbar_dock = QDockWidget("Tools", self)
        toolbar_dock.setWidget(self.toolbar)
        toolbar_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        toolbar_dock.setTitleBarWidget(QWidget())  # Hide title bar
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, toolbar_dock)
        
        # Store action definitions for toolbar customization
        self._toolbar_action_defs = {}
        self._setup_toolbar_actions()
        
        # Build toolbar from saved order or default
        self._build_toolbar()

        # Delete action needs to be stored for menu
        delete_action = self._toolbar_action_defs.get("delete", {}).get("action")

        file_menu = self.menuBar().addMenu("File")
        open_action = QAction(self.get_icon_resource("toolbar_icon_open"), "Open Images", self)
        open_action.triggered.connect(self.open_images)
        file_menu.addAction(open_action)

        paste_action = QAction(self.get_icon_resource("toolbar_icon_paste"), "Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.paste_image)
        file_menu.addAction(paste_action)

        save_action = QAction(self.get_icon_resource("toolbar_icon_save_as"), "Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_canvas)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("Edit")
        
        # Undo/Redo actions
        self.undo_action = QAction(self.get_icon_resource("toolbar_icon_undo"), "Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._do_undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = QAction(self.get_icon_resource("toolbar_icon_redo"), "Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self._do_redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)
        
        edit_menu.addSeparator()
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut(QKeySequence("Ctrl+,"))
        preferences_action.triggered.connect(self.open_preferences)
        edit_menu.addAction(preferences_action)
        
        # Connect undo manager signals
        self.undo_manager.undoAvailableChanged.connect(self.undo_action.setEnabled)
        self.undo_manager.redoAvailableChanged.connect(self.redo_action.setEnabled)
        self.undo_manager.undoDescriptionChanged.connect(
            lambda desc: self.undo_action.setText(f"Undo {desc}" if desc else "Undo")
        )
        self.undo_manager.redoDescriptionChanged.connect(
            lambda desc: self.redo_action.setText(f"Redo {desc}" if desc else "Redo")
        )
        
        # Load plugins after UI is set up
        self.plugin_manager.load_all_plugins()

    def _do_undo(self):
        """Perform undo action."""
        if self.undo_manager.undo():
            self._status_bar.showMessage(f"Undone: {self.undo_manager.redo_description()}", 2000)
    
    def _do_redo(self):
        """Perform redo action."""
        if self.undo_manager.redo():
            self._status_bar.showMessage(f"Redone: {self.undo_manager.undo_description()}", 2000)

    def set_active_plugin_tool(self, plugin_instance):
        """Set the active plugin tool on the canvas view."""
        self.view.set_active_plugin_tool(plugin_instance)

    def _setup_toolbar_actions(self):
        """Define all toolbar actions with their properties."""
        
        # Define core toolbar actions
        # Each entry: (id, icon_name, text, callback, shortcut, is_core)
        core_actions = [
            ("pointer", "toolbar_icon_pointer", "Pointer", lambda: self.view.set_tool(ToolType.SELECT), None, True),
            ("select", "toolbar_icon_selection", "Select", lambda: self.view.set_tool(ToolType.SELECTION), "S", True),
            ("move", "toolbar_icon_move", "Move", lambda: self.view.set_tool(ToolType.MOVE), None, True),
            ("rotate", "toolbar_icon_rotate", "Rotate", lambda: self.view.set_tool(ToolType.ROTATE), None, True),
            ("scale", "toolbar_icon_scale", "Scale", lambda: self.view.set_tool(ToolType.SCALE), None, True),
            ("delete", "toolbar_icon_eraser", "Delete", self.delete_selected_items, None, True),
            ("snap_grid", "toolbar_icon_snap_grid", "Snap Grid", lambda: self.view.set_tool(ToolType.ALIGN_GRID), None, True),
            ("bring_forward", "toolbar_icon_bring_forward", "Bring Forward", lambda: self.adjust_layer_z(-1), None, True),
            ("send_backward", "toolbar_icon_send_backward", "Send Backward", lambda: self.adjust_layer_z(1), None, True),
            ("---separator1---", None, None, None, None, True),  # Separator marker
            ("flatten_selected", "toolbar_icon_flatten_selected", "Flatten Selected", self.flatten_selected, None, True),
            ("flatten_all", "toolbar_icon_flatten_all", "Flatten All", self.flatten_all, None, True),
            ("---separator2---", None, None, None, None, True),  # Separator marker
            ("rectangle", "toolbar_icon_rectangle", "Rectangle", lambda: self.view.set_tool(ToolType.RECTANGLE), None, True),
            ("ellipse", "toolbar_icon_ellipse", "Ellipse", lambda: self.view.set_tool(ToolType.ELLIPSE), None, True),
            ("text", "toolbar_icon_text", "Text", lambda: self.view.set_tool(ToolType.TEXT), None, True),
        ]
        
        # Create actions and store them
        for action_id, icon_name, text, callback, shortcut, is_core in core_actions:
            if action_id.startswith("---"):
                # This is a separator marker
                self._toolbar_action_defs[action_id] = {
                    "id": action_id,
                    "is_separator": True,
                    "is_core": True,
                }
            else:
                action = QAction(self.get_icon_resource(icon_name), text, self)
                if shortcut:
                    action.setShortcut(shortcut)
                if callback:
                    action.triggered.connect(callback)
                
                self._toolbar_action_defs[action_id] = {
                    "id": action_id,
                    "action": action,
                    "icon_name": icon_name,
                    "text": text,
                    "is_separator": False,
                    "is_core": is_core,
                }
        
        # Set delete action shortcut
        if "delete" in self._toolbar_action_defs:
            self._toolbar_action_defs["delete"]["action"].setShortcut(
                QKeySequence(QKeySequence.StandardKey.Delete)
            )
    
    def _get_toolbar_order(self):
        """Get the toolbar order from settings or return default."""
        saved_order = self.settings.value("toolbar/order", None)
        if saved_order:
            return saved_order
        # Default order
        return list(self._toolbar_action_defs.keys())
    
    def _build_toolbar(self):
        """Build the toolbar based on the current order."""
        # Clear existing actions
        self.toolbar.clear()
        
        order = self._get_toolbar_order()
        
        # Add actions in order
        for action_id in order:
            if action_id not in self._toolbar_action_defs:
                continue
            
            action_def = self._toolbar_action_defs[action_id]
            if action_def.get("is_separator"):
                self.toolbar.addSeparator()
            else:
                action = action_def.get("action")
                if action:
                    self.toolbar.addAction(action)
        
        # Add any plugin actions that aren't in the saved order
        for action_id, action_def in self._toolbar_action_defs.items():
            if action_id not in order and not action_def.get("is_separator"):
                action = action_def.get("action")
                if action:
                    self.toolbar.addAction(action)
    
    def save_toolbar_order(self, order):
        """Save the toolbar order to settings and rebuild toolbar."""
        self.settings.setValue("toolbar/order", order)
        self._build_toolbar()
    
    def register_plugin_toolbar_action(self, action_id, action, icon_name=None):
        """Register a plugin action for the toolbar."""
        self._toolbar_action_defs[action_id] = {
            "id": action_id,
            "action": action,
            "icon_name": icon_name,
            "text": action.text(),
            "is_separator": False,
            "is_core": False,  # Plugin actions are not core
        }
        # Add to toolbar (will be at end unless order includes it)
        self._build_toolbar()

    def open_preferences(self):
        """Open the Preferences dialog."""
        current_library_dir = self.library_panel.current_root_path() if hasattr(self, 'library_panel') else None
        dialog = PreferencesDialog(
            self,
            settings=self.settings,
            current_save_dir=self.default_save_dir,
            current_library_dir=current_library_dir,
            plugin_manager=self.plugin_manager
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply save folder change
            new_save = dialog.get_save_folder()
            if new_save:
                self.default_save_dir = new_save
                self._ensure_save_directory()
                self.settings.setValue("default_save_dir", str(self.default_save_dir))
                self._status_bar.showMessage(f"Save folder set to {self.default_save_dir}", 5000)
            
            # Apply library folder change
            new_library = dialog.get_library_folder()
            if new_library and hasattr(self, 'library_panel'):
                self.library_panel.set_root_path(new_library, persist=True)
                self._status_bar.showMessage(f"Screenshot folder set to {new_library}", 5000)
            
            # Apply toolbar order change
            new_toolbar_order = dialog.get_toolbar_order()
            if new_toolbar_order:
                self.save_toolbar_order(new_toolbar_order)
                self._status_bar.showMessage("Toolbar order updated", 3000)

    def open_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Images", "", "Images (*.png *.jpg *.svg)")
        for file in files:
            self.add_artifact(file)

    def paste_image(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasText():
            print("Text clipboard - use right-click paste on canvas")
            return
        if mime_data.hasImage():
            image = mime_data.imageData()
            pixmap = QPixmap.fromImage(image)
            item = RasterItem(pixmap)
            self.add_to_repository(item, thumbnail_pixmap=pixmap)
        elif mime_data.hasFormat('image/svg+xml'):
            svg_data = mime_data.data('image/svg+xml')
            renderer = QSvgRenderer(svg_data)
            item = VectorItem(renderer)
            thumb = QPixmap(50, 50)
            thumb.fill(Qt.GlobalColor.transparent)
            painter = QPainter(thumb)
            renderer.render(painter)
            painter.end()
            self.add_to_repository(item, thumbnail_pixmap=thumb)

    def add_artifact(self, file_path):
        reader = QImageReader(file_path)
        if reader.canRead():
            pixmap = QPixmap(file_path)
            item = RasterItem(pixmap)
            self.add_to_repository(item, thumbnail_source=file_path)
        else:
            renderer = QSvgRenderer(file_path)
            if renderer.isValid():
                item = VectorItem(renderer)
                self.add_to_repository(item, thumbnail_source=file_path)

    def add_to_repository(self, item, thumbnail_source=None, thumbnail_pixmap=None):
        list_item = QListWidgetItem()
        pixmap = None
        if thumbnail_pixmap:
            pixmap = thumbnail_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio)
        elif thumbnail_source:
            pixmap = QPixmap(thumbnail_source).scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio)
        if pixmap:
            list_item.setIcon(QIcon(pixmap))
        list_item.setText(f"Item {self.artifact_list.count() + 1}")
        list_item.setData(Qt.ItemDataRole.UserRole, item)
        self.artifact_list.addItem(list_item)

    def add_item_to_canvas(self, item):
        if item.scene() != self.scene:
            self.scene.addItem(item)
        layer_item = QListWidgetItem()
        name = "Layer"
        if isinstance(item, QGraphicsRectItem):
            name = "Rectangle"
        elif isinstance(item, QGraphicsEllipseItem):
            name = "Ellipse"
        elif isinstance(item, RasterItem):
            name = "Image"
        elif isinstance(item, VectorItem):
            name = "Vector"
        elif isinstance(item, QGraphicsTextItem):
            name = "Text"
        layer_item.setText(f"{name} {self.layer_list.count() + 1}")
        layer_item.setData(Qt.ItemDataRole.UserRole, item)
        self.layer_list.insertItem(0, layer_item)
        self.layer_list.update_z_orders()
        # Block signals to prevent cascading selection updates
        self.scene.blockSignals(True)
        self.layer_list.blockSignals(True)
        # Clear all selections
        self.scene.clearSelection()
        self.layer_list.clearSelection()
        # Select only the new item
        item.setSelected(True)
        layer_item.setSelected(True)
        self.layer_list.setCurrentItem(layer_item)
        # Restore signals
        self.layer_list.blockSignals(False)
        self.scene.blockSignals(False)
        
        # Apply import behavior from settings
        behavior = self.settings.value("canvas/import_behavior", "keep")
        if behavior == "pan_to_new":
            self.view.pan_to_item(item)
        elif behavior == "fit_all":
            self.view.fit_all_items()
        elif behavior == "fit_new":
            self.view.fit_item(item)
        # "keep" = do nothing (default)

    def on_layer_selection_changed(self):
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        for item in self.layer_list.selectedItems():
            graphics_item = item.data(Qt.ItemDataRole.UserRole)
            # Check if C++ object is still valid
            if graphics_item and not sip.isdeleted(graphics_item):
                graphics_item.setSelected(True)
        self.scene.blockSignals(False)

    def on_scene_selection_changed(self):
        self.layer_list.blockSignals(True)
        self.layer_list.clearSelection()
        try:
            selected_items = self.scene.selectedItems()
            if selected_items:
                for i in range(self.layer_list.count()):
                    list_item = self.layer_list.item(i)
                    graphics_item = list_item.data(Qt.ItemDataRole.UserRole)
                    # Check if C++ object is still valid
                    if graphics_item and not sip.isdeleted(graphics_item):
                        if graphics_item in selected_items:
                            list_item.setSelected(True)
        except RuntimeError:
            # Handle case where scene or items are deleted
            pass
        self.layer_list.blockSignals(False)

    def flatten_selected(self):
        items = self._selected_layer_items()
        self._flatten_items(items)

    def flatten_all(self):
        self._flatten_items(self.layer_list.graphics_items())

    def delete_selected_items(self):
        items_to_delete = self._selected_layer_items()
        self._remove_items(items_to_delete)

    def _selected_layer_items(self):
        layer_items = self.layer_list.graphics_items()
        if not layer_items:
            return []
        layer_set = set(layer_items)
        items = [item for item in self.scene.selectedItems() if item in layer_set]
        for list_item in self.layer_list.selectedItems():
            graphics_item = list_item.data(Qt.ItemDataRole.UserRole)
            if graphics_item and graphics_item in layer_set and graphics_item not in items:
                items.append(graphics_item)
        return items

    def _flatten_items(self, items):
        layer_items = self.layer_list.graphics_items()
        items = [item for item in items if item in layer_items]
        if len(items) < 1:
            self._status_bar.showMessage("Select at least one item to flatten", 4000)
            return
        bounding = QRectF()
        for idx, item in enumerate(items):
            if idx == 0:
                bounding = item.sceneBoundingRect()
            else:
                bounding = bounding.united(item.sceneBoundingRect())
        if bounding.isEmpty():
            return
        size = bounding.size().toSize()
        if size.isEmpty():
            return
        scene = self.scene
        others_hidden = []
        for scene_item in scene.items():
            if scene_item not in items and scene_item.isVisible():
                scene_item.setVisible(False)
                others_hidden.append(scene_item)
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        scene.render(painter, QRectF(image.rect()), bounding)
        painter.end()
        for hidden in others_hidden:
            hidden.setVisible(True)
        new_item = RasterItem(QPixmap.fromImage(image))
        new_item.setPos(bounding.topLeft())
        self.view.itemAdded.emit(new_item)
        self._remove_items(items, clear_selection=False)
        self.scene.clearSelection()
        new_item.setSelected(True)
        self._status_bar.showMessage("Flattened items into a single layer", 4000)

    def _remove_items(self, items, clear_selection=True):
        if not items:
            return
        # Block signals to prevent selection handlers from accessing deleted items
        self.scene.blockSignals(True)
        self.layer_list.blockSignals(True)
        for graphics_item in items:
            if hasattr(graphics_item, 'clearSelectionOverlay'):
                graphics_item.clearSelectionOverlay()
            handles = getattr(graphics_item, 'handles', None)
            if handles:
                handles.cleanup()
                graphics_item.handles = None
            if graphics_item.scene() is self.scene:
                self.scene.removeItem(graphics_item)
        self.layer_list.remove_graphics_items(items)
        # Restore signals before clearing selection
        self.layer_list.blockSignals(False)
        self.scene.blockSignals(False)
        if clear_selection:
            self.scene.clearSelection()
            self.layer_list.clearSelection()
        self.view.handle_items_deleted(items)
        self.scene.update()

    def save_canvas(self):
        print(f"DEBUG save_canvas: default_save_dir = {self.default_save_dir}")
        image = self._capture_scene_image()
        if image is None:
            print("DEBUG save_canvas: No image to save (scene empty)")
            self._status_bar.showMessage("Nothing to save", 4000)
            return
        self._ensure_save_directory()
        print(f"DEBUG save_canvas: Directory exists = {self.default_save_dir.exists()}")
        base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge"
        counter = 1
        while True:
            candidate = self.default_save_dir / f"{base_name}_{counter}.png"
            if not candidate.exists():
                break
            counter += 1
        print(f"DEBUG save_canvas: Attempting to save to {candidate}")
        success = image.save(str(candidate))
        print(f"DEBUG save_canvas: Save result = {success}")
        if success:
            self._status_bar.showMessage(f"Saved canvas to {candidate}", 5000)
        else:
            self._status_bar.showMessage(f"ERROR: Failed to save to {candidate}", 5000)
            print(f"ERROR save_canvas: image.save() returned False for {candidate}")

    def _ensure_save_directory(self):
        self.default_save_dir.mkdir(parents=True, exist_ok=True)

    def _restore_window_geometry(self):
        """Restore window position and size based on startup preference."""
        startup_mode = self.settings.value("window/startup_mode", "last")
        startup_state_pref = self.settings.value("window/startup_state_pref", "normal")
        
        # Default size
        self.resize(1200, 800)
        
        if startup_mode == "last":
            geometry = self.settings.value("window/geometry")
            state = self.settings.value("window/state")
            if geometry:
                self.restoreGeometry(geometry)
            if state:
                self.restoreState(state)
        
        elif startup_mode == "monitor":
            monitor_idx = self.settings.value("window/startup_monitor", 0, type=int)
            screens = QApplication.screens()
            if 0 <= monitor_idx < len(screens):
                screen = screens[monitor_idx]
                # Center on this screen
                center = screen.availableGeometry().center()
                frame_geom = self.frameGeometry()
                frame_geom.moveCenter(center)
                self.move(frame_geom.topLeft())
                
        elif startup_mode == "mouse":
            # Move to screen with cursor
            screen = QApplication.screenAt(QCursor.pos())
            if screen:
                center = screen.availableGeometry().center()
                frame_geom = self.frameGeometry()
                frame_geom.moveCenter(center)
                self.move(frame_geom.topLeft())
        
        # Apply explicit state preference if not "last" (which handles it via restoreState)
        # OR if we want to enforce it overrides "last"? 
        # Usually "Restoring Last Session" implies restoring state too.
        # But for "monitor" or "mouse", we just positioned it, so now we apply state.
        if startup_mode != "last":
            if startup_state_pref == "maximized":
                self.showMaximized()
            elif startup_state_pref == "fullscreen":
                self.showFullScreen()
            else:
                self.showNormal()

        self._ensure_window_visible()
    
    def _ensure_window_visible(self):
        """Ensure the window is visible on a connected screen."""
        from PyQt6.QtGui import QGuiApplication
        
        window_rect = self.frameGeometry()
        window_center = window_rect.center()
        
        # Check if window center is on any available screen
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().contains(window_center):
                return  # Window is visible
        
        # Window is not on any screen - move to primary screen
        primary = QGuiApplication.primaryScreen()
        if primary:
            avail = primary.availableGeometry()
            # Center window on primary screen
            new_x = avail.x() + (avail.width() - window_rect.width()) // 2
            new_y = avail.y() + (avail.height() - window_rect.height()) // 2
            self.move(new_x, new_y)

    def _restore_selection_state(self, selected_items, overlay_item, overlay_state):
        if overlay_item and overlay_state:
            overlay_item.setVisible(overlay_state["visible"])
            if overlay_state["selected"]:
                overlay_item.setSelected(True)
        for item in selected_items:
            if item.scene() is self.scene:
                item.setSelected(True)

    def adjust_layer_z(self, delta):
        row = self.layer_list.currentRow()
        if row == -1:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.layer_list.count():
            return
        item = self.layer_list.takeItem(row)
        self.layer_list.insertItem(new_row, item)
        self.layer_list.setCurrentRow(new_row)
        self.layer_list.update_z_orders()

    def update_cursor_status(self, pos):
        if pos is None:
            self._status_bar.clearMessage()
            return
        self._status_bar.showMessage(f"Cursor: x={pos.x():.1f}, y={pos.y():.1f}")

    def _restore_splitter_sizes(self):
        default_sizes = [220, 760, 240]
        sizes = self.settings.value("main_splitter_sizes", [])
        if isinstance(sizes, list):
            int_sizes = []
            for value in sizes:
                try:
                    int_sizes.append(int(value))
                except (TypeError, ValueError):
                    continue
            if len(int_sizes) == 3:
                self._splitter.setSizes(int_sizes)
                return
        self._splitter.setSizes(default_sizes)

    def _import_library_asset(self, file_path):
        scene_pos = self.view.mapToScene(self.view.viewport().rect().center())
        if not self.view._paste_file_path(file_path, scene_pos):
            self.add_artifact(file_path)
        self._status_bar.showMessage(f"Imported {Path(file_path).name} from library", 4000)

    def _export_canvas_to_library(self):
        if not hasattr(self, 'library_panel'):
            return
        target_dir = self.library_panel.current_root_path()
        if not target_dir:
            self._status_bar.showMessage("Set a library folder before exporting", 4000)
            return
        image = self._capture_scene_image()
        if image is None:
            self._status_bar.showMessage("Nothing to export", 4000)
            return
        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"canvas_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        export_path = target_dir / file_name
        image.save(str(export_path))
        self._status_bar.showMessage(f"Exported canvas to {export_path}", 5000)
        self.library_panel.refresh()

    def _on_library_folder_changed(self, folder):
        self._status_bar.showMessage(f"Library folder: {folder}", 3000)

    def _capture_scene_image(self):
        selected_items = list(self.scene.selectedItems())
        overlay_item = None
        overlay_state = None
        overlay_host = self.view.active_selection_host()
        if overlay_host and overlay_host.hasSelectionOverlay():
            overlay_item = overlay_host.selectionOverlay()
            if overlay_item:
                overlay_state = {
                    "visible": overlay_item.isVisible(),
                    "selected": overlay_item.isSelected(),
                }
                overlay_item.setSelected(False)
                overlay_item.setVisible(False)
        self.scene.clearSelection()
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            rect = QRectF(self.view.viewport().rect())
        size = rect.size().toSize()
        if size.isEmpty():
            self._restore_selection_state(selected_items, overlay_item, overlay_state)
            return None
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        self._restore_selection_state(selected_items, overlay_item, overlay_state)
        return image

    def closeEvent(self, event):
        """Save window state before closing."""
        if hasattr(self, '_splitter'):
            self.settings.setValue("main_splitter_sizes", self._splitter.sizes())
        # Always save geometry
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        
        # Helper: save current monitor index for reference (optional usage)
        current_screen = self.screen()
        screens = QApplication.screens()
        if current_screen in screens:
            self.settings.setValue("window/last_monitor_index", screens.index(current_screen))

        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
