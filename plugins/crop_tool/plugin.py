"""
Crop Tool Plugin for CanvasForge

Allows users to crop raster images on the canvas:
1. Click "Crop" to activate crop mode
2. Click on an image OR drag to draw a crop region (like Select tool)
3. Drag edges/corners to adjust the crop region
4. Press C or right-click > "Crop to Selection" to apply

Features:
- Full undo/redo support
- Visual crop overlay with drag-to-resize edges
- Edge cursors (double-arrow) when hovering crop boundaries
- Keyboard shortcuts: C to apply crop, Escape to cancel
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt6.QtGui import QPen, QBrush, QColor, QPixmap, QCursor


class CropHandle:
    """Represents a draggable edge or corner of the crop overlay."""
    TOP = 0
    RIGHT = 1
    BOTTOM = 2
    LEFT = 3
    TOP_LEFT = 4
    TOP_RIGHT = 5
    BOTTOM_RIGHT = 6
    BOTTOM_LEFT = 7


class CropOverlay(QGraphicsRectItem):
    """Visual overlay showing the crop region with draggable edges."""
    
    HANDLE_SIZE = 12  # pixels for edge/corner hit detection
    
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self._dragging_handle = None
        self._drag_start_rect = None
        self._drag_start_pos = None
        
        # Visual style - dashed yellow border
        pen = QPen(QColor(255, 200, 0), 2, Qt.PenStyle.DashLine)
        self.setPen(pen)
        
        # Semi-transparent fill
        fill = QColor(255, 200, 0)
        fill.setAlpha(40)
        self.setBrush(QBrush(fill))
        
        # Make it interactive
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setZValue(1000)  # Always on top
    
    def set_crop_rect(self, rect: QRectF):
        """Set the crop rectangle in scene coordinates."""
        self.setPos(rect.topLeft())
        self.setRect(0, 0, rect.width(), rect.height())
    
    def scene_crop_rect(self) -> QRectF:
        """Get the crop rectangle in scene coordinates."""
        pos = self.scenePos()
        rect = self.rect()
        return QRectF(pos.x(), pos.y(), rect.width(), rect.height())
    
    def _get_handle_at(self, local_pos: QPointF) -> int:
        """Determine which handle (edge/corner) is at the given local position."""
        rect = self.rect()
        x, y = local_pos.x(), local_pos.y()
        h = self.HANDLE_SIZE
        
        on_left = x < h
        on_right = x > rect.width() - h
        on_top = y < h
        on_bottom = y > rect.height() - h
        
        # Corners first (they take priority)
        if on_top and on_left:
            return CropHandle.TOP_LEFT
        if on_top and on_right:
            return CropHandle.TOP_RIGHT
        if on_bottom and on_right:
            return CropHandle.BOTTOM_RIGHT
        if on_bottom and on_left:
            return CropHandle.BOTTOM_LEFT
        
        # Then edges
        if on_top:
            return CropHandle.TOP
        if on_right:
            return CropHandle.RIGHT
        if on_bottom:
            return CropHandle.BOTTOM
        if on_left:
            return CropHandle.LEFT
        
        return None  # Inside, not on an edge
    
    def _cursor_for_handle(self, handle: int) -> Qt.CursorShape:
        """Get the appropriate cursor for a handle."""
        if handle in (CropHandle.TOP, CropHandle.BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        if handle in (CropHandle.LEFT, CropHandle.RIGHT):
            return Qt.CursorShape.SizeHorCursor
        if handle in (CropHandle.TOP_LEFT, CropHandle.BOTTOM_RIGHT):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in (CropHandle.TOP_RIGHT, CropHandle.BOTTOM_LEFT):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.SizeAllCursor  # For moving the whole thing
    
    def hoverMoveEvent(self, event):
        """Update cursor based on which edge/corner we're hovering."""
        handle = self._get_handle_at(event.pos())
        if handle is not None:
            self.setCursor(self._cursor_for_handle(handle))
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)  # Move cursor inside
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # Show context menu
            self.plugin._show_crop_context_menu(event.screenPos())
            event.accept()
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_handle = self._get_handle_at(event.pos())
            self._drag_start_rect = self.scene_crop_rect()
            self._drag_start_pos = event.scenePos()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self._drag_start_rect is None:
            return
        
        delta = event.scenePos() - self._drag_start_pos
        rect = QRectF(self._drag_start_rect)
        
        handle = self._dragging_handle
        
        if handle is None:
            # Move the entire overlay
            rect.translate(delta)
        else:
            # Resize based on which handle is being dragged
            if handle in (CropHandle.LEFT, CropHandle.TOP_LEFT, CropHandle.BOTTOM_LEFT):
                rect.setLeft(rect.left() + delta.x())
            if handle in (CropHandle.RIGHT, CropHandle.TOP_RIGHT, CropHandle.BOTTOM_RIGHT):
                rect.setRight(rect.right() + delta.x())
            if handle in (CropHandle.TOP, CropHandle.TOP_LEFT, CropHandle.TOP_RIGHT):
                rect.setTop(rect.top() + delta.y())
            if handle in (CropHandle.BOTTOM, CropHandle.BOTTOM_LEFT, CropHandle.BOTTOM_RIGHT):
                rect.setBottom(rect.bottom() + delta.y())
        
        # Normalize and enforce minimum size
        rect = rect.normalized()
        if rect.width() < 10:
            rect.setWidth(10)
        if rect.height() < 10:
            rect.setHeight(10)
        
        # Constrain to target image bounds if we have one
        if self.plugin._target_item:
            img_rect = self.plugin._target_item.sceneBoundingRect()
            rect = rect.intersected(img_rect)
            if rect.isEmpty():
                rect = QRectF(img_rect.topLeft(), QPointF(img_rect.left() + 10, img_rect.top() + 10))
        
        self.set_crop_rect(rect)
        event.accept()
    
    def mouseReleaseEvent(self, event):
        self._dragging_handle = None
        self._drag_start_rect = None
        self._drag_start_pos = None
        event.accept()


class Plugin:
    """Crop Tool Plugin - crop raster images with edge-dragging."""
    
    def __init__(self, api):
        self.api = api
        self._crop_overlay = None
        self._target_item = None
        self._crop_mode_active = False
        self._drawing_crop = False
        self._draw_start_pos = None
        
        # Store original view event handlers
        self._original_mouse_press = None
        self._original_mouse_move = None
        self._original_mouse_release = None
    
    def on_load(self):
        """Called when plugin is loaded."""
        self.api.show_status_message("Crop Tool plugin loaded - Press C to crop", 2000)
    
    def on_unload(self):
        """Called when plugin is unloaded."""
        self.deactivate_crop_mode()
    
    def activate_crop_mode(self):
        """Activate crop mode - user can click an image or draw a crop region."""
        if self._crop_mode_active:
            return
        
        self._crop_mode_active = True
        
        # Register as the active tool so we receive mouse events
        self.api.set_active_tool_plugin(self)
        
        # Get the view and change cursor
        view = self.api._view
        view.setCursor(Qt.CursorShape.CrossCursor)
        
        self.api.show_status_message(
            "Crop Mode: Click on an image, or drag to draw crop region. "
            "Press C to crop, Escape to cancel.",
            5000
        )
    
    def crop_selected(self):
        """Crop the currently selected image (menu callback)."""
        # Get selected items
        scene = self.api._scene
        selected = scene.selectedItems()
        
        # Find a raster item in selection
        target = None
        for item in selected:
            if self.api.is_raster_item(item):
                target = item
                break
        
        if not target:
            self.api.show_status_message("Select an image first to crop", 3000)
            return
        
        # Activate crop mode and set up for this item
        self._crop_mode_active = True
        self.api.set_active_tool_plugin(self)
        
        self._target_item = target
        
        # Create overlay covering the entire image
        img_rect = target.sceneBoundingRect()
        self._crop_overlay = CropOverlay(self)
        self.api._scene.addItem(self._crop_overlay)
        self._crop_overlay.set_crop_rect(img_rect)
        
        view = self.api._view
        view.setCursor(Qt.CursorShape.CrossCursor)
        
        self.api.show_status_message(
            "Drag edges to adjust crop region. Press C or right-click to crop.",
            4000
        )
    
    def deactivate_crop_mode(self):
        """Deactivate crop mode and clean up."""
        if not self._crop_mode_active:
            return
        
        self._crop_mode_active = False
        self._drawing_crop = False
        self._draw_start_pos = None
        
        # Remove overlay
        if self._crop_overlay:
            scene = self._crop_overlay.scene()
            if scene:
                scene.removeItem(self._crop_overlay)
            self._crop_overlay = None
        
        self._target_item = None
        
        # Clear ourselves as the active tool
        self.api.clear_active_tool_plugin()
        
        # Restore view cursor
        view = self.api._view
        view.unsetCursor()
    
    def _on_view_mouse_press(self, event):
        """Handle mouse press in crop mode."""
        if not self._crop_mode_active:
            return False
        
        scene_pos = self.api._view.mapToScene(event.pos())
        
        # Check if clicking on a raster item
        item = self.api._scene.itemAt(scene_pos, self.api._view.transform())
        
        # Skip if clicking on existing overlay
        if item == self._crop_overlay:
            return False
        
        # Find raster item under click
        raster_item = None
        if item and self.api.is_raster_item(item):
            raster_item = item
        else:
            # Check items at this position
            items = self.api._scene.items(scene_pos)
            for i in items:
                if i != self._crop_overlay and self.api.is_raster_item(i):
                    raster_item = i
                    break
        
        if raster_item:
            self._target_item = raster_item
            self._drawing_crop = True
            self._draw_start_pos = scene_pos
            
            # Create or reset overlay
            if self._crop_overlay:
                self._crop_overlay.scene().removeItem(self._crop_overlay)
            
            self._crop_overlay = CropOverlay(self)
            self.api._scene.addItem(self._crop_overlay)
            self._crop_overlay.set_crop_rect(QRectF(scene_pos, scene_pos))
            
            return True
        
        return False
    
    def _on_view_mouse_move(self, event):
        """Handle mouse move in crop mode (while drawing)."""
        if not self._drawing_crop or not self._crop_overlay:
            return False
        
        scene_pos = self.api._view.mapToScene(event.pos())
        
        # Create rect from start to current
        rect = QRectF(self._draw_start_pos, scene_pos).normalized()
        
        # Constrain to target image
        if self._target_item:
            img_rect = self._target_item.sceneBoundingRect()
            rect = rect.intersected(img_rect)
        
        if not rect.isEmpty():
            self._crop_overlay.set_crop_rect(rect)
        
        return True
    
    def _on_view_mouse_release(self, event):
        """Handle mouse release in crop mode."""
        if not self._drawing_crop:
            return False
        
        self._drawing_crop = False
        self._draw_start_pos = None
        
        # Check if we have a valid crop region
        if self._crop_overlay:
            rect = self._crop_overlay.scene_crop_rect()
            if rect.width() < 10 or rect.height() < 10:
                # Too small, select full image
                if self._target_item:
                    img_rect = self._target_item.sceneBoundingRect()
                    self._crop_overlay.set_crop_rect(img_rect)
        
        self.api.show_status_message(
            "Drag edges to adjust crop region. Press C or right-click to crop.",
            4000
        )
        
        return True
    
    def _on_key_press(self, event):
        """Handle key press in crop mode."""
        if not self._crop_mode_active:
            return False
        
        key = event.key()
        
        # C key - apply crop
        if key == Qt.Key.Key_C:
            if self._crop_overlay and self._target_item:
                self.apply_crop()
                return True
        
        # Escape key - cancel crop
        if key == Qt.Key.Key_Escape:
            self.deactivate_crop_mode()
            self.api.show_status_message("Crop cancelled", 2000)
            return True
        
        return False
    
    def _show_crop_context_menu(self, screen_pos):
        """Show context menu with crop option."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu()
        
        crop_action = QAction("Crop to Selection", menu)
        crop_action.triggered.connect(self.apply_crop)
        menu.addAction(crop_action)
        
        cancel_action = QAction("Cancel Crop", menu)
        cancel_action.triggered.connect(self.deactivate_crop_mode)
        menu.addAction(cancel_action)
        
        # screen_pos may be QPoint or QPointF depending on PyQt6 version
        if hasattr(screen_pos, 'toPoint'):
            menu.exec(screen_pos.toPoint())
        else:
            menu.exec(screen_pos)
    
    def apply_crop(self):
        """Apply the crop to the target image."""
        if not self._crop_overlay or not self._target_item:
            self.api.show_status_message("No crop region selected", 2000)
            self.deactivate_crop_mode()
            return
        
        if not self.api.is_raster_item(self._target_item):
            self.api.show_status_message("Can only crop raster images", 2000)
            self.deactivate_crop_mode()
            return
        
        # Get crop rectangle in scene coordinates
        crop_scene_rect = self._crop_overlay.scene_crop_rect()
        
        # Convert to target item's local coordinates
        item_pos = self._target_item.scenePos()
        local_rect = QRectF(
            crop_scene_rect.x() - item_pos.x(),
            crop_scene_rect.y() - item_pos.y(),
            crop_scene_rect.width(),
            crop_scene_rect.height()
        )
        
        # Get current pixmap
        old_pixmap = self._target_item.pixmap()
        
        # Validate crop rect against image bounds
        img_rect = QRectF(0, 0, old_pixmap.width(), old_pixmap.height())
        local_rect = local_rect.intersected(img_rect)
        
        if local_rect.isEmpty() or local_rect.width() < 1 or local_rect.height() < 1:
            self.api.show_status_message("Invalid crop region", 2000)
            self.deactivate_crop_mode()
            return
        
        # Perform the crop
        cropped_image = old_pixmap.toImage().copy(local_rect.toRect())
        new_pixmap = QPixmap.fromImage(cropped_image)
        
        # Calculate new position (crop rect's top-left in scene coords)
        old_pos = self._target_item.pos()
        new_pos = QPointF(item_pos.x() + local_rect.x(), item_pos.y() + local_rect.y())
        
        # Create undoable action
        action = CropAction(
            self._target_item,
            old_pixmap,
            new_pixmap,
            old_pos,
            new_pos
        )
        
        # Execute with undo support
        self.api.push_undoable(action)
        action.execute()
        
        crop_width = int(local_rect.width())
        crop_height = int(local_rect.height())
        
        # Clean up
        self.deactivate_crop_mode()
        
        self.api.show_status_message(
            f"Cropped image to {crop_width}x{crop_height} pixels (Ctrl+Z to undo)",
            3000
        )


class CropAction:
    """Undoable crop action."""
    
    def __init__(self, item, old_pixmap: QPixmap, new_pixmap: QPixmap,
                 old_pos: QPointF, new_pos: QPointF):
        self.description = "Crop Image"
        self.item = item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.old_pos = old_pos
        self.new_pos = new_pos
    
    def execute(self):
        """Apply the crop."""
        self.item.setPixmap(self.new_pixmap)
        self.item.setPos(self.new_pos)
        if hasattr(self.item, 'updateImageBytes'):
            self.item.updateImageBytes()
        # Update transform origin for the new size
        self.item.setTransformOriginPoint(
            self.new_pixmap.width() / 2,
            self.new_pixmap.height() / 2
        )
    
    def undo(self):
        """Restore original image."""
        self.item.setPixmap(self.old_pixmap)
        self.item.setPos(self.old_pos)
        if hasattr(self.item, 'updateImageBytes'):
            self.item.updateImageBytes()
        # Restore transform origin
        self.item.setTransformOriginPoint(
            self.old_pixmap.width() / 2,
            self.old_pixmap.height() / 2
        )
