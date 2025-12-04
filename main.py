import sys
import tempfile
import subprocess
import os
import time
import math
from enum import Enum, auto
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
				 QGraphicsPixmapItem, QListWidget,
				 QToolBar, QFileDialog, QVBoxLayout, QWidget,
				 QHBoxLayout, QGraphicsRectItem, QGraphicsEllipseItem, QListWidgetItem, QLabel,
				 QAbstractItemView, QGraphicsItem, QGraphicsTextItem, QMenu)
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import (QPixmap, QImageReader, QAction, QPainter, QIcon, QPen, QColor, QBrush,
					 QFont, QTransform, QClipboard, QImage, QKeySequence, QTextCursor, QPalette)
from PyQt6.QtCore import (Qt, QMimeData, QPointF, QPoint, pyqtSignal, QRectF, QTimer,
		  QByteArray, QBuffer, QIODevice, QSizeF, QUrl, QSettings)
from pathlib import Path
import datetime


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

	def wheelEvent(self, event):
		factor = 1.25 if event.angleDelta().y() > 0 else 0.8
		self._zoom_factor *= factor
		self._zoom_factor = max(0.1, min(10.0, self._zoom_factor))
		cursor_pos = self.mapToScene(event.position().toPoint())
		self.setTransform(QTransform().scale(self._zoom_factor, self._zoom_factor))
		self.centerOn(cursor_pos)

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.MiddleButton:
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
			super().mousePressEvent(event)
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
		if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
			event.acceptProposedAction()
		else:
			super().dragEnterEvent(event)

	def dragMoveEvent(self, event):
		if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
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


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		def get_icon(name):
			return QIcon(os.path.join(os.path.dirname(__file__), "assets", "toolbar_icons", name))

		self.setWindowTitle("CanvasForge")
		self.setGeometry(100, 100, 1200, 800)
		self.fill_mode = FillMode.TRANSPARENT
		self.settings = QSettings("CanvasForge", "CanvasForge")
		default_pictures = Path.home() / "Pictures" / "CanvasForge"
		saved_dir = self.settings.value("default_save_dir", str(default_pictures))
		self.default_save_dir = Path(saved_dir)
		self._ensure_save_directory()
		self._status_bar = self.statusBar()
		self._status_bar.showMessage("Cursor: x=0.0, y=0.0")

		central_widget = QWidget()
		self.setCentralWidget(central_widget)
		main_layout = QHBoxLayout(central_widget)

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

		main_layout.addWidget(self.view, 3)
		main_layout.addWidget(right_widget, 1)

		self.toolbar = QToolBar("Tools")
		self.toolbar.setIconSize(QSizeF(48, 48).toSize())
		self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
		self.toolbar.setStyleSheet("QToolButton { font-size: 10pt; font-weight: bold; }")
		self.addToolBar(self.toolbar)

		pointer_action = QAction(get_icon("toolbar_icon_pointer_95x108.png"), "Pointer", self)
		pointer_action.triggered.connect(lambda: self.view.set_tool(ToolType.SELECT))
		self.toolbar.addAction(pointer_action)

		select_action = QAction(get_icon("toolbar_icon_selection_121x108.png"), "Select", self)
		select_action.setShortcut("S")
		select_action.triggered.connect(lambda: self.view.set_tool(ToolType.SELECTION))
		self.toolbar.addAction(select_action)

		move_action = QAction(get_icon("toolbar_icon_move_88x108.png"), "Move", self)
		move_action.triggered.connect(lambda: self.view.set_tool(ToolType.MOVE))
		self.toolbar.addAction(move_action)

		rotate_action = QAction(get_icon("toolbar_icon_rotate_64x64.svg"), "Rotate", self)
		rotate_action.triggered.connect(lambda: self.view.set_tool(ToolType.ROTATE))
		self.toolbar.addAction(rotate_action)

		scale_action = QAction(get_icon("toolbar_icon_scale_64x64.svg"), "Scale", self)
		scale_action.triggered.connect(lambda: self.view.set_tool(ToolType.SCALE))
		self.toolbar.addAction(scale_action)

		delete_action = QAction(get_icon("toolbar_icon_eraser_99x108.png"), "Delete", self)
		delete_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
		delete_action.triggered.connect(self.delete_selected_items)
		self.toolbar.addAction(delete_action)

		align_action = QAction(get_icon("toolbar_icon_snap_grid_64x64.svg"), "Snap Grid", self)
		align_action.triggered.connect(lambda: self.view.set_tool(ToolType.ALIGN_GRID))
		self.toolbar.addAction(align_action)

		bring_fwd_action = QAction(get_icon("toolbar_icon_bring_forward_64x64.svg"), "Bring Forward", self)
		bring_fwd_action.triggered.connect(lambda: self.adjust_layer_z(-1))
		self.toolbar.addAction(bring_fwd_action)

		send_back_action = QAction(get_icon("toolbar_icon_send_backward_64x64.svg"), "Send Backward", self)
		send_back_action.triggered.connect(lambda: self.adjust_layer_z(1))
		self.toolbar.addAction(send_back_action)

		self.toolbar.addSeparator()

		rect_action = QAction(get_icon("toolbar_icon_shape_93x108.png"), "Rectangle", self)
		rect_action.triggered.connect(lambda: self.view.set_tool(ToolType.RECTANGLE))
		self.toolbar.addAction(rect_action)

		ellipse_action = QAction(get_icon("toolbar_icon_shape_93x108.png"), "Ellipse", self)
		ellipse_action.triggered.connect(lambda: self.view.set_tool(ToolType.ELLIPSE))
		self.toolbar.addAction(ellipse_action)

		text_action = QAction(get_icon("toolbar_icon_text_79x108.png"), "Text", self)
		text_action.triggered.connect(lambda: self.view.set_tool(ToolType.TEXT))
		self.toolbar.addAction(text_action)

		file_menu = self.menuBar().addMenu("File")
		open_action = QAction(get_icon("toolbar_icon_open_94x108.png"), "Open Images", self)
		open_action.triggered.connect(self.open_images)
		file_menu.addAction(open_action)

		paste_action = QAction(get_icon("toolbar_icon_paste_237x108.png"), "Paste", self)
		paste_action.setShortcut("Ctrl+V")
		paste_action.triggered.connect(self.paste_image)
		file_menu.addAction(paste_action)

		save_action = QAction(get_icon("toolbar_icon_save_as_111x108.png"), "Save", self)
		save_action.setShortcut(QKeySequence.StandardKey.Save)
		save_action.triggered.connect(self.save_canvas)
		file_menu.addAction(save_action)

		flatten_selected_action = QAction(get_icon("toolbar_icon_flatten_selected_64x64.svg"), "Flatten Selected", self)
		flatten_selected_action.triggered.connect(self.flatten_selected)
		self.toolbar.addAction(flatten_selected_action)

		flatten_all_action = QAction(get_icon("toolbar_icon_flatten_all_137x108.png"), "Flatten All", self)
		flatten_all_action.triggered.connect(self.flatten_all)
		self.toolbar.addAction(flatten_all_action)

		edit_menu = self.menuBar().addMenu("Edit")
		edit_menu.addAction(delete_action)
		change_save_dir_action = QAction("Change Save Folder...", self)
		change_save_dir_action.triggered.connect(self.change_save_directory)
		edit_menu.addAction(change_save_dir_action)

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
		self.layer_list.setCurrentItem(layer_item)

	def on_layer_selection_changed(self):
		self.scene.blockSignals(True)
		self.scene.clearSelection()
		for item in self.layer_list.selectedItems():
			graphics_item = item.data(Qt.ItemDataRole.UserRole)
			if graphics_item:
				graphics_item.setSelected(True)
		self.scene.blockSignals(False)

	def on_scene_selection_changed(self):
		self.layer_list.blockSignals(True)
		self.layer_list.clearSelection()
		selected_items = self.scene.selectedItems()
		if selected_items:
			for i in range(self.layer_list.count()):
				list_item = self.layer_list.item(i)
				if list_item.data(Qt.ItemDataRole.UserRole) in selected_items:
					list_item.setSelected(True)
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
		if clear_selection:
			self.scene.clearSelection()
			self.layer_list.clearSelection()
		self.view.handle_items_deleted(items)
		self.scene.update()

	def save_canvas(self):
		self._ensure_save_directory()
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
			return
		try:
			image = QImage(size, QImage.Format.Format_ARGB32)
			image.fill(Qt.GlobalColor.transparent)
			painter = QPainter(image)
			self.scene.render(painter, QRectF(image.rect()), rect)
			painter.end()
			base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge"
			counter = 1
			while True:
				candidate = self.default_save_dir / f"{base_name}_{counter}.png"
				if not candidate.exists():
					break
				counter += 1
			image.save(str(candidate))
			self._status_bar.showMessage(f"Saved canvas to {candidate}", 5000)
		finally:
			self._restore_selection_state(selected_items, overlay_item, overlay_state)

	def change_save_directory(self):
		new_dir = QFileDialog.getExistingDirectory(self, "Select Save Folder", str(self.default_save_dir))
		if new_dir:
			self.default_save_dir = Path(new_dir)
			self._ensure_save_directory()
			self.settings.setValue("default_save_dir", str(self.default_save_dir))
			self._status_bar.showMessage(f"Default save folder set to {self.default_save_dir}", 5000)

	def _ensure_save_directory(self):
		self.default_save_dir.mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
	app = QApplication(sys.argv)
	apply_dark_theme(app)
	window = MainWindow()
	window.show()
	sys.exit(app.exec())
