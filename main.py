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
             QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem,
             QListWidgetItem, QLabel,
             QAbstractItemView, QGraphicsItem, QGraphicsTextItem, QMenu, QSplitter,
             QDialog, QDialogButtonBox, QTabWidget, QFormLayout, QLineEdit,
             QPushButton, QHBoxLayout, QGroupBox, QFrame, QComboBox, QCheckBox,
             QToolButton, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
             QMessageBox, QGraphicsBlurEffect, QSlider)
import shutil

__version__ = "0.6.0-beta.3"
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer
from PyQt6 import sip
from PyQt6.QtGui import (QPixmap, QImageReader, QAction, QPainter, QIcon, QPen, QColor, QBrush,
                     QFont, QTransform, QClipboard, QImage, QKeySequence, QTextCursor, QPalette,
                     QFontMetrics, QPainterPath, QPolygonF)
from PyQt6.QtCore import (Qt, QTimer, QPointF, QPoint, pyqtSignal, QRectF, QSize, QSettings, 
                          QByteArray, QMimeData, QBuffer, QIODevice, QSizeF, QUrl)
from pathlib import Path
import datetime
from image_library_panel import ImageLibraryPanel
from undo_manager import UndoManager, CallbackAction
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
    CUTOUT = auto()
    ARROW = auto()
    STEP = auto()
    BLUR = auto()
    BORDER = auto()
    HIGHLIGHT = auto()


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
        self._row_layouts = []  # legacy, kept for compatibility, no longer used
        self._last_width = 0
        self._dirty = True
        self._content_height = 0

    def invalidate(self):
        """Force the next rebuild to actually run regardless of width change."""
        self._dirty = True

    def addWidget(self, widget):
        """Add a widget to the flow layout."""
        self._items.append(widget)
        widget.setParent(self.parentWidget())
        self._dirty = True

    def clear(self):
        """Clear all widgets - actually deletes them."""
        for widget in self._items:
            widget.setParent(None)
            widget.deleteLater()
        self._items.clear()
        self._last_width = 0
        self._content_height = 0
        self._dirty = True
    
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
        """Position items directly via setGeometry — no nested layouts."""
        if not self._dirty and abs(available_width - self._last_width) < 10:
            return self._content_height  # no change
        self._last_width = available_width
        self._dirty = False

        margin = self.contentsMargins()
        h_margin_l = margin.left()
        h_margin_r = margin.right()
        v_margin_t = margin.top()
        v_margin_b = margin.bottom()
        max_width = max(100, available_width - h_margin_l - h_margin_r)

        x = h_margin_l
        y = v_margin_t
        row_h = 0

        for widget in self._items:
            if not widget or not hasattr(widget, "sizeHint"):
                continue
            ww = widget.sizeHint().width()
            wh = widget.sizeHint().height()
            if x > h_margin_l and x + ww > h_margin_l + max_width:
                # wrap to next row
                x = h_margin_l
                y += row_h + self._v_spacing
                row_h = 0
            widget.setGeometry(x, y, ww, wh)
            widget.show()
            x += ww + self._h_spacing
            row_h = max(row_h, wh)

        self._content_height = y + row_h + v_margin_b
        return self._content_height


class WrappingToolBar(QWidget):
    """A toolbar widget that wraps buttons to new rows when space is limited.

    Button geometry is derived from the current font metrics, icon size, and
    button style so the toolbar stays usable even when the user picks a larger
    system font or a bigger icon size.
    """

    DEFAULT_ICON_SIZE = 48
    H_PADDING = 14
    V_PADDING = 10
    AUTOFIT_LADDER = (
        # (icon_px, style)  — tried in order, biggest first
        (64, Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        (48, Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        (40, Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        (32, Qt.ToolButtonStyle.ToolButtonTextBesideIcon),
        (32, Qt.ToolButtonStyle.ToolButtonIconOnly),
        (24, Qt.ToolButtonStyle.ToolButtonIconOnly),
        (20, Qt.ToolButtonStyle.ToolButtonIconOnly),
        (16, Qt.ToolButtonStyle.ToolButtonIconOnly),
    )
    AUTOFIT_MAX_ROWS = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = FlowLayout(self, margin=5, h_spacing=2, v_spacing=2)
        self._buttons = []
        self._separators = []
        self._icon_size = QSize(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE)
        self._button_style = Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        self._uniform_width = False
        self._autofit = False
        self._autofitting = False  # reentrancy guard
        # Allow the dock to shrink horizontally with the window; vertical
        # sizing is left to the layout so the buttons stay visible.
        self.setMinimumWidth(0)
        self.setStyleSheet(
            """
            QToolButton {
                font-weight: bold;
                padding: 2px;
            }
            """
        )

    def _compute_geometry(self):
        """Resize every button to fit the current icon size + font metrics + style.

        Does NOT trigger a layout rebuild — the next resizeEvent (or an explicit
        setIconSize/setToolButtonStyle/setUniformWidth call) handles that. This
        keeps construction-time button additions cheap and avoids feeding stale
        widget widths into FlowLayout while the dock is still being assembled.
        """
        if not self._buttons:
            return

        font = self._buttons[0].font()
        metrics = QFontMetrics(font)
        line_h = metrics.height()
        icon_w = self._icon_size.width()
        icon_h = self._icon_size.height()
        style = self._button_style

        per_button_widths = []
        max_width = 0
        max_height = 0
        for btn in self._buttons:
            text = btn.text() or ""
            text_w = metrics.horizontalAdvance(text)

            if style == Qt.ToolButtonStyle.ToolButtonIconOnly:
                w = icon_w + self.H_PADDING
                h = icon_h + self.V_PADDING
            elif style == Qt.ToolButtonStyle.ToolButtonTextOnly:
                w = text_w + self.H_PADDING
                h = line_h + self.V_PADDING
            elif style == Qt.ToolButtonStyle.ToolButtonTextBesideIcon:
                w = icon_w + 6 + text_w + self.H_PADDING
                h = max(icon_h, line_h) + self.V_PADDING
            else:  # ToolButtonTextUnderIcon
                w = max(icon_w, text_w) + self.H_PADDING
                h = icon_h + 4 + line_h + self.V_PADDING

            per_button_widths.append(w)
            max_width = max(max_width, w)
            max_height = max(max_height, h)

        for btn, w in zip(self._buttons, per_button_widths):
            btn.setFixedWidth(max_width if self._uniform_width else w)
            btn.setFixedHeight(max_height)

        for sep in self._separators:
            sep.setFixedHeight(max(20, max_height - 10))

        self._layout.invalidate()

    def _relayout(self):
        """Reflow buttons across the current widget width and resize the host."""
        self._layout.invalidate()
        h = self._layout.rebuild(max(self.width(), 100))
        if h:
            self.setMinimumHeight(h)
            self.setMaximumHeight(h)
        self.updateGeometry()

    def sizeHint(self):
        h = self._layout._content_height or 100
        return QSize(max(self.width(), 200), h)

    def minimumSizeHint(self):
        if self._buttons:
            btn_h = self._buttons[0].height() or 32
            margin = self._layout.contentsMargins()
            return QSize(80, btn_h + margin.top() + margin.bottom())
        return super().minimumSizeHint()

    def setIconSize(self, size):
        if isinstance(size, QSizeF):
            size = size.toSize()
        self._icon_size = size
        for btn in self._buttons:
            btn.setIconSize(self._icon_size)
        self._compute_geometry()
        self._relayout()

    def iconSize(self):
        return self._icon_size

    def setToolButtonStyle(self, style):
        self._button_style = style
        for btn in self._buttons:
            btn.setToolButtonStyle(self._button_style)
        self._compute_geometry()
        self._relayout()

    def toolButtonStyle(self):
        return self._button_style

    def setUniformWidth(self, uniform: bool):
        self._uniform_width = bool(uniform)
        self._compute_geometry()
        self._relayout()

    def uniformWidth(self) -> bool:
        return self._uniform_width

    def setAutoFit(self, enabled: bool):
        """When enabled, shrink icon size / button style automatically so the
        toolbar fits within AUTOFIT_MAX_ROWS at the current widget width."""
        self._autofit = bool(enabled)
        if self._autofit and self._buttons:
            self._run_autofit()
        else:
            self._compute_geometry()
            self._relayout()

    def autoFit(self) -> bool:
        return self._autofit

    def _estimate_rows(self, available_width: int) -> int:
        if not self._buttons:
            return 0
        margin = self._layout.contentsMargins().left() + self._layout.contentsMargins().right()
        max_w = max(50, available_width - margin - 20)
        spacing = self._layout._h_spacing
        rows = 1
        used = 0
        widgets = self._buttons + self._separators
        # Iterate in DOM order — buttons interleaved with separators in _layout._items.
        for w in self._layout._items:
            if not hasattr(w, "sizeHint"):
                continue
            ww = w.sizeHint().width()
            if used + ww > max_w and used > 0:
                rows += 1
                used = 0
            used += ww + spacing
        return rows

    def _run_autofit(self):
        """Pick the largest entry on AUTOFIT_LADDER that fits in N rows."""
        if self._autofitting or not self._buttons:
            return
        self._autofitting = True
        try:
            parent_w = self.parentWidget().width() if self.parentWidget() else 0
            target_w = max(self.width(), parent_w, self.minimumWidth(), 100)
            chosen = self.AUTOFIT_LADDER[-1]
            for icon_px, style in self.AUTOFIT_LADDER:
                self._icon_size = QSize(icon_px, icon_px)
                self._button_style = style
                for btn in self._buttons:
                    btn.setIconSize(self._icon_size)
                    btn.setToolButtonStyle(self._button_style)
                self._compute_geometry()
                if self._estimate_rows(target_w) <= self.AUTOFIT_MAX_ROWS:
                    chosen = (icon_px, style)
                    break
            # Final apply with the chosen rung (already applied — just confirm).
            icon_px, style = chosen
            self._icon_size = QSize(icon_px, icon_px)
            self._button_style = style
            for btn in self._buttons:
                btn.setIconSize(self._icon_size)
                btn.setToolButtonStyle(self._button_style)
            self._compute_geometry()
            self._relayout()
        finally:
            self._autofitting = False

    def _action_help_text(self, action):
        """Return the hover/help text shown when toolbar labels are hidden."""
        tooltip = (action.toolTip() or action.text() or "").replace("&", "").strip()
        if tooltip.endswith("..."):
            tooltip = tooltip[:-3].rstrip()
        if not tooltip:
            tooltip = "Toolbar action"
        return tooltip

    def addAction(self, action):
        """Add an action as a tool button."""
        btn = QToolButton()
        help_text = self._action_help_text(action)
        action.setToolTip(help_text)
        action.setStatusTip(help_text)
        action.setWhatsThis(help_text)
        btn.setDefaultAction(action)
        btn.setIconSize(self._icon_size)
        btn.setToolButtonStyle(self._button_style)
        btn.setAutoRaise(False)
        # Apply directly to the QToolButton too; Qt does not always refresh the
        # visible hover text after setDefaultAction when the toolbar switches
        # into icon-only mode.
        btn.setToolTip(help_text)
        btn.setStatusTip(help_text)
        btn.setWhatsThis(help_text)
        btn.setAccessibleName(help_text)
        btn.setAccessibleDescription(help_text)
        self._buttons.append(btn)
        self._layout.addWidget(btn)
        self._compute_geometry()
        return btn

    def addSeparator(self):
        """Add a visual separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(2)
        self._separators.append(sep)
        self._layout.addWidget(sep)
        self._compute_geometry()

    def clear(self):
        """Clear all buttons and separators."""
        self._layout.clear()
        self._buttons.clear()
        self._separators.clear()

    def resizeEvent(self, event):
        """Rebuild layout when resized."""
        super().resizeEvent(event)
        if self._autofit:
            self._run_autofit()
        self._layout.rebuild(self.width())


HANDLE_LEFT = {0, 3, 7}
HANDLE_RIGHT = {1, 2, 5}
HANDLE_TOP = {0, 1, 4}
HANDLE_BOTTOM = {2, 3, 6}
HANDLE_CORNERS = {0, 1, 2, 3}

CANVAS_STANDARD_SIZE_PRESETS = (
    ("X Article Banner", 1920, 368),
    ("X Post Image", 1600, 900),
    ("X Post Image Compact", 1200, 675),
    ("X Website Card", 1200, 628),
    ("X Website Card Small", 800, 418),
    ("X Profile Header", 1500, 500),
    ("X Square Image", 1200, 1200),
    ("X Portrait Image", 1440, 1800),
    ("X Vertical Image", 1080, 1920),
    ("Open Graph Share", 1200, 630),
    ("LinkedIn Post", 1200, 627),
    ("LinkedIn Personal Banner", 1584, 396),
    ("Facebook Cover", 851, 315),
    ("Instagram Square", 1080, 1080),
    ("Instagram Portrait", 1080, 1350),
    ("Instagram Story/Reel", 1080, 1920),
    ("Threads Portrait", 1080, 1350),
    ("TikTok/Reels/Shorts", 1080, 1920),
    ("YouTube Thumbnail", 1280, 720),
    ("YouTube Channel Art", 2560, 1440),
    ("Pinterest Pin", 1000, 1500),
    ("Reddit Link Image", 1200, 628),
    ("HD 720p", 1280, 720),
    ("HD 1080p", 1920, 1080),
    ("4K UHD", 3840, 2160),
)


def _resize_modifiers(modifiers=None):
    if modifiers is None:
        modifiers = QApplication.keyboardModifiers()
    shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
    alt = bool(modifiers & Qt.KeyboardModifier.AltModifier)
    ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    return {
        "shift": shift,
        "alt": alt,
        "ctrl": ctrl,
        "centered": alt,
        "aspect_locked": not (shift or ctrl),
        "skew": ctrl and shift and not alt,
        "perspective": ctrl and shift and alt,
    }


def _resize_axes(handle_index):
    return (
        handle_index in (HANDLE_LEFT | HANDLE_RIGHT),
        handle_index in (HANDLE_TOP | HANDLE_BOTTOM),
    )


def _factor_from_drag(start_rect, raw_w, raw_h, width_changes, height_changes):
    factors = []
    if width_changes and start_rect.width() > 0:
        factors.append(raw_w / start_rect.width())
    if height_changes and start_rect.height() > 0:
        factors.append(raw_h / start_rect.height())
    if not factors:
        return 1.0
    return max(0.01, max(factors, key=lambda value: abs(value - 1.0)))


def _rect_from_resize_drag(start_rect: QRectF, handle_index: int, scene_pos: QPointF,
                           min_w=1.0, min_h=1.0, modifiers=None) -> QRectF:
    """Apply the app's standard resize-handle modifier rules to a scene rect."""
    mods = _resize_modifiers(modifiers)
    start = QRectF(start_rect).normalized()
    center = start.center()
    width_changes, height_changes = _resize_axes(handle_index)
    start_w = max(float(min_w), start.width())
    start_h = max(float(min_h), start.height())

    if mods["centered"]:
        raw_w = max(float(min_w), abs(scene_pos.x() - center.x()) * 2.0) if width_changes else start_w
        raw_h = max(float(min_h), abs(scene_pos.y() - center.y()) * 2.0) if height_changes else start_h
        if mods["aspect_locked"]:
            factor = _factor_from_drag(start, raw_w, raw_h, width_changes, height_changes)
            raw_w = max(float(min_w), start_w * factor)
            raw_h = max(float(min_h), start_h * factor)
        return QRectF(center.x() - raw_w / 2.0, center.y() - raw_h / 2.0, raw_w, raw_h)

    anchor_x = start.right() if handle_index in HANDLE_LEFT else start.left() if handle_index in HANDLE_RIGHT else center.x()
    anchor_y = start.bottom() if handle_index in HANDLE_TOP else start.top() if handle_index in HANDLE_BOTTOM else center.y()
    raw_w = max(float(min_w), abs(scene_pos.x() - anchor_x)) if width_changes else start_w
    raw_h = max(float(min_h), abs(scene_pos.y() - anchor_y)) if height_changes else start_h

    if mods["aspect_locked"]:
        factor = _factor_from_drag(start, raw_w, raw_h, width_changes, height_changes)
        raw_w = max(float(min_w), start_w * factor)
        raw_h = max(float(min_h), start_h * factor)

    if handle_index in HANDLE_LEFT:
        left = anchor_x - raw_w
    elif handle_index in HANDLE_RIGHT:
        left = anchor_x
    else:
        left = anchor_x - raw_w / 2.0

    if handle_index in HANDLE_TOP:
        top = anchor_y - raw_h
    elif handle_index in HANDLE_BOTTOM:
        top = anchor_y
    else:
        top = anchor_y - raw_h / 2.0

    return QRectF(left, top, raw_w, raw_h)


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
        self._start_transform = QTransform()
        self._start_origin = QPointF()

    def cleanup(self):
        if self.scene():
            self.scene().removeItem(self)

    def _anchor_for_handle(self, centered=False):
        rect = self.parent_item.boundingRect()
        if centered:
            return rect.center()
        idx = getattr(self, "handle_index", 2)
        anchors = {
            0: rect.bottomRight(),
            1: rect.bottomLeft(),
            2: rect.topLeft(),
            3: rect.topRight(),
            4: QPointF(rect.center().x(), rect.bottom()),
            5: QPointF(rect.left(), rect.center().y()),
            6: QPointF(rect.center().x(), rect.top()),
            7: QPointF(rect.right(), rect.center().y()),
        }
        return anchors.get(idx, rect.center())

    def _transform_around_anchor(self, delta_transform, anchor):
        around = QTransform()
        around.translate(anchor.x(), anchor.y())
        around = around * delta_transform
        around.translate(-anchor.x(), -anchor.y())
        return around * self._start_transform

    def _apply_nonuniform_resize(self, current_vector, modifiers):
        start_x = self._start_vector.x()
        start_y = self._start_vector.y()
        idx = getattr(self, "handle_index", 2)
        width_changes, height_changes = _resize_axes(idx)
        sx = abs(current_vector.x() / start_x) if width_changes and abs(start_x) > 0.01 else 1.0
        sy = abs(current_vector.y() / start_y) if height_changes and abs(start_y) > 0.01 else 1.0
        sx = max(0.05, min(20.0, sx))
        sy = max(0.05, min(20.0, sy))
        anchor = self._anchor_for_handle(centered=modifiers["centered"])
        delta = QTransform()
        delta.scale(sx, sy)
        self.parent_item.setTransform(self._transform_around_anchor(delta, anchor))

    def _apply_skew_resize(self, current_vector, perspective=False):
        rect = self.parent_item.boundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        delta = current_vector - self._start_vector
        idx = getattr(self, "handle_index", 2)
        width_changes, height_changes = _resize_axes(idx)
        sh = max(-2.0, min(2.0, delta.x() / max(1.0, rect.width())))
        sv = max(-2.0, min(2.0, delta.y() / max(1.0, rect.height())))
        transform = QTransform()
        if width_changes and not height_changes:
            transform.shear(0.0, sv)
        elif height_changes and not width_changes:
            transform.shear(sh, 0.0)
        else:
            transform.shear(sh, sv)
        if perspective:
            # Qt can render projective transforms, but keep the coefficient
            # tiny so a quick handle drag cannot explode the item geometry.
            px = max(-0.002, min(0.002, delta.x() / max(1.0, rect.width() * rect.width())))
            py = max(-0.002, min(0.002, delta.y() / max(1.0, rect.height() * rect.height())))
            transform.setMatrix(
                transform.m11(), transform.m12(), px,
                transform.m21(), transform.m22(), py,
                transform.m31(), transform.m32(), transform.m33(),
            )
        anchor = rect.center()
        self.parent_item.setTransform(self._transform_around_anchor(transform, anchor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.parent_item, 'handle_resize_press'):
                self.grabMouse()
                self.parent_item.handle_resize_press(self, event.scenePos())
                event.accept()
                return
            rect = self.parent_item.boundingRect()
            self._start_center = self.parent_item.mapToScene(rect.center())
            self._start_vector = event.scenePos() - self._start_center
            self._start_scale = self.parent_item.scale()
            self._start_transform = QTransform(self.parent_item.transform())
            self._start_origin = QPointF(self.parent_item.transformOriginPoint())
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
        modifiers = _resize_modifiers(event.modifiers())
        if modifiers["perspective"]:
            self._apply_skew_resize(current_vector, perspective=True)
            self.handles.update_handles()
            event.accept()
            return
        if modifiers["skew"]:
            self._apply_skew_resize(current_vector)
            self.handles.update_handles()
            event.accept()
            return
        if not modifiers["aspect_locked"]:
            self._apply_nonuniform_resize(current_vector, modifiers)
            self.handles.update_handles()
            event.accept()
            return
        factor = max(0.1, min(10.0, current_length / start_length))
        self.parent_item.setTransform(self._start_transform)
        self.parent_item.setScale(self._start_scale * factor)
        self.handles.update_handles()
        event.accept()

    def mouseReleaseEvent(self, event):
        if hasattr(self.parent_item, 'handle_resize_release'):
            self.ungrabMouse()
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


class CanvasArrowItem(ContextMenuForwarder, QGraphicsPathItem):
    """Arrow annotation: tail at start, arrowhead at end. Points stored in
    item-local coordinates so rotate/scale handles behave like other shapes.
    """
    supports_rotation_handles = True

    def __init__(self, start: QPointF, end: QPointF):
        super().__init__()
        self._start = QPointF(start)
        self._end = QPointF(end)
        self._head_size = 18.0
        self.setPen(QPen(QColor(220, 50, 50), 4, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self.setBrush(QBrush(QColor(220, 50, 50)))
        self._rebuild_path()

    def setEndpoints(self, start: QPointF, end: QPointF):
        self._start = QPointF(start)
        self._end = QPointF(end)
        self._rebuild_path()

    def endpoints(self):
        return (QPointF(self._start), QPointF(self._end))

    def _rebuild_path(self):
        path = QPainterPath()
        sx, sy = self._start.x(), self._start.y()
        ex, ey = self._end.x(), self._end.y()
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length < 1.0:
            self.setPath(path)
            return
        ux, uy = dx / length, dy / length
        head = self._head_size
        # Shorten the line so it ends at the base of the arrowhead.
        line_end_x = ex - ux * head * 0.6
        line_end_y = ey - uy * head * 0.6
        path.moveTo(sx, sy)
        path.lineTo(line_end_x, line_end_y)
        # Arrowhead triangle.
        nx, ny = -uy, ux
        head_back_x = ex - ux * head
        head_back_y = ey - uy * head
        left = QPointF(head_back_x + nx * head * 0.5, head_back_y + ny * head * 0.5)
        right = QPointF(head_back_x - nx * head * 0.5, head_back_y - ny * head * 0.5)
        head_path = QPainterPath()
        head_path.moveTo(QPointF(ex, ey))
        head_path.lineTo(left)
        head_path.lineTo(right)
        head_path.closeSubpath()
        path.addPath(head_path)
        self.setPath(path)

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasStepItem(ContextMenuForwarder, QGraphicsPathItem):
    """Numbered marker pin for the Step tool: tear-drop with a number.

    First-class scene item — selectable, movable, scalable, rotatable, and
    z-order adjustable like every other annotation. Double-click the pin to
    edit the displayed number.
    """
    supports_rotation_handles = True
    DEFAULT_FILL = QColor("#2a82da")
    DEFAULT_BORDER = QColor("#1f5f9e")

    def __init__(self, number: int, center: QPointF, radius: float = 22.0,
                 fill: QColor | None = None, border: QColor | None = None):
        super().__init__()
        self._number = int(number)
        self._radius = float(radius)
        self.setPen(QPen(border or self.DEFAULT_BORDER, 2))
        self.setBrush(QBrush(fill or self.DEFAULT_FILL))
        self._rebuild_path()
        self.setPos(center)
        self.setTransformOriginPoint(0, 0)

    def number(self) -> int:
        return self._number

    def setNumber(self, n: int):
        self._number = int(n)
        self.update()

    def setFillColor(self, color: QColor):
        self.setBrush(QBrush(color))
        self.update()

    def setBorderColor(self, color: QColor):
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)
        self.update()

    def _rebuild_path(self):
        r = self._radius
        path = QPainterPath()
        # Teardrop: circle with a downward point.
        path.addEllipse(QPointF(0, 0), r, r)
        tail = QPainterPath()
        tail.moveTo(-r * 0.55, r * 0.55)
        tail.lineTo(0, r * 1.7)
        tail.lineTo(r * 0.55, r * 0.55)
        tail.closeSubpath()
        path.addPath(tail)
        self.setPath(path)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("white")))
        font = QFont("Arial")
        font.setBold(True)
        font.setPointSizeF(self._radius * 0.9)
        painter.setFont(font)
        rect = QRectF(-self._radius, -self._radius, self._radius * 2, self._radius * 2)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._number))
        painter.restore()

    def mouseDoubleClickEvent(self, event):
        scene = self.scene()
        if scene and scene.views():
            view = scene.views()[0]
            new_n, ok = QInputDialog.getInt(
                view, "Step number",
                f"Edit step number (current: {self._number})",
                self._number, 0, 9999, 1,
            )
            if ok:
                self.setNumber(new_n)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasTextItem(ContextMenuForwarder, QGraphicsTextItem):
    supports_rotation_handles = False

    def __init__(self, text):
        super().__init__(text)
        self.setDefaultTextColor(QColor("black"))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self._editing = False
        self._font_resize_start_distance = None
        self._font_resize_start_size = None
        self._font_resize_center = None
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

    def handle_resize_press(self, handle, scene_pos):
        self._was_movable_before_resize = self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        center_local = self.boundingRect().center()
        self._font_resize_center = self.mapToScene(center_local)
        vector = scene_pos - self._font_resize_center
        self._font_resize_start_distance = math.hypot(vector.x(), vector.y())

        font = self.font()
        start_size = font.pointSizeF()
        if start_size <= 0:
            start_size = float(max(1, font.pointSize()))
        if start_size <= 0:
            start_size = 12.0

        self._font_resize_start_size = start_size

    def handle_resize_drag(self, handle, scene_pos):
        if not self._font_resize_center or not self._font_resize_start_distance or not self._font_resize_start_size:
            return

        vector = scene_pos - self._font_resize_center
        current_distance = math.hypot(vector.x(), vector.y())
        if current_distance <= 0:
            return

        factor = current_distance / self._font_resize_start_distance
        new_size = max(6.0, min(512.0, self._font_resize_start_size * factor))

        font = self.font()
        font.setPointSizeF(new_size)
        self.setFont(font)
        self._update_transform_origin()
        if self.handles:
            self.handles.update_handles()

    def handle_resize_release(self, handle, scene_pos):
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            bool(getattr(self, '_was_movable_before_resize', True)),
        )
        self._font_resize_start_distance = None
        self._font_resize_start_size = None
        self._font_resize_center = None


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
        idx = self._active_handle_index
        rect = _rect_from_resize_drag(self._drag_start_rect, idx, scene_pos, 1, 1)
        self.set_scene_rect(rect)

    def handle_resize_release(self, handle, scene_pos):
        self._active_handle_index = None
        self._drag_start_rect = QRectF()


class CutoutOverlay(QGraphicsRectItem):
    is_canvas_chrome = True

    def __init__(self):
        super().__init__(0, 0, 0, 0)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(100002)
        self._add_space = False
        self._axis = None
        self._min_px = 1.0
        self._line_length = 80.0
        self._line_pos = QPointF()
        self._rect = QRectF()
        self._update_style()

    def boundingRect(self):
        rect = super().boundingRect()
        if rect.isEmpty():
            pad = 5
            if self._axis == "vertical":
                return QRectF(
                    self._line_pos.x() - pad,
                    self._line_pos.y() - self._line_length / 2,
                    pad * 2,
                    self._line_length,
                )
            return QRectF(
                self._line_pos.x() - self._line_length / 2,
                self._line_pos.y() - pad,
                self._line_length,
                pad * 2,
            )
        return rect.adjusted(-2, -2, 2, 2)

    def set_preview(self, rect: QRectF, axis: str | None, add_space: bool):
        self.prepareGeometryChange()
        self._axis = axis
        self._add_space = add_space
        self._rect = QRectF(rect).normalized()
        self._update_style()
        if self._rect.width() >= self._min_px and self._rect.height() >= self._min_px:
            self.setRect(0, 0, self._rect.width(), self._rect.height())
            self.setPos(self._rect.topLeft())
        else:
            self.setRect(0, 0, 0, 0)
            self._line_pos = self._rect.topLeft()
            self.setPos(0, 0)

    def _update_style(self):
        color = QColor("#22c55e") if self._add_space else QColor("#ef4444")
        self.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
        fill = QColor(color)
        fill.setAlpha(70 if self._add_space else 85)
        self.setBrush(QBrush(fill))

    def paint(self, painter, option, widget=None):
        if not self.rect().isEmpty():
            super().paint(painter, option, widget)
            return
        painter.save()
        self._update_style()
        painter.setPen(self.pen())
        if self._axis == "vertical":
            painter.drawLine(
                QPointF(self._line_pos.x(), self._line_pos.y() - self._line_length / 2),
                QPointF(self._line_pos.x(), self._line_pos.y() + self._line_length / 2),
            )
        else:
            painter.drawLine(
                QPointF(self._line_pos.x() - self._line_length / 2, self._line_pos.y()),
                QPointF(self._line_pos.x() + self._line_length / 2, self._line_pos.y()),
            )
        painter.restore()


class CanvasResizeHandle(QGraphicsRectItem):
    is_canvas_chrome = True

    def __init__(self, canvas_item, handle_index, cursor):
        super().__init__(-5, -5, 10, 10)
        self.canvas_item = canvas_item
        self.handle_index = handle_index
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(cursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setPen(QPen(QColor("#6b7280"), 1))
        self.setBrush(QBrush(QColor("#f8fafc")))
        self.setZValue(100000)

    def mousePressEvent(self, event):
        self.grabMouse()
        self.canvas_item.start_resize(self.handle_index, event.modifiers())
        event.accept()

    def mouseMoveEvent(self, event):
        self.canvas_item.resize_to(self.handle_index, event.scenePos(), event.modifiers())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.ungrabMouse()
        self.canvas_item.finish_resize()
        event.accept()


class CanvasSizeReadoutItem(QGraphicsItem):
    is_canvas_chrome = True

    def __init__(self):
        super().__init__()
        self._text = ""
        self._rect = QRectF(14, -34, 96, 28)
        self._font = QFont("Arial", 9)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(100001)
        self.setVisible(False)

    def boundingRect(self):
        return self._rect.adjusted(-2, -2, 2, 2)

    def set_readout(self, text: str, handle_index: int):
        metrics = QFontMetrics(self._font)
        width = max(74, metrics.horizontalAdvance(text) + 18)
        height = metrics.height() + 10
        if handle_index == 0:       # top-left
            x, y = -width - 14, -height - 14
        elif handle_index == 1:     # top-right
            x, y = 14, -height - 14
        elif handle_index == 2:     # bottom-right
            x, y = 14, 14
        elif handle_index == 3:     # bottom-left
            x, y = -width - 14, 14
        elif handle_index == 4:     # top edge
            x, y = 14, -height - 14
        elif handle_index == 5:     # right edge
            x, y = 14, -height / 2
        elif handle_index == 6:     # bottom edge
            x, y = 14, 14
        else:                       # left edge
            x, y = -width - 14, -height / 2
        self.prepareGeometryChange()
        self._text = text
        self._rect = QRectF(x, y, width, height)
        self.update()

    def paint(self, painter, option, widget=None):
        if not self._text:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.setBrush(QBrush(QColor(248, 250, 252, 235)))
        painter.drawRoundedRect(self._rect, 2, 2)
        painter.setFont(self._font)
        painter.setPen(QPen(QColor("#475569")))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()


class CanvasInfoTagItem(QGraphicsItem):
    is_canvas_chrome = True

    def __init__(self):
        super().__init__()
        self._text = ""
        self._rect = QRectF(0, 0, 240, 24)
        self._font = QFont("Arial", 9)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(100001)

    def boundingRect(self):
        return self._rect.adjusted(-2, -2, 2, 2)

    def set_info(self, width: int, height: int, image_type="PNG", transparent=True):
        transparency = "Transparency On" if transparent else "Transparency Off"
        self._text = (
            f"Resolution {width} x {height} px | "
            f"Ratio {self._aspect_label(width, height)} | "
            f"{image_type.upper()} | {transparency}"
        )
        metrics = QFontMetrics(self._font)
        tag_width = max(240, metrics.horizontalAdvance(self._text) + 22)
        tag_height = metrics.height() + 10
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, tag_width, tag_height)
        self.update()

    def _aspect_label(self, width: int, height: int) -> str:
        if width <= 0 or height <= 0:
            return "--"
        ratio = width / height
        common = (
            ("1:1", 1.0),
            ("16:9", 16 / 9),
            ("9:16", 9 / 16),
            ("1.91:1", 1.91),
            ("4:5", 4 / 5),
            ("5:4", 5 / 4),
            ("2:3", 2 / 3),
            ("3:4", 3 / 4),
            ("3:1", 3.0),
            ("5.2:1", 5.2),
        )
        for label, target in common:
            if abs(ratio - target) < 0.015:
                return label
        divisor = math.gcd(int(width), int(height))
        aspect_w = int(width) // divisor
        aspect_h = int(height) // divisor
        if aspect_w <= 40 and aspect_h <= 40:
            return f"{aspect_w}:{aspect_h}"
        return f"{ratio:.2f}:1"

    def paint(self, painter, option, widget=None):
        if not self._text:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.setBrush(QBrush(QColor(248, 250, 252, 235)))
        painter.drawRoundedRect(self._rect, 2, 2)
        painter.setFont(self._font)
        painter.setPen(QPen(QColor("#334155")))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()


class CanvasBoundsItem(QGraphicsRectItem):
    is_canvas_chrome = True
    MIN_SIZE = 64
    CHECK_SIZE = 16
    PADDING = 64

    def __init__(self, rect: QRectF, settings=None):
        super().__init__(rect)
        self.settings = settings
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(-100000)
        self.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._active_resize_index = None
        self._resize_start_rect = QRectF(rect)
        self._handles = []
        self._readout = CanvasSizeReadoutItem()
        self._info_tag = CanvasInfoTagItem()
        self._active_snap_label = ""
        self._create_handles()

    def _create_handles(self):
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
        self._handles = [
            CanvasResizeHandle(self, idx, cursor)
            for idx, cursor in enumerate(cursors)
        ]

    def add_to_scene(self, scene):
        if self.scene() is not scene:
            scene.addItem(self)
        for handle in self._handles:
            if handle.scene() is not scene:
                scene.addItem(handle)
        if self._readout.scene() is not scene:
            scene.addItem(self._readout)
        if self._info_tag.scene() is not scene:
            scene.addItem(self._info_tag)
        self.update_handles()

    def paint(self, painter, option, widget=None):
        rect = self.rect()
        painter.save()
        painter.fillRect(rect, QColor("#ffffff"))
        tile = self.CHECK_SIZE
        light = QColor("#f8fafc")
        dark = QColor("#e2e8f0")
        left = int(math.floor(rect.left() / tile) * tile)
        top = int(math.floor(rect.top() / tile) * tile)
        y = top
        while y < rect.bottom():
            x = left
            while x < rect.right():
                color = dark if ((x // tile) + (y // tile)) % 2 == 0 else light
                painter.fillRect(QRectF(x, y, tile, tile).intersected(rect), color)
                x += tile
            y += tile
        painter.restore()
        super().paint(painter, option, widget)

    def update_handles(self):
        rect = self.rect()
        points = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomRight(),
            rect.bottomLeft(),
            QPointF(rect.center().x(), rect.top()),
            QPointF(rect.right(), rect.center().y()),
            QPointF(rect.center().x(), rect.bottom()),
            QPointF(rect.left(), rect.center().y()),
        ]
        for handle, point in zip(self._handles, points):
            handle.setPos(point)
        self._update_info_tag()

    def start_resize(self, handle_index, modifiers=None):
        self._active_resize_index = handle_index
        self._resize_start_rect = QRectF(self.rect())
        self._active_snap_label = ""
        self._update_size_readout(handle_index, show=True)

    def resize_to(self, handle_index, scene_pos, modifiers=None):
        mods = _resize_modifiers(modifiers)
        rect = _rect_from_resize_drag(
            self._resize_start_rect, handle_index, scene_pos,
            self.MIN_SIZE, self.MIN_SIZE, modifiers,
        )
        snap_probe = rect
        if mods["alt"]:
            snap_modifiers = modifiers | Qt.KeyboardModifier.ShiftModifier if modifiers is not None else Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier
            snap_probe = _rect_from_resize_drag(
                self._resize_start_rect, handle_index, scene_pos,
                self.MIN_SIZE, self.MIN_SIZE, snap_modifiers,
            )
        rect = self._snap_resize_rect(rect, handle_index, modifiers, snap_probe)
        self.prepareGeometryChange()
        self.setRect(rect)
        self.update_handles()
        self._update_size_readout(handle_index, show=True)
        scene = self.scene()
        if scene:
            scene.setSceneRect(rect.adjusted(-2000, -2000, 2000, 2000))
            scene.update()

    def finish_resize(self):
        self._active_resize_index = None
        self._readout.setVisible(False)
        self._active_snap_label = ""
        if self.settings:
            rect = self.rect()
            self.settings.setValue("canvas/workspace_x", rect.x())
            self.settings.setValue("canvas/workspace_y", rect.y())
            self.settings.setValue("canvas/workspace_width", rect.width())
            self.settings.setValue("canvas/workspace_height", rect.height())

    def set_canvas_rect(self, rect: QRectF):
        rect = QRectF(rect).normalized()
        rect.setWidth(max(self.MIN_SIZE, rect.width()))
        rect.setHeight(max(self.MIN_SIZE, rect.height()))
        self.prepareGeometryChange()
        self.setRect(rect)
        self.update_handles()
        scene = self.scene()
        if scene:
            scene.setSceneRect(rect.adjusted(-2000, -2000, 2000, 2000))
            scene.update()
        self.finish_resize()

    def set_chrome_visible(self, visible):
        self.setVisible(visible)
        for handle in self._handles:
            handle.setVisible(visible)
        self._info_tag.setVisible(visible)
        if not visible:
            self._readout.setVisible(False)

    def _update_size_readout(self, handle_index: int, show: bool):
        if handle_index < 0 or handle_index >= len(self._handles):
            return
        rect = self.rect()
        start = self._resize_start_rect if not self._resize_start_rect.isNull() else rect
        width = int(round(rect.width()))
        height = int(round(rect.height()))
        delta_w = width - int(round(start.width()))
        delta_h = height - int(round(start.height()))
        if delta_w and delta_h:
            delta_text = f"{delta_w:+d}px x {delta_h:+d}px"
        elif delta_w:
            delta_text = f"{delta_w:+d}px w"
        else:
            delta_text = f"{delta_h:+d}px h"
        readout = f"{width} x {height} ({delta_text})"
        if self._active_snap_label:
            readout += f" - Snap: {self._active_snap_label}"
        self._readout.set_readout(readout, handle_index)
        self._readout.setPos(self._handles[handle_index].pos())
        self._readout.setVisible(show)

    def _update_info_tag(self):
        rect = self.rect()
        width = int(round(rect.width()))
        height = int(round(rect.height()))
        self._info_tag.set_info(width, height, image_type="PNG", transparent=True)
        tag_x = rect.left()
        tag_y = rect.bottom() + 10
        self._info_tag.setPos(QPointF(tag_x, tag_y))

    def _snap_resize_rect(self, rect: QRectF, handle_index: int, modifiers=None,
                          probe_rect=None) -> QRectF:
        mods = _resize_modifiers(modifiers)
        if not mods["alt"]:
            self._active_snap_label = ""
            return rect

        probe = probe_rect or rect
        width, height, label = self._nearest_canvas_preset(probe.width(), probe.height())
        self._active_snap_label = label
        return self._rect_for_snapped_size(width, height, handle_index, centered=mods["centered"])

    def _nearest_canvas_preset(self, width: float, height: float):
        target_w = max(float(self.MIN_SIZE), float(width))
        target_h = max(float(self.MIN_SIZE), float(height))
        start = self._resize_start_rect.normalized()
        candidates = [
            ("", max(float(self.MIN_SIZE), start.width()), max(float(self.MIN_SIZE), start.height()))
        ]
        candidates.extend(self._canvas_size_presets())

        best_label, best_w, best_h = candidates[0]
        best_score = math.inf
        for label, preset_w, preset_h in candidates:
            score = math.hypot(target_w - preset_w, target_h - preset_h)
            if score < best_score:
                best_label, best_w, best_h = label, preset_w, preset_h
                best_score = score
        return best_w, best_h, best_label

    def _rect_for_snapped_size(self, width: float, height: float, handle_index: int,
                               centered: bool) -> QRectF:
        width = max(float(self.MIN_SIZE), float(width))
        height = max(float(self.MIN_SIZE), float(height))
        start = self._resize_start_rect.normalized()
        if centered:
            center = start.center()
            return QRectF(center.x() - width / 2.0, center.y() - height / 2.0, width, height)

        anchor_x = (
            start.right() if handle_index in HANDLE_LEFT
            else start.left() if handle_index in HANDLE_RIGHT
            else start.center().x()
        )
        anchor_y = (
            start.bottom() if handle_index in HANDLE_TOP
            else start.top() if handle_index in HANDLE_BOTTOM
            else start.center().y()
        )

        if handle_index in HANDLE_LEFT:
            left = anchor_x - width
        elif handle_index in HANDLE_RIGHT:
            left = anchor_x
        else:
            left = anchor_x - width / 2.0

        if handle_index in HANDLE_TOP:
            top = anchor_y - height
        elif handle_index in HANDLE_BOTTOM:
            top = anchor_y
        else:
            top = anchor_y - height / 2.0

        return QRectF(left, top, width, height)

    def _canvas_size_presets(self):
        presets = []
        current_screen = self._current_app_screen()
        if current_screen:
            width, height = self._screen_pixel_size(current_screen)
            presets.append((self._screen_preset_label("Current Monitor", current_screen), width, height))

        for index, screen in enumerate(QApplication.screens(), 1):
            if current_screen and screen == current_screen:
                continue
            width, height = self._screen_pixel_size(screen)
            presets.append((self._screen_preset_label(f"Monitor {index}", screen), width, height))

        presets.extend(CANVAS_STANDARD_SIZE_PRESETS)
        return self._dedup_canvas_presets(presets)

    def _current_app_screen(self):
        scene = self.scene()
        if scene:
            for view in scene.views():
                window = view.window().windowHandle()
                if window and window.screen():
                    return window.screen()
                if hasattr(view, "screen") and view.screen():
                    return view.screen()
        return QApplication.primaryScreen()

    def _screen_pixel_size(self, screen):
        geometry = screen.geometry()
        scale = max(1.0, float(screen.devicePixelRatio()))
        width = int(round(geometry.width() * scale))
        height = int(round(geometry.height() * scale))
        return max(self.MIN_SIZE, width), max(self.MIN_SIZE, height)

    def _screen_preset_label(self, prefix: str, screen) -> str:
        name = screen.name() or ""
        return f"{prefix}: {name}" if name else prefix

    def _dedup_canvas_presets(self, presets):
        ordered = []
        by_size = {}
        for label, width, height in presets:
            width = int(round(width))
            height = int(round(height))
            if width < self.MIN_SIZE or height < self.MIN_SIZE:
                continue
            key = (width, height)
            if key not in by_size:
                by_size[key] = [label]
                ordered.append(key)
            elif label and label not in by_size[key]:
                by_size[key].append(label)

        result = []
        for width, height in ordered:
            labels = [label for label in by_size[(width, height)] if label]
            label = labels[0] if labels else ""
            if len(labels) > 1:
                label = f"{label} + {len(labels) - 1} more"
            result.append((self._short_preset_label(label), width, height))
        return result

    def _short_preset_label(self, label: str) -> str:
        if len(label) <= 42:
            return label
        return label[:39].rstrip() + "..."

    def ensure_contains(self, scene_rect: QRectF):
        if scene_rect.isEmpty():
            return
        padded = QRectF(scene_rect).adjusted(
            -self.PADDING, -self.PADDING, self.PADDING, self.PADDING
        )
        current = QRectF(self.rect())
        expanded = current.united(padded)
        if expanded == current:
            return
        self.prepareGeometryChange()
        self.setRect(expanded)
        self.update_handles()
        scene = self.scene()
        if scene:
            scene.setSceneRect(expanded.adjusted(-2000, -2000, 2000, 2000))
            scene.update()
        self.finish_resize()


class SelectionMagnifier(QWidget):
    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self._view_pos = QPoint()
        self._scene_pos = QPointF()
        self._diameter = 132
        self._source_radius = 24
        self.setFixedSize(self._diameter, self._diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def show_at(self, view_pos, scene_pos):
        self._view_pos = QPoint(view_pos)
        self._scene_pos = QPointF(scene_pos)
        margin = 18
        x = view_pos.x() + margin
        y = view_pos.y() + margin
        if x + self.width() > self.parentWidget().width():
            x = view_pos.x() - self.width() - margin
        if y + self.height() > self.parentWidget().height():
            y = view_pos.y() - self.height() - margin
        self.move(max(0, x), max(0, y))
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addEllipse(outer)
        painter.setClipPath(path)
        source = QRectF(
            self._scene_pos.x() - self._source_radius,
            self._scene_pos.y() - self._source_radius,
            self._source_radius * 2,
            self._source_radius * 2,
        )
        self.view.scene().render(painter, outer, source)
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#111827"), 3))
        painter.drawEllipse(outer)
        painter.setPen(QPen(QColor("#f6c21a"), 3))
        painter.drawLine(QPointF(outer.center().x(), 8), QPointF(outer.center().x(), self.height() - 8))
        painter.drawLine(QPointF(8, outer.center().y()), QPointF(self.width() - 8, outer.center().y()))
        painter.setPen(QPen(QColor("#111827"), 1))
        painter.drawLine(QPointF(outer.center().x(), 8), QPointF(outer.center().x(), self.height() - 8))
        painter.drawLine(QPointF(8, outer.center().y()), QPointF(self.width() - 8, outer.center().y()))
        painter.end()


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

    def mouseDoubleClickEvent(self, event):
        scene = self.scene()
        if scene:
            views = scene.views()
            if views and hasattr(views[0], '_add_text_inside_item'):
                if views[0]._add_text_inside_item(self):
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

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

    def applyPixmapEdit(self, pixmap: QPixmap):
        pixmap = self._ensure_argb_pixmap(pixmap)
        self.setPixmap(pixmap)
        self.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
        self.updateImageBytes()
        if self.handles:
            self.handles.update_handles()

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
    def __init__(self, renderer, svg_bytes=None, source_path=None):
        super().__init__()
        self.setSharedRenderer(renderer)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.renderer = renderer
        self.svg_bytes = bytes(svg_bytes) if svg_bytes else None
        self.source_path = str(source_path) if source_path else None
        if not self.svg_bytes and self.source_path and os.path.isfile(self.source_path):
            try:
                self.svg_bytes = Path(self.source_path).read_bytes()
            except Exception:
                self.svg_bytes = None
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

    def mouseDoubleClickEvent(self, event):
        scene = self.scene()
        if scene:
            views = scene.views()
            if views and hasattr(views[0], '_add_text_inside_item'):
                if views[0]._add_text_inside_item(self):
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)


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


class CanvasBlurItem(ContextMenuForwarder, QGraphicsPixmapItem):
    """Pixel-snapshot redaction: blur + darken baked into the displayed pixmap.

    `strength` (0–100) drives BOTH the Gaussian radius AND a translucent
    darkening overlay, so higher values reliably make the underlying text
    less recoverable instead of getting washed out by edge dilution at
    very large blur radii.

    Resizes non-uniformly: corner handles stretch width and height
    independently; edge handles stretch only one dimension.
    """
    supports_rotation_handles = True
    DEFAULT_STRENGTH = 50  # 0-100
    MIN_DIM = 8

    def __init__(self, source_pixmap: QPixmap, strength: int | None = None,
                 blur_radius: float | None = None):
        # The baked output pixmap (blur + darken) is what the scene renders.
        # _source is the pristine snapshot we re-bake from on resize/strength change.
        self._source = QPixmap(source_pixmap)
        if strength is None and blur_radius is not None:
            # Back-compat: map an old radius value to a strength setting.
            strength = max(1, min(100, int(blur_radius)))
        self._strength = int(strength) if strength is not None else self.DEFAULT_STRENGTH
        baked = self._bake(self._source, self._strength)
        super().__init__(baked)
        rect = self.boundingRect()
        self.setTransformOriginPoint(rect.width() / 2, rect.height() / 2)
        self._rs_idx = None
        self._rs_anchor_scene = QPointF(0, 0)

    @staticmethod
    def _bake(source: QPixmap, strength: int) -> QPixmap:
        """Apply Gaussian blur and a strength-scaled darkening pass."""
        s = max(1, min(100, int(strength)))
        # Radius 4 .. 36 across strength 1..100 — small enough to avoid edge
        # dilution that washes out very large radii on small snapshots.
        radius = 4 + (s / 100.0) * 32.0
        # Darken alpha 30 (~12%) at strength=1, 230 (~90%) at strength=100.
        dark_alpha = int(30 + (s / 100.0) * 200)

        # Step 1 — bake the Gaussian blur into a flat pixmap via a one-shot scene.
        bp = QGraphicsPixmapItem(source)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(radius)
        effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        bp.setGraphicsEffect(effect)
        tmp_scene = QGraphicsScene()
        tmp_scene.addItem(bp)
        baked = QPixmap(source.size())
        baked.fill(QColor(0, 0, 0, 0))
        painter = QPainter(baked)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        tmp_scene.render(
            painter,
            QRectF(0, 0, baked.width(), baked.height()),
            QRectF(0, 0, source.width(), source.height()),
        )
        # Step 2 — overlay a dark wash (alpha-only) so high strength = unreadable.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        painter.fillRect(baked.rect(), QColor(20, 20, 20, dark_alpha))
        painter.end()
        return baked

    def setStrength(self, strength: int):
        self._strength = max(1, min(100, int(strength)))
        # Heal any legacy item that still has the old QGraphicsBlurEffect
        # attached — its boundingRect is inflated by the effect halo, which
        # would make the pixmap grow on every strength change.
        if self.graphicsEffect() is not None:
            self.setGraphicsEffect(None)
        baked = self._bake(self._source, self._strength)
        # Use the *pixmap* size as the source of truth — never boundingRect,
        # which can include effect-extended margins.
        cur = self.pixmap()
        cur_w = max(self.MIN_DIM, cur.width()) if not cur.isNull() else baked.width()
        cur_h = max(self.MIN_DIM, cur.height()) if not cur.isNull() else baked.height()
        if (cur_w, cur_h) != (baked.width(), baked.height()):
            baked = baked.scaled(
                cur_w, cur_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.prepareGeometryChange()
        self.setPixmap(baked)
        self.setTransformOriginPoint(cur_w / 2, cur_h / 2)
        self.update()
        if getattr(self, "handles", None):
            self.handles.update_handles()

    def strength(self) -> int:
        return self._strength

    # Back-compat shims for callers that knew the old API.
    def setBlurRadius(self, radius: float):
        self.setStrength(int(radius))

    def blurRadius(self) -> float:
        return float(self._strength)

    # ------------------------------------------------------------------
    # Non-uniform resize via the SelectionHandles delegate protocol.
    # Handle indices: 0=TL, 1=TR, 2=BR, 3=BL, 4=Top, 5=Right, 6=Bottom, 7=Left
    # ------------------------------------------------------------------
    def _local_anchor(self, idx: int, w: float, h: float) -> QPointF:
        anchors = {
            0: QPointF(w, h), 1: QPointF(0, h), 2: QPointF(0, 0), 3: QPointF(w, 0),
            4: QPointF(0, h), 5: QPointF(0, 0), 6: QPointF(0, 0), 7: QPointF(w, 0),
        }
        return anchors[idx]

    def handle_resize_press(self, handle, scene_pos):
        idx = handle.handle_index
        # Strip legacy effect halo before measuring.
        if self.graphicsEffect() is not None:
            self.setGraphicsEffect(None)
        # Pixmap size is the actual content size; boundingRect can be inflated
        # by a stale graphics effect on legacy items.
        pix = self.pixmap()
        w = pix.width() if not pix.isNull() else self.boundingRect().width()
        h = pix.height() if not pix.isNull() else self.boundingRect().height()
        self._rs_idx = idx
        self._rs_start_w = w
        self._rs_start_h = h
        self._rs_start_rect = QRectF(self.pos(), QSizeF(w, h))
        self._rs_anchor_scene = self.mapToScene(
            self._local_anchor(idx, self._rs_start_w, self._rs_start_h)
        )

    def handle_resize_drag(self, handle, scene_pos):
        if self._rs_idx is None:
            return
        idx = self._rs_idx
        rect = _rect_from_resize_drag(
            self._rs_start_rect, idx, scene_pos,
            self.MIN_DIM, self.MIN_DIM,
        )
        new_w = rect.width()
        new_h = rect.height()
        # Bake fresh from the pristine source so the pixmap can never grow
        # past the user's actual drag.
        baked = self._bake(self._source, self._strength)
        scaled = baked.scaled(
            int(new_w), int(new_h),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.prepareGeometryChange()
        self.setPixmap(scaled)
        self.setPos(rect.topLeft())
        # Keep the rotation pivot at the new center.
        self.setTransformOriginPoint(new_w / 2, new_h / 2)
        if getattr(self, "handles", None):
            self.handles.update_handles()

    def handle_resize_release(self, handle, scene_pos):
        self._rs_idx = None

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasHighlightItem(ContextMenuForwarder, QGraphicsRectItem):
    """Translucent rectangle used to highlight regions of an image like a marker.

    Like the Blur item, it resizes non-uniformly (edge handles stretch one
    axis, corner handles stretch both). Right-click to switch color.
    """
    supports_rotation_handles = True
    DEFAULT_COLOR = QColor(255, 235, 59, 110)  # marker yellow at ~43% alpha
    MIN_DIM = 8

    def __init__(self, rect: QRectF, color: QColor | None = None):
        super().__init__(rect)
        self._color = color or self.DEFAULT_COLOR
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(self._color))
        self.setTransformOriginPoint(rect.center())
        self._rs_idx = None

    def setHighlightColor(self, color: QColor):
        self._color = color
        self.setBrush(QBrush(color))
        self.update()

    def highlightColor(self) -> QColor:
        return self._color

    # Same non-uniform resize protocol as CanvasBlurItem — edges = one-axis,
    # corners = both axes independently.
    def _local_anchor(self, idx: int, w: float, h: float) -> QPointF:
        anchors = {
            0: QPointF(w, h), 1: QPointF(0, h), 2: QPointF(0, 0), 3: QPointF(w, 0),
            4: QPointF(0, h), 5: QPointF(0, 0), 6: QPointF(0, 0), 7: QPointF(w, 0),
        }
        return anchors[idx]

    def handle_resize_press(self, handle, scene_pos):
        idx = handle.handle_index
        rect = self.rect()
        self._rs_idx = idx
        self._rs_start_w = rect.width()
        self._rs_start_h = rect.height()
        self._rs_start_rect = QRectF(self.pos(), QSizeF(self._rs_start_w, self._rs_start_h))
        self._rs_anchor_scene = self.mapToScene(
            self.rect().topLeft() + self._local_anchor(idx, self._rs_start_w, self._rs_start_h)
        )

    def handle_resize_drag(self, handle, scene_pos):
        if self._rs_idx is None:
            return
        idx = self._rs_idx
        resized = _rect_from_resize_drag(
            self._rs_start_rect, idx, scene_pos,
            self.MIN_DIM, self.MIN_DIM,
        )
        new_w = resized.width()
        new_h = resized.height()
        self.prepareGeometryChange()
        self.setRect(QRectF(0, 0, new_w, new_h))
        self.setPos(resized.topLeft())
        self.setTransformOriginPoint(new_w / 2, new_h / 2)
        if getattr(self, "handles", None):
            self.handles.update_handles()

    def handle_resize_release(self, handle, scene_pos):
        self._rs_idx = None

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


class CanvasBorderItem(ContextMenuForwarder, QGraphicsRectItem):
    """A rectangle styled as a decorative border around content beneath it."""
    supports_rotation_handles = True
    DEFAULT_COLOR = QColor("#1f5f9e")
    DEFAULT_THICKNESS = 8

    def __init__(self, rect: QRectF, color: QColor | None = None,
                 thickness: int | None = None):
        super().__init__(rect)
        c = color or self.DEFAULT_COLOR
        t = thickness if thickness is not None else self.DEFAULT_THICKNESS
        pen = QPen(c, t)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setTransformOriginPoint(rect.center())

    def setBorderColor(self, color: QColor):
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)

    def setBorderThickness(self, thickness: int):
        pen = self.pen()
        pen.setWidth(int(thickness))
        self.setPen(pen)

    def contextMenuEvent(self, event):
        if self._forward_context_menu(event):
            return
        super().contextMenuEvent(event)


add_handles_support(CanvasRectItem)
add_handles_support(CanvasEllipseItem)
add_handles_support(CanvasTextItem)
add_handles_support(CanvasArrowItem)
add_handles_support(CanvasStepItem)
add_handles_support(CanvasBlurItem)
add_handles_support(CanvasBorderItem)
add_handles_support(CanvasHighlightItem)


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
    MIN_ZOOM = 0.02
    MAX_ZOOM = 100.0
    WHEEL_ZOOM_BASE = 1.10

    def __init__(self, scene, artifact_list, main_window):
        super().__init__(scene)
        self.artifact_list = artifact_list
        self.main_window = main_window
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QBrush(QColor("#d7dde5")))
        self.viewport().setAutoFillBackground(True)
        self.viewport().setStyleSheet("background-color: #d7dde5;")
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
        self._cutout_overlay = None
        self._cutout_start_scene = None
        self._cutout_target_item = None
        self._cutout_axis = None
        self._cutout_add_space = False
        self._pending_text_edit_item = None
        self._selection_magnifier = SelectionMagnifier(self)
        self._pixel_grid_enabled = self.main_window.settings.value(
            "view/pixel_grid", False, type=bool
        )
        self._zoom_with_scroll_wheel = self.main_window.settings.value(
            "canvas/zoom_with_scroll_wheel", True, type=bool
        )
        self._animated_zoom_enabled = self.main_window.settings.value(
            "canvas/animated_zoom", True, type=bool
        )
        self._zoom_sensitivity = float(self.main_window.settings.value(
            "canvas/zoom_sensitivity", 100,
        )) / 100.0
        self._zoom_target_factor = self._zoom_factor
        self._smooth_zoom_view_pos = QPoint()
        self._smooth_zoom_scene_pos = QPointF()
        self._smooth_zoom_timer = QTimer(self)
        self._smooth_zoom_timer.setInterval(16)
        self._smooth_zoom_timer.timeout.connect(self._apply_scheduled_zoom)
        bg_name = self.main_window.settings.value("view/background_color", "#d7dde5")
        self.set_view_background(QColor(str(bg_name)))

    def _set_blur_strength(self, blur_items):
        """Live slider to dial blur strength across selected blur items."""
        if not blur_items:
            return
        from PyQt6.QtWidgets import QSlider, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox

        original = [(it, it.strength()) for it in blur_items]
        dialog = QDialog(self)
        dialog.setWindowTitle("Blur Strength")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "Drag the slider — higher = darker / less recoverable.\n"
            "0 leaves the snapshot untouched, 100 fully redacts it."
        ))
        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 100)
        slider.setValue(int(blur_items[0].strength()))
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(10)
        value_lbl = QLabel(f"{slider.value()}")
        value_lbl.setFixedWidth(34)
        row.addWidget(slider)
        row.addWidget(value_lbl)
        layout.addLayout(row)

        def apply_value(v):
            value_lbl.setText(str(v))
            for it in blur_items:
                it.setStrength(v)
        slider.valueChanged.connect(apply_value)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            for it, prev in original:
                it.setStrength(prev)

    def _pick_highlight_color(self, hl_items):
        """Pick a custom color (alpha-aware) for selected highlight items."""
        if not hl_items:
            return
        from PyQt6.QtWidgets import QColorDialog
        current = hl_items[0].highlightColor()
        chosen = QColorDialog.getColor(
            current, self, "Highlight color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if chosen.isValid():
            for it in hl_items:
                it.setHighlightColor(chosen)

    def _snapshot_scene_rect(self, scene_rect: QRectF, exclude_item=None) -> QPixmap:
        """Render the scene contents inside scene_rect into a QPixmap.

        exclude_item lets the Blur tool hide its own preview rectangle so the
        resulting snapshot only contains content beneath the redaction.
        """
        w = max(1, int(scene_rect.width()))
        h = max(1, int(scene_rect.height()))
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor(0, 0, 0, 0))
        was_visible = None
        if exclude_item is not None:
            was_visible = exclude_item.isVisible()
            exclude_item.setVisible(False)
        try:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = QRectF(0, 0, w, h)
            self.scene().render(painter, target, scene_rect)
            painter.end()
        finally:
            if exclude_item is not None and was_visible is not None:
                exclude_item.setVisible(was_visible)
        return pixmap

    def _abort_drag_preview(self):
        """Drop any partially-drawn preview rect / arrow so it doesn't linger."""
        if self._drawing_item is not None:
            try:
                if self._drawing_item.scene() is self.scene():
                    self.scene().removeItem(self._drawing_item)
            except Exception:
                pass
            self._drawing_item = None
        self._start_pos = None

    def set_tool(self, tool):
        # Don't strand an in-progress drag when the user clicks another tool.
        self._abort_drag_preview()
        self._selection_magnifier.hide()
        if self.current_tool == ToolType.SELECTION and tool != ToolType.SELECTION:
            self._cancel_selection_mode()
        if self.current_tool == ToolType.CUTOUT and tool != ToolType.CUTOUT:
            self._cancel_cutout_mode()
        self.current_tool = tool
        if tool == ToolType.SELECT:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        if tool == ToolType.CUTOUT:
            self._show_cutout_status()
        self._apply_cursor()

    def set_cutout_add_mode(self, enabled: bool):
        self._cutout_add_space = bool(enabled)
        if self.current_tool == ToolType.CUTOUT:
            self._show_cutout_status()

    def fit_all_items(self):
        """Zoom and pan to fit all items in the scene."""
        self._stop_smooth_zoom()
        rect = self._content_or_canvas_rect()
        if rect.isEmpty():
            return
        rect.adjust(-50, -50, 50, 50)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # Update internal zoom factor to match
        transform = self.transform()
        self._zoom_factor = transform.m11()

    def _content_or_canvas_rect(self):
        items = [
            item for item in self.scene().items()
            if item.isVisible()
            and item.boundingRect().isValid()
            and not getattr(item, "is_canvas_chrome", False)
        ]
        if items:
            rect = items[0].sceneBoundingRect()
            for item in items[1:]:
                rect = rect.united(item.sceneBoundingRect())
            return rect
        canvas = getattr(self.main_window, "canvas_bounds_item", None)
        if canvas:
            return QRectF(canvas.rect())
        return QRectF()

    def zoom_to_fit(self):
        self.fit_all_items()

    def _viewport_center(self):
        return self.viewport().rect().center()

    def _current_view_scale(self):
        scale = self.transform().m11()
        return scale if scale > 0 else self._zoom_factor

    def _clamped_zoom_factor(self, requested_factor):
        current = self._current_view_scale()
        target = max(self.MIN_ZOOM, min(self.MAX_ZOOM, current * requested_factor))
        if current <= 0:
            return 1.0
        return target / current

    def _apply_zoom_factor(self, factor, view_pos=None, update_target=True, anchor_scene_pos=None):
        factor = self._clamped_zoom_factor(factor)
        if abs(factor - 1.0) < 0.000001:
            self._zoom_factor = self._current_view_scale()
            return
        if view_pos is None:
            view_pos = self._viewport_center()
        if hasattr(view_pos, "toPoint"):
            view_pos = view_pos.toPoint()

        if anchor_scene_pos is None:
            anchor_scene_pos = self.mapToScene(view_pos)
        old_anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.scale(factor, factor)
        self.setTransformationAnchor(old_anchor)
        after = self.mapToScene(view_pos)
        delta = after - anchor_scene_pos
        self.centerOn(self.mapToScene(self._viewport_center()) - delta)
        self._zoom_factor = self._current_view_scale()
        if update_target:
            self._zoom_target_factor = self._zoom_factor

    def zoom_by(self, factor, view_pos=None):
        self._stop_smooth_zoom()
        self._apply_zoom_factor(factor, view_pos)

    def zoom_in(self):
        self.zoom_by(self.WHEEL_ZOOM_BASE)

    def zoom_out(self):
        self.zoom_by(1.0 / self.WHEEL_ZOOM_BASE)

    def actual_size(self):
        self._stop_smooth_zoom()
        self._zoom_factor = 1.0
        self.setTransform(QTransform())
        self._zoom_target_factor = self._zoom_factor

    def set_pixel_grid_enabled(self, enabled: bool):
        self._pixel_grid_enabled = bool(enabled)
        self.viewport().update()

    def set_view_background(self, color: QColor):
        self._background_color = QColor(color)
        self.setBackgroundBrush(QBrush(self._background_color))
        self.viewport().setStyleSheet(f"background-color: {self._background_color.name()};")

    def set_zoom_with_scroll_wheel(self, enabled: bool):
        self._zoom_with_scroll_wheel = bool(enabled)

    def set_animated_zoom_enabled(self, enabled: bool):
        self._animated_zoom_enabled = bool(enabled)
        if not self._animated_zoom_enabled:
            self._stop_smooth_zoom()

    def set_zoom_sensitivity(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 100.0
        self._zoom_sensitivity = max(0.25, min(2.0, value / 100.0))

    def _stop_smooth_zoom(self):
        if hasattr(self, "_smooth_zoom_timer"):
            self._smooth_zoom_timer.stop()
        self._zoom_factor = self._current_view_scale()
        self._zoom_target_factor = self._zoom_factor

    def fit_item(self, item):
        """Zoom and pan to fit a specific item."""
        self._stop_smooth_zoom()
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
        should_zoom = (
            self._zoom_with_scroll_wheel or
            bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        )
        if should_zoom:
            self._handle_zoom_wheel(event)
            event.accept()
            return
        super().wheelEvent(event)

    def _wheel_steps(self, event):
        angle_y = event.angleDelta().y()
        if angle_y:
            return angle_y / 120.0
        pixel_y = event.pixelDelta().y()
        if pixel_y:
            return pixel_y / 40.0
        return 0.0

    def _handle_zoom_wheel(self, event):
        steps = self._wheel_steps(event)
        if steps == 0:
            return
        view_pos = event.position().toPoint()
        factor = self.WHEEL_ZOOM_BASE ** (steps * self._zoom_sensitivity)
        if not self._animated_zoom_enabled:
            self.zoom_by(factor, view_pos)
            return
        current = self._current_view_scale()
        if self._smooth_zoom_timer.isActive():
            current_direction = self._zoom_target_factor - current
            incoming_direction = (current * factor) - current
            if current_direction and incoming_direction and (
                current_direction > 0
            ) != (incoming_direction > 0):
                self._zoom_target_factor = current
        else:
            self._zoom_target_factor = current
        self._zoom_target_factor = max(
            self.MIN_ZOOM,
            min(self.MAX_ZOOM, self._zoom_target_factor * factor),
        )
        self._smooth_zoom_view_pos = QPoint(view_pos)
        self._smooth_zoom_scene_pos = self.mapToScene(view_pos)
        if not self._smooth_zoom_timer.isActive():
            self._smooth_zoom_timer.start()

    def _apply_scheduled_zoom(self):
        current = self._current_view_scale()
        if current <= 0:
            self._stop_smooth_zoom()
            return
        remaining = math.log(self._zoom_target_factor / current)
        if abs(remaining) < 0.001:
            self._smooth_zoom_timer.stop()
            self._zoom_factor = current
            return
        tick = max(-0.035, min(0.035, remaining * 0.35))
        if abs(tick) < 0.002:
            tick = remaining
        self._apply_zoom_factor(
            math.exp(tick),
            self._smooth_zoom_view_pos,
            update_target=False,
            anchor_scene_pos=self._smooth_zoom_scene_pos,
        )
        if self._zoom_factor <= self.MIN_ZOOM or self._zoom_factor >= self.MAX_ZOOM:
            self._stop_smooth_zoom()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self.main_window, "_shrink_to_fit_enabled", False):
            QTimer.singleShot(0, self.zoom_to_fit)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if not self._pixel_grid_enabled or self._zoom_factor < 6.0:
            return
        left = math.floor(rect.left())
        right = math.ceil(rect.right())
        top = math.floor(rect.top())
        bottom = math.ceil(rect.bottom())
        if (right - left) > 2500 or (bottom - top) > 2500:
            return
        painter.save()
        painter.setPen(QPen(QColor(148, 163, 184, 110), 0))
        for x in range(left, right + 1):
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        for y in range(top, bottom + 1):
            painter.drawLine(QPointF(left, y), QPointF(right, y))
        painter.restore()

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

        if isinstance(clicked_item, (ResizeHandle, RotateHandle, CanvasResizeHandle)):
            super().mousePressEvent(event)
            return

        if self.current_tool == ToolType.SELECTION:
            self._handle_selection_press(event, scene_pos, clicked_item)
            return
        if self.current_tool == ToolType.CUTOUT:
            self._handle_cutout_press(event, scene_pos)
            return
        if self.current_tool == ToolType.SELECT and event.button() == Qt.MouseButton.LeftButton:
            if self._handle_object_select_press(event, clicked_item):
                return

        if self.current_tool in (ToolType.RECTANGLE, ToolType.ELLIPSE,
                                 ToolType.BLUR, ToolType.BORDER,
                                 ToolType.HIGHLIGHT):
            self._start_pos = scene_pos
            if self.current_tool == ToolType.RECTANGLE:
                self._drawing_item = CanvasRectItem(QRectF(scene_pos, scene_pos))
                self._drawing_item.setPen(QPen(Qt.GlobalColor.black, 2))
                self._drawing_item.setBrush(QBrush(QColor(100, 100, 255, 100)))
            elif self.current_tool == ToolType.ELLIPSE:
                self._drawing_item = CanvasEllipseItem(QRectF(scene_pos, scene_pos))
                self._drawing_item.setPen(QPen(Qt.GlobalColor.black, 2))
                self._drawing_item.setBrush(QBrush(QColor(100, 100, 255, 100)))
            elif self.current_tool == ToolType.BLUR:
                # Live-preview as a translucent black rect — snapshot baked on release.
                self._drawing_item = CanvasRectItem(QRectF(scene_pos, scene_pos))
                self._drawing_item.setPen(QPen(QColor(0, 0, 0, 180), 1, Qt.PenStyle.DashLine))
                self._drawing_item.setBrush(QBrush(QColor(0, 0, 0, 60)))
            elif self.current_tool == ToolType.HIGHLIGHT:
                self._drawing_item = CanvasHighlightItem(QRectF(scene_pos, scene_pos))
            else:  # BORDER
                self._drawing_item = CanvasBorderItem(QRectF(scene_pos, scene_pos))
            self.scene().addItem(self._drawing_item)
            return
        elif self.current_tool == ToolType.ARROW:
            self._start_pos = scene_pos
            self._drawing_item = CanvasArrowItem(scene_pos, scene_pos)
            self.scene().addItem(self._drawing_item)
            return
        elif self.current_tool == ToolType.STEP:
            # Find next step number based on existing CanvasStepItems.
            n = 1
            for it in self.scene().items():
                if isinstance(it, CanvasStepItem):
                    n = max(n, it.number() + 1)
            step = CanvasStepItem(n, scene_pos)
            step.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            step.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            step.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            self.scene().addItem(step)
            self.itemAdded.emit(step)
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
            self.scene().clearSelection()
            text_item.setSelected(True)
            self._pending_text_edit_item = text_item
            QTimer.singleShot(0, self._activate_pending_text_edit)
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
                self._selection_magnifier.show_at(event.pos(), scene_pos)
                return
            if self._selection_drop_active:
                self._selection_drop_pos = scene_pos
                return
            super().mouseMoveEvent(event)
            return
        if self.current_tool == ToolType.CUTOUT:
            if self._cutout_start_scene is not None:
                self._update_cutout_preview(scene_pos, event.modifiers())
                return
            super().mouseMoveEvent(event)
            return

        if self._drawing_item:
            if isinstance(self._drawing_item, CanvasArrowItem):
                self._drawing_item.setEndpoints(self._start_pos, scene_pos)
            else:
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
                self._selection_magnifier.hide()
                if self._selection_host and self._selection_host.hasSelectionOverlay():
                    self._selection_host.lockSelectionOverlay()
                    self._selection_host.activateSelectionOverlay()
                self._apply_cursor()
                return
            if self._selection_drop_active:
                target_pos = self._selection_drop_pos or scene_pos
                self._selection_drop_active = False
                self._selection_drop_pos = None
                self._selection_magnifier.hide()
                self._finalize_selection(target_pos)
                self._apply_cursor()
                return
            super().mouseReleaseEvent(event)
            return
        if self.current_tool == ToolType.CUTOUT:
            if self._cutout_start_scene is not None:
                self._apply_cutout(scene_pos, event.modifiers())
                return
            super().mouseReleaseEvent(event)
            return

        if self._drawing_item:
            # Special-case BLUR: replace the temporary rect with a baked snapshot.
            if self.current_tool == ToolType.BLUR and isinstance(self._drawing_item, CanvasRectItem):
                rect = self._drawing_item.rect().normalized()
                if rect.width() < 4 or rect.height() < 4:
                    self.scene().removeItem(self._drawing_item)
                    self._drawing_item = None
                    self._start_pos = None
                    return
                snap = self._snapshot_scene_rect(rect, exclude_item=self._drawing_item)
                self.scene().removeItem(self._drawing_item)
                blur_item = CanvasBlurItem(snap)
                blur_item.setPos(rect.topLeft())
                blur_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                blur_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                blur_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
                self.scene().addItem(blur_item)
                self.itemAdded.emit(blur_item)
                self._drawing_item = None
                self._start_pos = None
                return

            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._drawing_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            if isinstance(self._drawing_item, CanvasArrowItem):
                bbox = self._drawing_item.boundingRect()
                self._drawing_item.setTransformOriginPoint(bbox.center())
            else:
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

    def _show_cutout_status(self):
        mode = "add space" if self._cutout_add_space else "cut out"
        self.main_window._status_bar.showMessage(
            f"Cut Out: drag vertically for a horizontal band, horizontally for a vertical band ({mode}; Alt inverts)",
            6000,
        )

    def _selected_cutout_raster(self):
        raster_items = [
            item for item in self.main_window._selected_layer_items()
            if isinstance(item, RasterItem) and item.scene() is self.scene()
        ]
        return raster_items[0] if len(raster_items) == 1 else None

    def _cutout_target_bounds(self):
        if self._cutout_target_item:
            return self._cutout_target_item.sceneBoundingRect()
        canvas = getattr(self.main_window, "canvas_bounds_item", None)
        return QRectF(canvas.rect()) if canvas else QRectF()

    def _handle_cutout_press(self, event, scene_pos):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._cutout_start_scene = QPointF(scene_pos)
        self._cutout_target_item = self._selected_cutout_raster()
        self._cutout_axis = None
        if self._cutout_overlay and self._cutout_overlay.scene():
            self._cutout_overlay.scene().removeItem(self._cutout_overlay)
        self._cutout_overlay = CutoutOverlay()
        self.scene().addItem(self._cutout_overlay)
        self._update_cutout_preview(scene_pos, event.modifiers())
        event.accept()

    def _cutout_axis_from_drag(self, scene_pos):
        if self._cutout_start_scene is None:
            return "horizontal"
        if self._cutout_target_item:
            start = self._cutout_target_item.mapFromScene(self._cutout_start_scene)
            current = self._cutout_target_item.mapFromScene(scene_pos)
            dx = abs(current.x() - start.x())
            dy = abs(current.y() - start.y())
        else:
            dx = abs(scene_pos.x() - self._cutout_start_scene.x())
            dy = abs(scene_pos.y() - self._cutout_start_scene.y())
        return "horizontal" if dy >= dx else "vertical"

    def _cutout_scene_rect(self, scene_pos, axis):
        target = self._cutout_target_bounds()
        if target.isEmpty() or self._cutout_start_scene is None:
            return QRectF(scene_pos, scene_pos)

        if self._cutout_target_item:
            item = self._cutout_target_item
            start_local = item.mapFromScene(self._cutout_start_scene)
            current_local = item.mapFromScene(scene_pos)
            pix = item.pixmap()
            if axis == "horizontal":
                y1, y2 = sorted((start_local.y(), current_local.y()))
                y1 = max(0.0, min(float(pix.height()), y1))
                y2 = max(0.0, min(float(pix.height()), y2))
                return item.mapRectToScene(QRectF(0, y1, pix.width(), max(0.0, y2 - y1)))
            x1, x2 = sorted((start_local.x(), current_local.x()))
            x1 = max(0.0, min(float(pix.width()), x1))
            x2 = max(0.0, min(float(pix.width()), x2))
            return item.mapRectToScene(QRectF(x1, 0, max(0.0, x2 - x1), pix.height()))

        if axis == "horizontal":
            y1, y2 = sorted((self._cutout_start_scene.y(), scene_pos.y()))
            y1 = max(target.top(), min(target.bottom(), y1))
            y2 = max(target.top(), min(target.bottom(), y2))
            return QRectF(target.left(), y1, target.width(), max(0.0, y2 - y1))
        x1, x2 = sorted((self._cutout_start_scene.x(), scene_pos.x()))
        x1 = max(target.left(), min(target.right(), x1))
        x2 = max(target.left(), min(target.right(), x2))
        return QRectF(x1, target.top(), max(0.0, x2 - x1), target.height())

    def _update_cutout_preview(self, scene_pos, modifiers=None):
        if not self._cutout_overlay:
            return
        add_space = bool(self._cutout_add_space or (modifiers and modifiers & Qt.KeyboardModifier.AltModifier))
        axis = self._cutout_axis or self._cutout_axis_from_drag(scene_pos)
        self._cutout_axis = axis
        self._cutout_overlay.set_preview(self._cutout_scene_rect(scene_pos, axis), axis, add_space)

    def _apply_cutout(self, scene_pos, modifiers=None):
        add_space = bool(self._cutout_add_space or (modifiers and modifiers & Qt.KeyboardModifier.AltModifier))
        axis = self._cutout_axis or self._cutout_axis_from_drag(scene_pos)
        if self._cutout_target_item:
            changed = self._apply_raster_cutout(self._cutout_target_item, scene_pos, axis, add_space)
        else:
            changed = self._apply_canvas_cutout(scene_pos, axis, add_space)
        self._clear_cutout_overlay(reset_mode=not changed)
        self._cutout_start_scene = None
        self._cutout_target_item = None
        self._cutout_axis = None
        if not changed:
            self.main_window._status_bar.showMessage("Cut Out canceled: drag at least 1 pixel", 3000)
        self._apply_cursor()

    @staticmethod
    def _cutout_pixmap(pixmap: QPixmap, axis: str, start_value: float, end_value: float, add_space: bool):
        source = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        width = source.width()
        height = source.height()
        limit = height if axis == "horizontal" else width
        start = int(round(min(start_value, end_value)))
        end = int(round(max(start_value, end_value)))
        start = max(0, min(limit, start))
        end = max(0, min(limit, end))
        amount = end - start
        if amount < 1:
            return None, 0
        if not add_space and amount >= limit:
            return None, 0

        if axis == "horizontal":
            new_height = height + amount if add_space else height - amount
            target = QImage(width, new_height, QImage.Format.Format_ARGB32)
            target.fill(Qt.GlobalColor.transparent)
            painter = QPainter(target)
            if start > 0:
                painter.drawImage(0, 0, source.copy(0, 0, width, start))
            if add_space:
                if start < height:
                    painter.drawImage(0, start + amount, source.copy(0, start, width, height - start))
            elif end < height:
                painter.drawImage(0, start, source.copy(0, end, width, height - end))
            painter.end()
        else:
            new_width = width + amount if add_space else width - amount
            target = QImage(new_width, height, QImage.Format.Format_ARGB32)
            target.fill(Qt.GlobalColor.transparent)
            painter = QPainter(target)
            if start > 0:
                painter.drawImage(0, 0, source.copy(0, 0, start, height))
            if add_space:
                if start < width:
                    painter.drawImage(start + amount, 0, source.copy(start, 0, width - start, height))
            elif end < width:
                painter.drawImage(start, 0, source.copy(end, 0, width - end, height))
            painter.end()
        return QPixmap.fromImage(target), amount

    def _capture_cutout_state(self, items):
        canvas = getattr(self.main_window, "canvas_bounds_item", None)
        return {
            "canvas_rect": QRectF(canvas.rect()) if canvas else QRectF(),
            "items": [
                (
                    item,
                    QPointF(item.pos()),
                    item.pixmap().copy() if isinstance(item, RasterItem) else None,
                )
                for item in items
                if item and not sip.isdeleted(item) and item.scene() is self.scene()
            ],
        }

    def _restore_cutout_state(self, state):
        canvas = getattr(self.main_window, "canvas_bounds_item", None)
        if canvas and not state["canvas_rect"].isEmpty():
            canvas.set_canvas_rect(state["canvas_rect"])
        for item, pos, pixmap in state["items"]:
            if sip.isdeleted(item):
                continue
            if item.scene() is self.scene():
                item.setPos(pos)
            if pixmap is not None and isinstance(item, RasterItem):
                item.applyPixmapEdit(pixmap)
        self.scene().update()

    def _push_cutout_undo(self, description, before_state, after_state):
        action = CallbackAction(
            description,
            lambda state=after_state: self._restore_cutout_state(state),
            lambda state=before_state: self._restore_cutout_state(state),
        )
        self.main_window.undo_manager.push(action)

    def _apply_raster_cutout(self, item, scene_pos, axis, add_space):
        start_local = item.mapFromScene(self._cutout_start_scene)
        current_local = item.mapFromScene(scene_pos)
        start = start_local.y() if axis == "horizontal" else start_local.x()
        end = current_local.y() if axis == "horizontal" else current_local.x()
        new_pixmap, amount = self._cutout_pixmap(item.pixmap(), axis, start, end, add_space)
        if not new_pixmap:
            return False
        before = self._capture_cutout_state([item])
        item.applyPixmapEdit(new_pixmap)
        after = self._capture_cutout_state([item])
        label = "Add Space" if add_space else "Cut Out"
        self._push_cutout_undo(f"{label} Image", before, after)
        unit = "rows" if axis == "horizontal" else "columns"
        self.main_window._status_bar.showMessage(
            f"{label}: {amount}px {unit} {'inserted' if add_space else 'removed'} from selected image",
            4000,
        )
        return True

    def _cutout_local_span_for_item(self, item, axis, start_edge, end_edge):
        bounds = item.sceneBoundingRect()
        if axis == "horizontal":
            x = bounds.center().x()
            p1 = item.mapFromScene(QPointF(x, start_edge))
            p2 = item.mapFromScene(QPointF(x, end_edge))
            return p1.y(), p2.y()
        y = bounds.center().y()
        p1 = item.mapFromScene(QPointF(start_edge, y))
        p2 = item.mapFromScene(QPointF(end_edge, y))
        return p1.x(), p2.x()

    def _apply_canvas_cutout(self, scene_pos, axis, add_space):
        canvas = getattr(self.main_window, "canvas_bounds_item", None)
        if not canvas or self._cutout_start_scene is None:
            return False
        canvas_rect = QRectF(canvas.rect())
        if axis == "horizontal":
            start_edge, end_edge = sorted((self._cutout_start_scene.y(), scene_pos.y()))
            start_edge = max(canvas_rect.top(), min(canvas_rect.bottom(), start_edge))
            end_edge = max(canvas_rect.top(), min(canvas_rect.bottom(), end_edge))
            max_size = canvas_rect.height()
        else:
            start_edge, end_edge = sorted((self._cutout_start_scene.x(), scene_pos.x()))
            start_edge = max(canvas_rect.left(), min(canvas_rect.right(), start_edge))
            end_edge = max(canvas_rect.left(), min(canvas_rect.right(), end_edge))
            max_size = canvas_rect.width()
        amount = int(round(end_edge - start_edge))
        if amount < 1 or (not add_space and amount >= max_size):
            return False

        items = [
            item for item in self.main_window.layer_list.graphics_items()
            if item and not sip.isdeleted(item) and item.scene() is self.scene()
        ]
        before = self._capture_cutout_state(items)
        after_threshold = start_edge if add_space else end_edge
        for item in items:
            bounds = item.sceneBoundingRect()
            before_strip = bounds.bottom() <= start_edge if axis == "horizontal" else bounds.right() <= start_edge
            after_strip = bounds.top() >= after_threshold if axis == "horizontal" else bounds.left() >= after_threshold
            crosses_insert = (
                bounds.top() < start_edge < bounds.bottom()
                if axis == "horizontal"
                else bounds.left() < start_edge < bounds.right()
            )
            crosses_cut = (
                bounds.top() < end_edge and bounds.bottom() > start_edge
                if axis == "horizontal"
                else bounds.left() < end_edge and bounds.right() > start_edge
            )
            if before_strip:
                continue
            if isinstance(item, RasterItem) and ((add_space and crosses_insert) or (not add_space and crosses_cut)):
                local_start, local_end = self._cutout_local_span_for_item(item, axis, start_edge, end_edge)
                new_pixmap, _local_amount = self._cutout_pixmap(item.pixmap(), axis, local_start, local_end, add_space)
                if new_pixmap:
                    item.applyPixmapEdit(new_pixmap)
                continue
            if after_strip:
                delta = QPointF(0, amount if add_space else -amount) if axis == "horizontal" else QPointF(amount if add_space else -amount, 0)
                item.setPos(item.pos() + delta)

        new_rect = QRectF(canvas_rect)
        if axis == "horizontal":
            new_rect.setHeight(canvas_rect.height() + amount if add_space else canvas_rect.height() - amount)
        else:
            new_rect.setWidth(canvas_rect.width() + amount if add_space else canvas_rect.width() - amount)
        canvas.set_canvas_rect(new_rect)
        after = self._capture_cutout_state(items)
        label = "Add Space" if add_space else "Cut Out"
        self._push_cutout_undo(f"{label} Canvas", before, after)
        self.main_window._status_bar.showMessage(
            f"{label}: {amount}px {'horizontal' if axis == 'horizontal' else 'vertical'} space "
            f"{'inserted into' if add_space else 'removed from'} canvas",
            4000,
        )
        return True

    def _clear_cutout_overlay(self, reset_mode=False):
        if self._cutout_overlay and self._cutout_overlay.scene():
            self._cutout_overlay.scene().removeItem(self._cutout_overlay)
        self._cutout_overlay = None
        if reset_mode:
            self._cutout_add_space = False

    def _cancel_cutout_mode(self):
        self._clear_cutout_overlay(reset_mode=True)
        self._cutout_start_scene = None
        self._cutout_target_item = None
        self._cutout_axis = None
        self._apply_cursor()

    def _activate_pending_text_edit(self):
        text_item = self._pending_text_edit_item
        self._pending_text_edit_item = None
        if not text_item:
            return
        if sip.isdeleted(text_item):
            return
        if text_item.scene() is not self.scene():
            return
        text_item.enter_edit_mode(select_all=True)

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

                if isinstance(user_data, dict):
                    item_kind = user_data.get('kind')
                    if item_kind == 'raster':
                        image_bytes = user_data.get('image_bytes')
                        if image_bytes:
                            pixmap = QPixmap()
                            pixmap.loadFromData(image_bytes)
                            if not pixmap.isNull():
                                new_item = RasterItem(pixmap)
                                new_item.image_bytes = image_bytes
                    elif item_kind == 'vector':
                        svg_bytes = user_data.get('svg_bytes')
                        source_path = user_data.get('source_path')
                        renderer = None

                        if svg_bytes:
                            renderer = QSvgRenderer(QByteArray(svg_bytes))
                        elif source_path and os.path.isfile(source_path):
                            renderer = QSvgRenderer(source_path)

                        if renderer and renderer.isValid():
                            new_item = VectorItem(renderer, svg_bytes=svg_bytes, source_path=source_path)

                elif isinstance(user_data, RasterItem):
                    pixmap = QPixmap()
                    pixmap.loadFromData(user_data.image_bytes)
                    new_item = RasterItem(pixmap)
                    new_item.image_bytes = user_data.image_bytes
                elif isinstance(user_data, VectorItem):
                    new_item = self._clone_vector_item(user_data)

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
            if len(selected_layer_items) == 1 and isinstance(selected_layer_items[0], (VectorItem, RasterItem)):
                target_item = selected_layer_items[0]

                if isinstance(target_item, VectorItem):
                    edit_action = QAction("Edit Vector in Inkscape", self)
                    edit_action.triggered.connect(target_item.edit_with_inkscape)
                    menu.addAction(edit_action)

                add_text_action = QAction("Add Textbox Inside Callout", self)
                add_text_action.triggered.connect(lambda _, item=target_item: self._add_text_inside_item(item))
                menu.addAction(add_text_action)

            # Blur-specific: live strength slider.
            blur_items = [it for it in selected_layer_items if isinstance(it, CanvasBlurItem)]
            if blur_items:
                menu.addSeparator()
                strength_action = QAction("Blur Strength…", self)
                strength_action.triggered.connect(
                    lambda _, items=blur_items: self._set_blur_strength(items)
                )
                menu.addAction(strength_action)

            # Highlight-specific: change color.
            hl_items = [it for it in selected_layer_items if isinstance(it, CanvasHighlightItem)]
            if hl_items:
                menu.addSeparator()
                for label, color in (
                    ("Yellow", QColor(255, 235, 59, 110)),
                    ("Green",  QColor(76, 217, 100, 110)),
                    ("Pink",   QColor(255, 105, 180, 110)),
                    ("Blue",   QColor(64, 156, 255, 110)),
                    ("Orange", QColor(255, 149, 0, 110)),
                ):
                    act = QAction(f"Highlight: {label}", self)
                    act.triggered.connect(
                        lambda _, items=hl_items, c=color: [h.setHighlightColor(c) for h in items]
                    )
                    menu.addAction(act)
                custom_act = QAction("Highlight: Custom Color…", self)
                custom_act.triggered.connect(
                    lambda _, items=hl_items: self._pick_highlight_color(items)
                )
                menu.addAction(custom_act)

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
            return True
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if mime_data.hasFormat('image/svg+xml'):
            svg_data = mime_data.data('image/svg+xml')
            log_path = f"pasted_logs/svg_{timestamp}.svg"
            with open(log_path, 'wb') as f:
                f.write(svg_data)
            print(f"Logged SVG to {log_path}")
            renderer = QSvgRenderer(svg_data)
            item = VectorItem(renderer, svg_bytes=bytes(svg_data))
            item.setPos(scene_pos)
            self.itemAdded.emit(item)
            self.main_window.add_artifact(log_path)
            return True
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
            return True
        if mime_data.hasText():
            text = mime_data.text()
            if self._try_paste_path_from_text(text, scene_pos):
                return True
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
            return True
        return False

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
            svg_bytes = None
            try:
                svg_bytes = Path(path).read_bytes()
            except Exception:
                svg_bytes = None

            renderer = QSvgRenderer(svg_bytes) if svg_bytes else QSvgRenderer(path)
            if not renderer.isValid():
                return False
            item = VectorItem(renderer, svg_bytes=svg_bytes, source_path=path)
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
        
        if event.key() == Qt.Key.Key_Escape:
            if self.current_tool == ToolType.CUTOUT:
                self._cancel_cutout_mode()
                return
            # Abort any in-progress drag (blur/highlight/border/rect/ellipse/arrow).
            if self._drawing_item is not None:
                self._abort_drag_preview()
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
        if event.key() == Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.main_window.select_all_items()
            return
        super().keyPressEvent(event)

    def _handle_object_select_press(self, event, clicked_item):
        layer_items = set(self.main_window.layer_list.graphics_items())
        target = self._layer_item_from_hit(clicked_item, layer_items)
        if not target:
            return False

        additive = bool(event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ))
        if additive:
            target.setSelected(not target.isSelected())
            event.accept()
            return True

        if target.isSelected():
            return False

        self.scene().clearSelection()
        target.setSelected(True)
        event.accept()
        return True

    def _layer_item_from_hit(self, item, layer_items):
        current = item
        while current:
            if current in layer_items:
                return current
            current = current.parentItem()
        return None

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
            self._selection_magnifier.show_at(event.pos(), scene_pos)
            self._apply_cursor()
            return
        if overlay:
            self._selection_drop_active = True
            self._selection_drop_pos = scene_pos
            self._selection_magnifier.hide()
            event.accept()
            self._apply_cursor()
            return
        self._selection_host = None
        self._selection_magnifier.hide()
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
        self._selection_magnifier.hide()
        self._apply_cursor()

    def leaveEvent(self, event):
        self._selection_magnifier.hide()
        super().leaveEvent(event)

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
            clone = self._clone_vector_item(item)
            if clone is None:
                return None
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

    def _add_text_inside_item(self, target_item):
        if not target_item or sip.isdeleted(target_item):
            return False

        item_rect = target_item.sceneBoundingRect()
        if item_rect.isEmpty():
            return False

        text_item = CanvasTextItem("Text")
        text_item.setFont(QFont("Arial", 16))
        text_item._update_transform_origin()
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.scene().addItem(text_item)
        text_rect = text_item.boundingRect()
        center = item_rect.center()
        text_item.setPos(center.x() - (text_rect.width() / 2), center.y() - (text_rect.height() / 2))

        self.itemAdded.emit(text_item)
        self.scene().clearSelection()
        text_item.setSelected(True)
        self._pending_text_edit_item = text_item
        QTimer.singleShot(0, self._activate_pending_text_edit)
        return True

    def _clone_vector_item(self, vector_item):
        svg_bytes = getattr(vector_item, 'svg_bytes', None)
        source_path = getattr(vector_item, 'source_path', None)

        renderer = None
        if svg_bytes:
            renderer = QSvgRenderer(QByteArray(svg_bytes))
        elif source_path and os.path.isfile(source_path):
            renderer = QSvgRenderer(source_path)

        if not renderer or not renderer.isValid():
            fallback_renderer = getattr(vector_item, 'renderer', None)
            if fallback_renderer and fallback_renderer.isValid():
                renderer = fallback_renderer
            else:
                return None

        return VectorItem(renderer, svg_bytes=svg_bytes, source_path=source_path)

    def _cancel_selection_mode(self):
        if self._selection_host:
            self._selection_host.clearSelectionOverlay()
        self._selection_host = None
        self._selection_creating = False
        self._selection_drop_active = False
        self._selection_drop_pos = None
        self._selection_magnifier.hide()
        self._apply_cursor()

    def _apply_cursor(self):
        if self.current_tool == ToolType.SELECTION:
            if self._selection_creating or self._selection_drop_active or not self._selection_host:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self.current_tool == ToolType.CUTOUT:
            self.setCursor(Qt.CursorShape.CrossCursor)
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
        if self._cutout_target_item and self._cutout_target_item in deleted_items:
            self._cancel_cutout_mode()


def apply_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(43, 43, 43))
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
        QToolTip {
            background-color: #2b2b2b;
            color: #ffffff;
            border: 1px solid #f0c75e;
            padding: 4px 6px;
            border-radius: 3px;
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
        self.tab_widget.addTab(self._create_agent_tab(), "Agent")
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

        # Canvas Navigation Group
        navigation_group = QGroupBox("Canvas Navigation")
        navigation_layout = QFormLayout(navigation_group)
        navigation_layout.setSpacing(10)

        self.zoom_with_scroll_checkbox = QCheckBox("Zoom with Scroll Wheel")
        saved_zoom_wheel = self.settings.value(
            "canvas/zoom_with_scroll_wheel", True, type=bool
        ) if self.settings else True
        self.zoom_with_scroll_checkbox.setChecked(bool(saved_zoom_wheel))
        navigation_layout.addRow(self.zoom_with_scroll_checkbox)

        self.animated_zoom_checkbox = QCheckBox("Animated Zoom")
        saved_animated_zoom = self.settings.value(
            "canvas/animated_zoom", True, type=bool
        ) if self.settings else True
        self.animated_zoom_checkbox.setChecked(bool(saved_animated_zoom))
        navigation_layout.addRow(self.animated_zoom_checkbox)

        sensitivity_widget = QWidget()
        sensitivity_layout = QHBoxLayout(sensitivity_widget)
        sensitivity_layout.setContentsMargins(0, 0, 0, 0)
        self.zoom_sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_sensitivity_slider.setRange(25, 200)
        self.zoom_sensitivity_slider.setTickInterval(25)
        self.zoom_sensitivity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        saved_sensitivity = int(self.settings.value("canvas/zoom_sensitivity", 100)) if self.settings else 100
        self.zoom_sensitivity_slider.setValue(max(25, min(200, saved_sensitivity)))
        self.zoom_sensitivity_label = QLabel(f"{self.zoom_sensitivity_slider.value()}%")
        self.zoom_sensitivity_label.setFixedWidth(46)
        self.zoom_sensitivity_slider.valueChanged.connect(
            lambda value: self.zoom_sensitivity_label.setText(f"{value}%")
        )
        sensitivity_layout.addWidget(self.zoom_sensitivity_slider)
        sensitivity_layout.addWidget(self.zoom_sensitivity_label)
        navigation_layout.addRow("Zoom sensitivity:", sensitivity_widget)

        zoom_desc = QLabel(
            "When enabled, the mouse wheel zooms at the cursor like the common Photoshop preference. "
            "When disabled, wheel scrolls/pans vertically and Alt+wheel zooms. "
            "Animated Zoom smooths fast wheel flicks into a controlled Photoshop-style glide."
        )
        zoom_desc.setStyleSheet("color: #888; font-size: 11px;")
        zoom_desc.setWordWrap(True)
        navigation_layout.addRow("", zoom_desc)

        layout.addWidget(navigation_group)
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

        # Toolbar Layout group: keep all icons on screen even with larger fonts.
        layout_group = QGroupBox("Toolbar Layout")
        layout_form = QFormLayout(layout_group)
        layout_form.setSpacing(10)

        self.icon_size_combo = QComboBox()
        for label, value in (("Small (24px)", 24), ("Medium (32px)", 32),
                              ("Large (48px)", 48), ("Extra Large (64px)", 64)):
            self.icon_size_combo.addItem(label, value)
        saved_icon_size = int(self.settings.value("appearance/toolbar_icon_size", 48))
        idx = self.icon_size_combo.findData(saved_icon_size)
        if idx < 0:
            # Closest neighbour for unusual saved sizes.
            options = [self.icon_size_combo.itemData(i) for i in range(self.icon_size_combo.count())]
            closest = min(options, key=lambda v: abs(v - saved_icon_size))
            idx = self.icon_size_combo.findData(closest)
        self.icon_size_combo.setCurrentIndex(max(0, idx))
        layout_form.addRow("Icon size:", self.icon_size_combo)

        self.button_style_combo = QComboBox()
        # Stored values match Qt.ToolButtonStyle enum names so they survive restarts.
        self.button_style_combo.addItem("Icon only", "ToolButtonIconOnly")
        self.button_style_combo.addItem("Text below icon", "ToolButtonTextUnderIcon")
        self.button_style_combo.addItem("Text beside icon", "ToolButtonTextBesideIcon")
        self.button_style_combo.addItem("Text only", "ToolButtonTextOnly")
        saved_style = self.settings.value("appearance/toolbar_button_style", "ToolButtonTextUnderIcon")
        idx = self.button_style_combo.findData(saved_style)
        self.button_style_combo.setCurrentIndex(idx if idx >= 0 else 1)
        layout_form.addRow("Button style:", self.button_style_combo)

        self.uniform_width_checkbox = QCheckBox("Use uniform button width")
        self.uniform_width_checkbox.setToolTip(
            "Off (recommended): each button takes only the room it needs, so more "
            "icons fit per row when fonts grow. On: every button matches the widest."
        )
        saved_uniform = self.settings.value("appearance/toolbar_uniform_width", False, type=bool)
        self.uniform_width_checkbox.setChecked(bool(saved_uniform))
        layout_form.addRow("", self.uniform_width_checkbox)

        self.autofit_checkbox = QCheckBox("Auto-fit toolbar to window width")
        self.autofit_checkbox.setToolTip(
            "When the window is resized (e.g. via Hyprland tiling / SUPER+arrow), "
            "shrink icons and drop labels automatically so all tools stay on screen "
            "in two rows or fewer. Overrides the manual Icon size / Button style above."
        )
        saved_autofit = self.settings.value("appearance/toolbar_autofit", True, type=bool)
        self.autofit_checkbox.setChecked(bool(saved_autofit))
        layout_form.addRow("", self.autofit_checkbox)

        layout.addWidget(layout_group)

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

    def get_toolbar_icon_size(self) -> int:
        return int(self.icon_size_combo.currentData())

    def get_toolbar_button_style(self) -> str:
        return self.button_style_combo.currentData()

    def get_toolbar_uniform_width(self) -> bool:
        return self.uniform_width_checkbox.isChecked()

    def get_toolbar_autofit(self) -> bool:
        return self.autofit_checkbox.isChecked()


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
            "Drag rows to reorder toolbar items. Change icons by selecting an item and clicking 'Change Icon'."
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
        self.toolbar_table.setDragEnabled(True)
        self.toolbar_table.setAcceptDrops(True)
        self.toolbar_table.viewport().setAcceptDrops(True)
        self.toolbar_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.toolbar_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.toolbar_table.setDragDropOverwriteMode(False)
        self.toolbar_table.setDropIndicatorShown(True)
        self.toolbar_table.setMinimumHeight(300)
        self.toolbar_table.setIconSize(QSize(32, 32))
        self.toolbar_table.model().rowsMoved.connect(
            lambda *_args: QTimer.singleShot(0, self._apply_toolbar_table_order)
        )
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
        
        self._move_table_row(row, row - 1)
        self._apply_toolbar_table_order()
        self.toolbar_table.selectRow(row - 1)

    def _move_toolbar_item_down(self):
        """Move selected toolbar item down."""
        row = self.toolbar_table.currentRow()
        count = self.toolbar_table.rowCount()
        if row < 0 or row >= count - 1: return
        
        self._move_table_row(row, row + 1)
        self._apply_toolbar_table_order()
        self.toolbar_table.selectRow(row + 1)

    def _move_table_row(self, source_row, target_row):
        if source_row == target_row:
            return
        column_count = self.toolbar_table.columnCount()
        row_items = []
        for col in range(column_count):
            row_items.append(self.toolbar_table.takeItem(source_row, col))
        self.toolbar_table.removeRow(source_row)
        self.toolbar_table.insertRow(target_row)
        for col, item in enumerate(row_items):
            self.toolbar_table.setItem(target_row, col, item)

    def _toolbar_order_from_table(self):
        current_order = []
        for i in range(self.toolbar_table.rowCount()):
            item = self.toolbar_table.item(i, 1)
            if not item:
                continue
            action_id = item.data(Qt.ItemDataRole.UserRole)
            if action_id:
                current_order.append(action_id)
        return current_order

    def _apply_toolbar_table_order(self):
        current_order = self._toolbar_order_from_table()
        if not current_order:
            return
        self.settings.setValue("toolbar/order", current_order)
        if self.main_window and hasattr(self.main_window, "_reorder_toolbar"):
            self.main_window._reorder_toolbar(current_order)

    def _swap_rows(self, row1, row2):
        """Compatibility wrapper for older button wiring."""
        self._move_table_row(row1, row2)
        self._apply_toolbar_table_order()
        self._populate_toolbar_order_list()

    def _reset_toolbar_order(self):
        """Reset toolbar order to default."""
        if self.main_window and hasattr(self.main_window, '_toolbar_action_defs'):
            self.settings.remove("toolbar/order")
            self.main_window._reorder_toolbar(None)
            self.main_window._setup_toolbar_actions()
            self._populate_toolbar_order_list()
    
    def get_toolbar_order(self):
        """Get the new toolbar order from the table."""
        order = []
        for action_id in self._toolbar_order_from_table():
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

    def get_zoom_with_scroll_wheel(self):
        """Return whether the canvas wheel zooms directly."""
        return self.zoom_with_scroll_checkbox.isChecked()

    def get_animated_zoom(self):
        """Return whether wheel zoom is animated."""
        return self.animated_zoom_checkbox.isChecked()

    def get_zoom_sensitivity(self):
        """Return the zoom sensitivity percentage."""
        return self.zoom_sensitivity_slider.value()
    
    def accept(self):
        """Save settings when dialog is accepted."""
        if self.settings:
            self.settings.setValue("canvas/import_behavior", self.get_import_behavior())
            self.settings.setValue("canvas/scale_large_images", self.get_scale_large_images())
            self.settings.setValue("canvas/zoom_with_scroll_wheel", self.get_zoom_with_scroll_wheel())
            self.settings.setValue("canvas/animated_zoom", self.get_animated_zoom())
            self.settings.setValue("canvas/zoom_sensitivity", self.get_zoom_sensitivity())
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

    def _create_agent_tab(self):
        """Create the Agent settings tab for selected-image handoff targets."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        cli_group = QGroupBox("Agent Handoff")
        cli_form = QFormLayout(cli_group)

        self.agent_target_combo = QComboBox()
        self.agent_target_combo.addItem("Clipboard (path)", "clipboard")
        self.agent_target_combo.addItem("Clipboard (base64 image)", "clipboard_base64")
        self.agent_target_combo.addItem("Codex", "codex")
        self.agent_target_combo.addItem("VS Code Codex", "vscode_codex")
        self.agent_target_combo.addItem("Claude", "claude")
        self.agent_target_combo.addItem("OpenClaw", "openclaw")
        self.agent_target_combo.addItem("Wizwam Agent Platform", "wizwam")
        saved_target = self.settings.value("agent/target", "claude")
        idx = self.agent_target_combo.findData(saved_target)
        self.agent_target_combo.setCurrentIndex(idx if idx >= 0 else 1)
        cli_form.addRow("Default agent:", self.agent_target_combo)

        self.agent_command_edit = QLineEdit()
        self.agent_command_edit.setPlaceholderText("claude -p \"{prompt}\"")
        self.agent_command_edit.setText(
            self.settings.value(
                "agent/command_template",
                f"{shutil.which('claude') or 'claude'} -p \"{{prompt}}\"",
            )
        )
        cli_form.addRow("Command template:", self.agent_command_edit)

        self.agent_endpoint_edit = QLineEdit()
        self.agent_endpoint_edit.setPlaceholderText("http://127.0.0.1:18790/...")
        self.agent_endpoint_edit.setText(self.settings.value("agent/http_endpoint", ""))
        cli_form.addRow("HTTP endpoint:", self.agent_endpoint_edit)

        from PyQt6.QtWidgets import QPlainTextEdit
        self.agent_prompt_edit = QPlainTextEdit()
        self.agent_prompt_edit.setPlaceholderText(
            "Please review the annotated screenshot at {image}. "
            "Structured annotations are at {json}. ..."
        )
        default_prompt = (
            "Please review the annotated screenshot at {image}. "
            "Structured annotations are at {json}. "
            "Tell me what changes the user is asking for and propose code edits."
        )
        self.agent_prompt_edit.setPlainText(
            self.settings.value("agent/prompt_template", default_prompt)
        )
        self.agent_prompt_edit.setFixedHeight(120)
        cli_form.addRow("Prompt template:", self.agent_prompt_edit)

        layout.addWidget(cli_group)

        info = QLabel(
            "Send to Agent writes the selected layers as selected.png plus annotations.json. "
            "If nothing is selected, the whole canvas is bundled. Command placeholders: "
            "{prompt}, {image}, {json}, {dir}, {agent}. If an HTTP endpoint is set, "
            "CanvasForge POSTs the same values as JSON instead of launching a command. "
            "VS Code Codex opens the bundle folder in VS Code and copies the ready prompt. "
            "Clipboard path saves a PNG to your save folder and copies the image path. "
            "Clipboard base64 copies a data:image/png;base64 URL for tools like Grok."
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()
        return widget

    def get_agent_target(self) -> str:
        return self.agent_target_combo.currentData() or "claude"

    def get_agent_command_template(self) -> str:
        return self.agent_command_edit.text().strip()

    def get_agent_http_endpoint(self) -> str:
        return self.agent_endpoint_edit.text().strip()

    def get_agent_prompt_template(self) -> str:
        return self.agent_prompt_edit.toPlainText().strip()

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

    def get_zoom_with_scroll_wheel(self):
        """Return whether the canvas wheel zooms directly."""
        return self.zoom_with_scroll_checkbox.isChecked()

    def get_animated_zoom(self):
        """Return whether wheel zoom is animated."""
        return self.animated_zoom_checkbox.isChecked()

    def get_zoom_sensitivity(self):
        """Return the zoom sensitivity percentage."""
        return self.zoom_sensitivity_slider.value()
    
    def accept(self):
        """Save settings when dialog is accepted."""
        if self.settings:
            self.settings.setValue("canvas/import_behavior", self.get_import_behavior())
            self.settings.setValue("canvas/scale_large_images", self.get_scale_large_images())
            self.settings.setValue("canvas/zoom_with_scroll_wheel", self.get_zoom_with_scroll_wheel())
            self.settings.setValue("canvas/animated_zoom", self.get_animated_zoom())
            self.settings.setValue("canvas/zoom_sensitivity", self.get_zoom_sensitivity())
            win_settings = self.get_window_settings()
            self.settings.setValue("window/startup_mode", win_settings["mode"])
            self.settings.setValue("window/startup_monitor", win_settings["monitor"])
            self.settings.setValue("window/startup_state_pref", win_settings["state"])
            self.settings.setValue("plugins/editor_path", self.get_editor_path())
            self.settings.setValue("appearance/icon_theme", self.get_icon_theme())
            self.settings.setValue("appearance/toolbar_icon_size", self.get_toolbar_icon_size())
            self.settings.setValue("appearance/toolbar_button_style", self.get_toolbar_button_style())
            self.settings.setValue("appearance/toolbar_uniform_width", self.get_toolbar_uniform_width())
            self.settings.setValue("appearance/toolbar_autofit", self.get_toolbar_autofit())
            self.settings.setValue("agent/target", self.get_agent_target())
            self.settings.setValue("agent/command_template", self.get_agent_command_template())
            self.settings.setValue("agent/http_endpoint", self.get_agent_http_endpoint())
            self.settings.setValue("agent/prompt_template", self.get_agent_prompt_template())
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
        self._shrink_to_fit_enabled = self.settings.value(
            "view/shrink_to_fit", True, type=bool
        )
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
        canvas_x = float(self.settings.value("canvas/workspace_x", 0))
        canvas_y = float(self.settings.value("canvas/workspace_y", 0))
        canvas_w = float(self.settings.value("canvas/workspace_width", 936))
        canvas_h = float(self.settings.value("canvas/workspace_height", 728))
        self.canvas_bounds_item = CanvasBoundsItem(
            QRectF(canvas_x, canvas_y, max(64, canvas_w), max(64, canvas_h)),
            settings=self.settings,
        )
        self.canvas_bounds_item.add_to_scene(self.scene)
        self.scene.setSceneRect(self.canvas_bounds_item.rect().adjusted(-2000, -2000, 2000, 2000))

        self.artifact_list = ArtifactList()
        self.view = CanvasView(self.scene, self.artifact_list, self)
        self.view.cursorMoved.connect(self.update_cursor_status)
        self.view.itemAdded.connect(self.add_item_to_canvas)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
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
        self._splitter.addWidget(self.right_panel)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setStretchFactor(2, 1)
        self._restore_splitter_sizes()
        sidebars_visible = self.settings.value("view/sidebars_visible", True, type=bool)
        self._set_sidebars_visible(sidebars_visible, persist=False)
        
        # Initialize Plugin Manager (after layer_list is created)
        self.plugin_manager = PluginManager(self, self.undo_manager)

        # Create wrapping toolbar
        self.toolbar = WrappingToolBar(self)
        self._apply_toolbar_layout_settings()
        
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

        send_to_agent_action = QAction("Send to Agent...", self)
        send_to_agent_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        send_to_agent_action.triggered.connect(self.send_to_agent)
        file_menu.addAction(send_to_agent_action)

        copy_bundle_action = QAction("Copy Annotation Bundle Path", self)
        copy_bundle_action.triggered.connect(self.copy_annotation_bundle_path)
        file_menu.addAction(copy_bundle_action)

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
        select_all_action = QAction("Select All Canvas Items", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.select_all_items)
        edit_menu.addAction(select_all_action)
        edit_menu.addSeparator()
        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut(QKeySequence("Ctrl+,"))
        preferences_action.triggered.connect(self.open_preferences)
        edit_menu.addAction(preferences_action)

        self._setup_view_menu()
        
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
        if self._shrink_to_fit_enabled:
            QTimer.singleShot(0, self.view.zoom_to_fit)

    def _do_undo(self):
        """Perform undo action."""
        if self.undo_manager.undo():
            self._status_bar.showMessage(f"Undone: {self.undo_manager.redo_description()}", 2000)
    
    def _do_redo(self):
        """Perform redo action."""
        if self.undo_manager.redo():
            self._status_bar.showMessage(f"Redone: {self.undo_manager.undo_description()}", 2000)

    def _setup_view_menu(self):
        view_menu = self.menuBar().addMenu("View")

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        zoom_in_action.triggered.connect(self.view.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self.view.zoom_out)
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("Zoom to Fit", self)
        zoom_fit_action.triggered.connect(self.view.zoom_to_fit)
        view_menu.addAction(zoom_fit_action)

        self.shrink_to_fit_action = QAction("Shrink to Fit", self)
        self.shrink_to_fit_action.setCheckable(True)
        self.shrink_to_fit_action.setChecked(bool(self._shrink_to_fit_enabled))
        self.shrink_to_fit_action.toggled.connect(self._set_shrink_to_fit)
        view_menu.addAction(self.shrink_to_fit_action)

        actual_size_action = QAction("Actual Size", self)
        actual_size_action.setShortcut(QKeySequence("Ctrl+0"))
        actual_size_action.triggered.connect(self.view.actual_size)
        view_menu.addAction(actual_size_action)

        pixel_grid_action = QAction("Pixel Grid", self)
        pixel_grid_action.setCheckable(True)
        pixel_grid_action.setChecked(bool(getattr(self.view, "_pixel_grid_enabled", False)))
        pixel_grid_action.setShortcut(QKeySequence("Ctrl+G"))
        pixel_grid_action.toggled.connect(self._set_pixel_grid_enabled)
        view_menu.addAction(pixel_grid_action)

        bg_menu = view_menu.addMenu("Background Color")
        for label, color in (
            ("Light Gray", "#d7dde5"),
            ("Dark Gray", "#1f2937"),
            ("White", "#ffffff"),
            ("Black", "#111827"),
        ):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, c=color: self._set_view_background_color(c))
            bg_menu.addAction(action)
        custom_bg_action = QAction("Custom...", self)
        custom_bg_action.triggered.connect(self._choose_view_background_color)
        bg_menu.addAction(custom_bg_action)

        effects_action = QAction("Effects", self)
        effects_action.setEnabled(False)
        view_menu.addAction(effects_action)

        properties_action = QAction("Properties", self)
        properties_action.setEnabled(False)
        view_menu.addAction(properties_action)

        view_menu.addSeparator()
        self.side_bar_action = QAction("Side Bar", self)
        self.side_bar_action.setCheckable(True)
        self.side_bar_action.setChecked(self.library_panel.isVisible() or self.right_panel.isVisible())
        self.side_bar_action.toggled.connect(self._set_sidebars_visible)
        view_menu.addAction(self.side_bar_action)

        details_action = QAction("Details", self)
        details_action.triggered.connect(self._show_details_panel)
        view_menu.addAction(details_action)

        switch_library_action = QAction("Switch to Library", self)
        switch_library_action.triggered.connect(self._switch_to_library)
        view_menu.addAction(switch_library_action)

        recent_action = QAction("Recent Captures", self)
        recent_action.triggered.connect(self._show_recent_captures)
        view_menu.addAction(recent_action)

    def _set_shrink_to_fit(self, enabled: bool):
        self._shrink_to_fit_enabled = bool(enabled)
        self.settings.setValue("view/shrink_to_fit", self._shrink_to_fit_enabled)
        if self._shrink_to_fit_enabled:
            self.view.zoom_to_fit()

    def _set_pixel_grid_enabled(self, enabled: bool):
        self.view.set_pixel_grid_enabled(enabled)
        self.settings.setValue("view/pixel_grid", bool(enabled))

    def _set_view_background_color(self, color):
        qcolor = QColor(color)
        if not qcolor.isValid():
            return
        self.view.set_view_background(qcolor)
        self.settings.setValue("view/background_color", qcolor.name())

    def _choose_view_background_color(self):
        from PyQt6.QtWidgets import QColorDialog
        current = getattr(self.view, "_background_color", QColor("#d7dde5"))
        chosen = QColorDialog.getColor(current, self, "Background Color")
        if chosen.isValid():
            self._set_view_background_color(chosen)

    def _set_sidebars_visible(self, visible: bool, persist: bool = True):
        visible = bool(visible)
        if hasattr(self, "library_panel"):
            self.library_panel.setVisible(visible)
        if hasattr(self, "right_panel"):
            self.right_panel.setVisible(visible)
        if visible and hasattr(self, "_splitter"):
            sizes = self._splitter.sizes()
            if len(sizes) == 3 and (sizes[0] == 0 or sizes[2] == 0):
                self._restore_splitter_sizes()
        if persist:
            self.settings.setValue("view/sidebars_visible", visible)
        if hasattr(self, "side_bar_action") and self.side_bar_action.isChecked() != visible:
            self.side_bar_action.setChecked(visible)

    def _show_details_panel(self):
        self._set_sidebars_visible(True)
        self.layer_list.setFocus()

    def _switch_to_library(self):
        self._set_sidebars_visible(True)
        self.library_panel.list_view_widget().setFocus()

    def _show_recent_captures(self):
        self._set_sidebars_visible(True)
        self.library_panel.search_field.clear()
        self.library_panel.sort_combo.setCurrentIndex(0)
        self.library_panel.refresh()
        self.library_panel.list_view_widget().setFocus()

    def set_active_plugin_tool(self, plugin_instance):
        """Set the active plugin tool on the canvas view."""
        self.view.set_active_plugin_tool(plugin_instance)

    def activate_cutout_tool(self):
        self.view.set_cutout_add_mode(
            bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)
        )
        self.view.set_tool(ToolType.CUTOUT)

    def _setup_toolbar_actions(self):
        """Define all toolbar actions with their properties."""
        
        # Define core toolbar actions
        # Each entry: (id, icon_name, text, callback, shortcut, is_core)
        core_actions = [
            ("pointer", "toolbar_icon_pointer", "Pointer", lambda: self.view.set_tool(ToolType.SELECT), None, True),
            ("select", "toolbar_icon_selection", "Select", lambda: self.view.set_tool(ToolType.SELECT), "S", True),
            ("cutout", "toolbar_icon_cut", "Cutout", self.activate_cutout_tool, None, True),
            ("move", "toolbar_icon_move", "Move", lambda: self.view.set_tool(ToolType.MOVE), None, True),
            ("rotate", "toolbar_icon_rotate", "Rotate", lambda: self.view.set_tool(ToolType.ROTATE), None, True),
            ("scale", "toolbar_icon_scale", "Scale", lambda: self.view.set_tool(ToolType.SCALE), None, True),
            ("delete", "toolbar_icon_eraser", "Delete", self.delete_selected_items, None, True),
            ("snap_grid", "toolbar_icon_snap_grid", "Snap Grid", lambda: self.view.set_tool(ToolType.ALIGN_GRID), None, True),
            ("bring_forward", "toolbar_icon_bring_forward", "Bring Forward", lambda: self.adjust_layer_z(-1), None, True),
            ("send_backward", "toolbar_icon_send_backward", "Send Backward", lambda: self.adjust_layer_z(1), None, True),
            ("---separator1---", None, None, None, None, True),  # Separator marker
            ("save_selected", "toolbar_icon_save_as", "Save Selected", self.save_selected_items, "Ctrl+Alt+S", True),
            ("send_to_agent", "toolbar_icon_send_to_agent", "Send to Agent", self.send_to_agent, "Ctrl+Shift+A", True),
            ("---separator_agent---", None, None, None, None, True),  # Separator marker
            ("flatten_selected", "toolbar_icon_flatten_selected", "Flatten Selected", self.flatten_selected, None, True),
            ("flatten_all", "toolbar_icon_flatten_all", "Flatten All", self.flatten_all, None, True),
            ("---separator2---", None, None, None, None, True),  # Separator marker
            ("rectangle", "toolbar_icon_rectangle", "Rectangle", lambda: self.view.set_tool(ToolType.RECTANGLE), None, True),
            ("ellipse", "toolbar_icon_ellipse", "Ellipse", lambda: self.view.set_tool(ToolType.ELLIPSE), None, True),
            ("arrow", "toolbar_icon_arrow", "Arrow", lambda: self.view.set_tool(ToolType.ARROW), "A", True),
            ("step", "toolbar_icon_step", "Step", lambda: self.view.set_tool(ToolType.STEP), "N", True),
            ("blur", "toolbar_icon_blur", "Blur", lambda: self.view.set_tool(ToolType.BLUR), "B", True),
            ("highlight", "toolbar_icon_highlight", "Highlight", lambda: self.view.set_tool(ToolType.HIGHLIGHT), "H", True),
            ("border", "toolbar_icon_border", "Border", lambda: self.view.set_tool(ToolType.BORDER), None, True),
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
        default_order = list(self._toolbar_action_defs.keys())
        saved_order = self.settings.value("toolbar/order", None)
        if saved_order:
            if isinstance(saved_order, str):
                saved_order = [part.strip() for part in saved_order.split(",") if part.strip()]
            order = [action_id for action_id in saved_order if action_id in self._toolbar_action_defs]
            for action_id in default_order:
                if action_id in order:
                    continue
                default_index = default_order.index(action_id)
                insert_at = len(order)
                for previous in reversed(default_order[:default_index]):
                    if previous in order:
                        insert_at = order.index(previous) + 1
                        break
                order.insert(insert_at, action_id)
            return order
        return default_order
    
    def _apply_toolbar_layout_settings(self):
        """Read appearance settings and push them onto the toolbar widget."""
        size_px = int(self.settings.value("appearance/toolbar_icon_size", 48))
        size_px = max(16, min(size_px, 128))
        self.toolbar.setIconSize(QSize(size_px, size_px))

        style_name = self.settings.value("appearance/toolbar_button_style", "ToolButtonTextUnderIcon")
        style_map = {
            "ToolButtonIconOnly": Qt.ToolButtonStyle.ToolButtonIconOnly,
            "ToolButtonTextOnly": Qt.ToolButtonStyle.ToolButtonTextOnly,
            "ToolButtonTextBesideIcon": Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
            "ToolButtonTextUnderIcon": Qt.ToolButtonStyle.ToolButtonTextUnderIcon,
        }
        self.toolbar.setToolButtonStyle(
            style_map.get(style_name, Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        )

        uniform = self.settings.value("appearance/toolbar_uniform_width", False, type=bool)
        self.toolbar.setUniformWidth(bool(uniform))

        # Auto-fit runs last so it can override icon size / style for the
        # current window width; resizeEvent will keep it in sync after that.
        autofit = self.settings.value("appearance/toolbar_autofit", True, type=bool)
        self.toolbar.setAutoFit(bool(autofit))

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

        # Now that all buttons exist, run a single geometry+layout pass.
        if self.toolbar.autoFit():
            self.toolbar._run_autofit()
        else:
            self.toolbar._compute_geometry()
            self.toolbar._relayout()
    
    def save_toolbar_order(self, order):
        """Save the toolbar order to settings and rebuild toolbar."""
        if order:
            self.settings.setValue("toolbar/order", order)
        else:
            self.settings.remove("toolbar/order")
        self._build_toolbar()

    def _reorder_toolbar(self, order):
        """Apply a toolbar order immediately, used by the Preferences table."""
        if order:
            self.settings.setValue("toolbar/order", order)
        else:
            self.settings.remove("toolbar/order")
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

            # Apply toolbar layout (icon size / button style / uniform width).
            self._apply_toolbar_layout_settings()
            self.view.set_zoom_with_scroll_wheel(
                self.settings.value("canvas/zoom_with_scroll_wheel", True, type=bool)
            )
            self.view.set_animated_zoom_enabled(
                self.settings.value("canvas/animated_zoom", True, type=bool)
            )
            self.view.set_zoom_sensitivity(
                self.settings.value("canvas/zoom_sensitivity", 100)
            )
            # Re-resolve icons in case the theme changed.
            self._setup_toolbar_actions()
            self._build_toolbar()

    def open_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Images", "", "Images (*.png *.jpg *.svg)")
        for file in files:
            self.add_artifact(file)

    def paste_image(self):
        viewport_center = self.view.viewport().rect().center()
        if self.view.paste_at_position(viewport_center):
            self._status_bar.showMessage("Pasted clipboard content onto canvas", 2000)
        else:
            self._status_bar.showMessage("Clipboard does not contain a supported paste item", 3000)

    def add_artifact(self, file_path, display_name=None):
        lower = str(file_path).lower()

        if lower.endswith('.svg'):
            svg_bytes = None
            try:
                svg_bytes = Path(file_path).read_bytes()
            except Exception:
                svg_bytes = None

            renderer = QSvgRenderer(svg_bytes) if svg_bytes else QSvgRenderer(file_path)
            if renderer.isValid():
                item = VectorItem(renderer, svg_bytes=svg_bytes, source_path=file_path)
                self.add_to_repository(item, thumbnail_source=file_path, display_name=display_name)
            return

        reader = QImageReader(file_path)
        if reader.canRead():
            pixmap = QPixmap(file_path)
            item = RasterItem(pixmap)
            self.add_to_repository(item, thumbnail_source=file_path, display_name=display_name)
        else:
            renderer = QSvgRenderer(file_path)
            if renderer.isValid():
                item = VectorItem(renderer, source_path=file_path)
                self.add_to_repository(item, thumbnail_source=file_path, display_name=display_name)

    def add_to_repository(self, item, thumbnail_source=None, thumbnail_pixmap=None, display_name=None):
        list_item = QListWidgetItem()
        pixmap = None
        if thumbnail_pixmap:
            pixmap = thumbnail_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio)
        elif thumbnail_source:
            pixmap = QPixmap(thumbnail_source).scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio)
        if pixmap:
            list_item.setIcon(QIcon(pixmap))

        if display_name:
            list_item.setText(display_name)
        else:
            list_item.setText(f"Item {self.artifact_list.count() + 1}")

        repository_payload = item
        if isinstance(item, RasterItem):
            repository_payload = {
                'kind': 'raster',
                'image_bytes': bytes(getattr(item, 'image_bytes', b'')),
            }
        elif isinstance(item, VectorItem):
            repository_payload = {
                'kind': 'vector',
                'svg_bytes': bytes(item.svg_bytes) if item.svg_bytes else None,
                'source_path': item.source_path,
            }

        list_item.setData(Qt.ItemDataRole.UserRole, repository_payload)
        self.artifact_list.addItem(list_item)

    def add_item_to_canvas(self, item):
        if item.scene() != self.scene:
            self.scene.addItem(item)
        if hasattr(self, "canvas_bounds_item"):
            self.canvas_bounds_item.ensure_contains(item.sceneBoundingRect())
        layer_item = QListWidgetItem()
        name = "Layer"
        # Order matters: more specific subclasses must be checked first.
        if isinstance(item, CanvasArrowItem):
            name = "Arrow"
        elif isinstance(item, CanvasStepItem):
            name = "Step"
        elif isinstance(item, CanvasBlurItem):
            name = "Blur"
        elif isinstance(item, CanvasHighlightItem):
            name = "Highlight"
        elif isinstance(item, CanvasBorderItem):
            name = "Border"
        elif isinstance(item, QGraphicsRectItem):
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

    def select_all_items(self):
        items = self.layer_list.graphics_items()
        if not items:
            self._status_bar.showMessage("No canvas items to select", 3000)
            return
        self.scene.blockSignals(True)
        self.layer_list.blockSignals(True)
        self.scene.clearSelection()
        self.layer_list.clearSelection()
        item_to_list = {}
        for i in range(self.layer_list.count()):
            list_item = self.layer_list.item(i)
            item_to_list[list_item.data(Qt.ItemDataRole.UserRole)] = list_item
        for graphics_item in items:
            if graphics_item and not sip.isdeleted(graphics_item):
                graphics_item.setSelected(True)
                list_item = item_to_list.get(graphics_item)
                if list_item:
                    list_item.setSelected(True)
        self.layer_list.blockSignals(False)
        self.scene.blockSignals(False)
        self._status_bar.showMessage(f"Selected {len(items)} items", 3000)

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

    def save_selected_items(self):
        items = self._selected_layer_items()
        if not items:
            self._status_bar.showMessage("Select at least one item to save", 4000)
            return
        image = self._capture_scene_image(items)
        if image is None:
            self._status_bar.showMessage("Selected items could not be saved", 4000)
            return
        self._ensure_save_directory()
        base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge_selection"
        counter = 1
        while True:
            candidate = self.default_save_dir / f"{base_name}_{counter}.png"
            if not candidate.exists():
                break
            counter += 1
        if image.save(str(candidate)):
            self._status_bar.showMessage(f"Saved selected items to {candidate}", 5000)
        else:
            self._status_bar.showMessage(f"ERROR: Failed to save selected items to {candidate}", 5000)

    def _ensure_save_directory(self):
        self.default_save_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Agent handoff: serialize annotations + flatten image, run Claude CLI.
    # ------------------------------------------------------------------
    def _serialize_annotations(self, items=None):
        """Return a list of dicts describing every meaningful scene item.

        Schema (one entry per scene item):
            {
              "id": int,                # zValue order — useful for stacking
              "type": "rect"|"ellipse"|"arrow"|"step"|"text"|"image"|"vector",
              "x": float, "y": float,   # scene-space top-left (or center for step)
              "w": float, "h": float,   # bounding-rect width/height
              "rotation": float,        # degrees
              "text": str,              # text content (when applicable)
              "number": int,            # step number (when applicable)
              "endpoints": [[sx,sy],[ex,ey]],  # arrows only, scene coords
              "color": "#rrggbb"        # primary color when known
            }
        """
        allowed = set(items) if items is not None else None
        items = []
        for it in self.scene.items():
            if allowed is not None and it not in allowed:
                continue
            if getattr(it, "is_canvas_chrome", False):
                continue
            if isinstance(it, (ResizeHandle, RotateHandle)):
                continue
            br = it.sceneBoundingRect()
            entry = {
                "id": int(it.zValue() * 1000) if it.zValue() else None,
                "x": round(br.x(), 1),
                "y": round(br.y(), 1),
                "w": round(br.width(), 1),
                "h": round(br.height(), 1),
                "rotation": round(it.rotation(), 2),
            }
            if isinstance(it, CanvasArrowItem):
                entry["type"] = "arrow"
                start, end = it.endpoints()
                ssp = it.mapToScene(start)
                esp = it.mapToScene(end)
                entry["endpoints"] = [
                    [round(ssp.x(), 1), round(ssp.y(), 1)],
                    [round(esp.x(), 1), round(esp.y(), 1)],
                ]
                color = it.pen().color()
                entry["color"] = color.name()
            elif isinstance(it, CanvasStepItem):
                entry["type"] = "step"
                entry["number"] = it.number()
                center = it.scenePos()
                entry["x"] = round(center.x(), 1)
                entry["y"] = round(center.y(), 1)
                color = it.brush().color()
                entry["color"] = color.name()
            elif isinstance(it, CanvasHighlightItem):
                entry["type"] = "highlight"
                color = it.highlightColor()
                entry["color"] = color.name(QColor.NameFormat.HexArgb)
            elif isinstance(it, CanvasBorderItem):
                entry["type"] = "border"
                entry["color"] = it.pen().color().name()
                entry["thickness"] = it.pen().width()
            elif isinstance(it, CanvasBlurItem):
                entry["type"] = "blur"
                entry["blur_radius"] = round(it.blurRadius(), 1)
            elif isinstance(it, CanvasRectItem):
                entry["type"] = "rect"
                entry["color"] = it.pen().color().name()
            elif isinstance(it, CanvasEllipseItem):
                entry["type"] = "ellipse"
                entry["color"] = it.pen().color().name()
            elif isinstance(it, CanvasTextItem):
                entry["type"] = "text"
                entry["text"] = it.toPlainText()
                entry["color"] = it.defaultTextColor().name()
            elif isinstance(it, QGraphicsSvgItem):
                entry["type"] = "vector"
            elif isinstance(it, QGraphicsPixmapItem):
                entry["type"] = "image"
            else:
                # Skip helper/overlay items.
                continue
            items.append(entry)
        items.sort(key=lambda e: (e.get("id") or 0))
        return items

    def _build_annotation_bundle(self) -> Path | None:
        """Flatten the canvas to PNG and write annotations.json next to it.

        Returns the directory containing both files, or None if there's
        nothing on the canvas.
        """
        import json
        selected_items = self._selected_layer_items()
        bundle_items = selected_items or self.layer_list.graphics_items()
        image = self._capture_scene_image(bundle_items)
        if image is None:
            self._status_bar.showMessage("Nothing on canvas to send", 4000)
            return None
        bundle_dir = Path(tempfile.mkdtemp(prefix="canvasforge_agent_"))
        png_path = bundle_dir / ("selected.png" if selected_items else "canvas.png")
        json_path = bundle_dir / "annotations.json"
        if not image.save(str(png_path)):
            self._status_bar.showMessage("Failed to write canvas PNG", 4000)
            return None
        bundle = {
            "schema": "canvasforge.agent.bundle/1",
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "canvas_image": png_path.name,
            "selected_only": bool(selected_items),
            "scene_size": [
                round(image.width(), 1),
                round(image.height(), 1),
            ],
            "annotations": self._serialize_annotations(bundle_items),
        }
        json_path.write_text(json.dumps(bundle, indent=2))
        return bundle_dir

    def copy_annotation_bundle_path(self):
        """Build the bundle and copy its directory path to the clipboard."""
        bundle_dir = self._build_annotation_bundle()
        if bundle_dir is None:
            return
        QApplication.clipboard().setText(str(bundle_dir))
        self._status_bar.showMessage(
            f"Annotation bundle at {bundle_dir} (path copied to clipboard)", 8000
        )

    def _next_agent_clipboard_image_path(self) -> Path:
        self._ensure_save_directory()
        base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge"
        counter = 1
        while True:
            candidate = self.default_save_dir / f"{base_name}_{counter}.png"
            if not candidate.exists():
                return candidate
            counter += 1

    def _notify_clipboard_image_path(self, image_path: Path, copied_value: str = "path"):
        if copied_value == "base64":
            message = f"Base64 image URL copied to clipboard:\n{image_path}"
        else:
            message = f"Image path copied to clipboard:\n{image_path}"
        self._status_bar.showMessage(message.replace("\n", " "), 7000)
        notify_send = shutil.which("notify-send")
        if not notify_send:
            return
        try:
            subprocess.Popen(
                [
                    notify_send,
                    "-a",
                    "CanvasForge",
                    "-t",
                    "3500",
                    "CanvasForge",
                    message,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _clipboard_image_mime_data(self, image: QImage, image_path: Path, as_base64: bool) -> QMimeData | None:
        import base64

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            return None
        png_bytes = bytes(buffer.data())

        mime_data = QMimeData()
        mime_data.setData("image/png", QByteArray(png_bytes))
        mime_data.setImageData(image)
        mime_data.setUrls([QUrl.fromLocalFile(str(image_path))])
        if as_base64:
            image_text = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
        else:
            image_text = str(image_path)
        mime_data.setText(image_text)
        return mime_data

    def _send_to_clipboard_agent(self, as_base64: bool = False) -> Path | None:
        selected_items = self._selected_layer_items()
        image_items = selected_items or self.layer_list.graphics_items()
        if not image_items:
            self._status_bar.showMessage("Nothing on canvas to send", 4000)
            return None
        image = self._capture_scene_image(image_items)
        if image is None:
            self._status_bar.showMessage("Nothing on canvas to send", 4000)
            return None
        image_path = self._next_agent_clipboard_image_path()
        if not image.save(str(image_path)):
            self._status_bar.showMessage(f"ERROR: Failed to save image to {image_path}", 5000)
            return None
        mime_data = self._clipboard_image_mime_data(image, image_path, as_base64)
        if mime_data is None:
            self._status_bar.showMessage("ERROR: Failed to encode image for clipboard", 5000)
            return None
        QApplication.clipboard().setMimeData(mime_data)
        self._notify_clipboard_image_path(image_path, "base64" if as_base64 else "path")
        return image_path

    def send_to_agent(self):
        """Build a selected-image bundle and send it to the configured agent."""
        target = str(self.settings.value("agent/target", "claude") or "claude")
        if target in ("clipboard", "clipboard_base64"):
            self._send_to_clipboard_agent(as_base64=(target == "clipboard_base64"))
            return

        bundle_dir = self._build_annotation_bundle()
        if bundle_dir is None:
            return
        png_path = next(bundle_dir.glob("*.png"))
        json_path = bundle_dir / "annotations.json"

        prompt_template = self.settings.value(
            "agent/prompt_template",
            "Please review the annotated screenshot at {image}. "
            "Structured annotations are at {json}. "
            "Tell me what changes the user is asking for and propose code edits.",
        )
        prompt = prompt_template.format(
            image=str(png_path), json=str(json_path), dir=str(bundle_dir), agent=target
        )

        if target == "vscode_codex":
            self._send_to_vscode_codex(prompt, png_path, json_path, bundle_dir)
            return

        endpoint = str(self.settings.value("agent/http_endpoint", "") or "").strip()
        if endpoint:
            self._post_bundle_to_agent(endpoint, target, prompt, png_path, json_path, bundle_dir)
            return

        legacy_cli = str(self.settings.value("agent/cli_path", "") or "")
        default_command = f"{legacy_cli or shutil.which('claude') or 'claude'} -p \"{{prompt}}\""
        command_template = str(
            self.settings.value("agent/command_template", default_command) or ""
        ).strip()
        if not command_template:
            QMessageBox.warning(
                self,
                "Agent command not configured",
                "Set an Agent command template or HTTP endpoint in Preferences.",
            )
            return
        command = command_template.format(
            prompt=prompt,
            image=str(png_path),
            json=str(json_path),
            dir=str(bundle_dir),
            agent=target,
        )
        import shlex
        try:
            cmd = shlex.split(command)
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._status_bar.showMessage(
                f"Sent selected image to {target}: {cmd[0]} (bundle: {bundle_dir})", 8000
            )
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Agent command not found",
                f"Could not run '{cmd[0]}'. Set the command in Preferences → Agent. "
                f"The annotation bundle is still "
                f"available at:\n\n{bundle_dir}",
            )
        except ValueError as exc:
            QMessageBox.warning(
                self,
                "Agent command error",
                f"Could not parse the Agent command template:\n\n{exc}\n\nBundle: {bundle_dir}",
            )

    def _send_to_vscode_codex(self, prompt, png_path, json_path, bundle_dir):
        code_path = shutil.which("code")
        prompt_path = bundle_dir / "codex_prompt.md"
        prompt_path.write_text(
            "# CanvasForge to VS Code Codex\n\n"
            f"{prompt}\n\n"
            "## Bundle\n\n"
            f"- Image: `{png_path}`\n"
            f"- Annotations: `{json_path}`\n"
            f"- Folder: `{bundle_dir}`\n\n"
            "Open the image and annotations in this folder, then use this prompt in the VS Code Codex/OpenAI panel.\n",
            encoding="utf-8",
        )
        QApplication.clipboard().setText(prompt_path.read_text(encoding="utf-8"))

        if not code_path:
            QMessageBox.warning(
                self,
                "VS Code not found",
                f"Could not find the 'code' command. The Codex prompt was copied "
                f"to the clipboard and the bundle is available at:\n\n{bundle_dir}",
            )
            return

        try:
            subprocess.Popen(
                [code_path, "--reuse-window", str(bundle_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._status_bar.showMessage(
                f"Opened VS Code Codex bundle: {bundle_dir} (prompt copied)", 10000
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "VS Code handoff failed",
                f"Could not open VS Code:\n\n{exc}\n\n"
                f"The Codex prompt was copied and the bundle is at:\n\n{bundle_dir}",
            )

    def _post_bundle_to_agent(self, endpoint, target, prompt, png_path, json_path, bundle_dir):
        import base64
        import json
        import urllib.request
        payload = {
            "source": "CanvasForge",
            "target": target,
            "prompt": prompt,
            "bundle_dir": str(bundle_dir),
            "image_path": str(png_path),
            "annotations_path": str(json_path),
            "image_base64": base64.b64encode(png_path.read_bytes()).decode("ascii"),
            "annotations": json.loads(json_path.read_text()),
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=15).read()
            self._status_bar.showMessage(
                f"Posted selected image to {target} via {endpoint}", 8000
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Agent HTTP send failed",
                f"Could not POST to {endpoint}:\n\n{exc}\n\nBundle: {bundle_dir}",
            )

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

    def _capture_scene_image(self, target_items=None):
        selected_items = list(self.scene.selectedItems())
        chrome_states = []
        for scene_item in self.scene.items():
            if getattr(scene_item, "is_canvas_chrome", False):
                chrome_states.append((scene_item, scene_item.isVisible()))
                scene_item.setVisible(False)
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

        visible_states = []
        targets = [item for item in (target_items or []) if item and not sip.isdeleted(item)]
        if targets:
            target_set = set(targets)
            for scene_item in self.scene.items():
                if scene_item not in target_set and scene_item.isVisible():
                    visible_states.append(scene_item)
                    scene_item.setVisible(False)
            rect = QRectF()
            for item in targets:
                if item.scene() is self.scene:
                    rect = item.sceneBoundingRect() if rect.isNull() else rect.united(item.sceneBoundingRect())
        else:
            layer_items = [
                item for item in self.layer_list.graphics_items()
                if item and not sip.isdeleted(item) and item.scene() is self.scene
            ]
            rect = QRectF()
            for item in layer_items:
                rect = item.sceneBoundingRect() if rect.isNull() else rect.united(item.sceneBoundingRect())
            if rect.isEmpty() and hasattr(self, "canvas_bounds_item"):
                rect = QRectF(self.canvas_bounds_item.rect())
        if rect.isEmpty():
            rect = QRectF(self.view.viewport().rect())
        size = rect.size().toSize()
        if size.isEmpty():
            for hidden in visible_states:
                hidden.setVisible(True)
            for item, was_visible in chrome_states:
                item.setVisible(was_visible)
            self._restore_selection_state(selected_items, overlay_item, overlay_state)
            return None
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        for hidden in visible_states:
            hidden.setVisible(True)
        for item, was_visible in chrome_states:
            item.setVisible(was_visible)
        self._restore_selection_state(selected_items, overlay_item, overlay_state)
        return image

    def closeEvent(self, event):
        """Save window state before closing."""
        if hasattr(self, '_splitter'):
            sidebars_visible = (
                getattr(self, "library_panel", None) and self.library_panel.isVisible()
            ) or (
                getattr(self, "right_panel", None) and self.right_panel.isVisible()
            )
            if sidebars_visible:
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
