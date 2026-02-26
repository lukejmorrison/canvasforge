"""
CanvasForge Undo/Redo System

Provides comprehensive undo/redo functionality that works consistently
across the entire application for every image edit.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Callable
from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtCore import QPointF, pyqtSignal, QObject


class UndoableAction(ABC):
    """Base class for all undoable actions."""
    
    def __init__(self, description: str):
        self.description = description
        self.timestamp = time.time()
    
    @abstractmethod
    def execute(self) -> None:
        """Perform the action."""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """Reverse the action."""
        pass


class ActionGroup(UndoableAction):
    """Group of actions that undo/redo together."""
    
    def __init__(self, description: str):
        super().__init__(description)
        self.actions: List[UndoableAction] = []
    
    def add(self, action: UndoableAction) -> None:
        self.actions.append(action)
    
    def execute(self) -> None:
        for action in self.actions:
            action.execute()
    
    def undo(self) -> None:
        for action in reversed(self.actions):
            action.undo()


class UndoManager(QObject):
    """Global undo/redo manager for all operations."""
    
    # Signals for UI updates
    undoAvailableChanged = pyqtSignal(bool)
    redoAvailableChanged = pyqtSignal(bool)
    undoDescriptionChanged = pyqtSignal(str)
    redoDescriptionChanged = pyqtSignal(str)
    
    def __init__(self, max_history: int = 100):
        super().__init__()
        self._undo_stack: List[UndoableAction] = []
        self._redo_stack: List[UndoableAction] = []
        self._max_history = max_history
        self._group_stack: List[ActionGroup] = []
    
    def execute(self, action: UndoableAction) -> None:
        """Execute an action and add to undo stack."""
        action.execute()
        
        # If we're in a group, add to group instead
        if self._group_stack:
            self._group_stack[-1].add(action)
        else:
            self._undo_stack.append(action)
            self._redo_stack.clear()
            self._trim_history()
            self._emit_state_changed()
    
    def push(self, action: UndoableAction) -> None:
        """Add an already-executed action to undo stack."""
        if self._group_stack:
            self._group_stack[-1].add(action)
        else:
            self._undo_stack.append(action)
            self._redo_stack.clear()
            self._trim_history()
            self._emit_state_changed()
    
    def undo(self) -> bool:
        """Undo the last action. Returns True if successful."""
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        action.undo()
        self._redo_stack.append(action)
        self._emit_state_changed()
        return True
    
    def redo(self) -> bool:
        """Redo the last undone action. Returns True if successful."""
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        action.execute()
        self._undo_stack.append(action)
        self._emit_state_changed()
        return True
    
    def begin_group(self, name: str) -> None:
        """Begin a compound action group."""
        self._group_stack.append(ActionGroup(name))
    
    def end_group(self) -> None:
        """End compound action group and add to undo stack."""
        if self._group_stack:
            group = self._group_stack.pop()
            if group.actions:
                self._undo_stack.append(group)
                self._redo_stack.clear()
                self._trim_history()
                self._emit_state_changed()
    
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0
    
    def undo_description(self) -> str:
        """Get description of next undo action."""
        return self._undo_stack[-1].description if self._undo_stack else ""
    
    def redo_description(self) -> str:
        """Get description of next redo action."""
        return self._redo_stack[-1].description if self._redo_stack else ""
    
    def clear(self) -> None:
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._group_stack.clear()
        self._emit_state_changed()
    
    def _trim_history(self) -> None:
        """Remove oldest actions if over limit."""
        while len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
    
    def _emit_state_changed(self) -> None:
        """Emit signals for UI updates."""
        self.undoAvailableChanged.emit(self.can_undo())
        self.redoAvailableChanged.emit(self.can_redo())
        self.undoDescriptionChanged.emit(self.undo_description())
        self.redoDescriptionChanged.emit(self.redo_description())


# ============================================================================
# Built-in Action Types
# ============================================================================

class AddItemAction(UndoableAction):
    """Undo/redo adding an item to the scene."""
    
    def __init__(self, scene, item, layer_list, item_name: str = "item"):
        super().__init__(f"Add {item_name}")
        self.scene = scene
        self.item = item
        self.layer_list = layer_list
        self._layer_item = None
    
    def execute(self) -> None:
        if self.item.scene() != self.scene:
            self.scene.addItem(self.item)
    
    def undo(self) -> None:
        if self.item.scene() == self.scene:
            self.scene.removeItem(self.item)
            # Also remove from layer list
            self.layer_list.remove_graphics_items([self.item])


class RemoveItemAction(UndoableAction):
    """Undo/redo removing an item from the scene."""
    
    def __init__(self, scene, item, layer_list, item_name: str = "item"):
        super().__init__(f"Delete {item_name}")
        self.scene = scene
        self.item = item
        self.layer_list = layer_list
        self._position = item.pos()
        self._z_value = item.zValue()
    
    def execute(self) -> None:
        if self.item.scene() == self.scene:
            self.scene.removeItem(self.item)
            self.layer_list.remove_graphics_items([self.item])
    
    def undo(self) -> None:
        if self.item.scene() != self.scene:
            self.scene.addItem(self.item)
            self.item.setPos(self._position)
            self.item.setZValue(self._z_value)


class MoveItemAction(UndoableAction):
    """Undo/redo item movement."""
    
    def __init__(self, item, old_pos: QPointF, new_pos: QPointF):
        super().__init__("Move")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos
    
    def execute(self) -> None:
        self.item.setPos(self.new_pos)
    
    def undo(self) -> None:
        self.item.setPos(self.old_pos)


class TransformItemAction(UndoableAction):
    """Undo/redo item transformations (rotation, scale)."""
    
    def __init__(self, item, old_rotation: float, old_scale: float,
                 new_rotation: float, new_scale: float, description: str = "Transform"):
        super().__init__(description)
        self.item = item
        self.old_rotation = old_rotation
        self.old_scale = old_scale
        self.new_rotation = new_rotation
        self.new_scale = new_scale
    
    def execute(self) -> None:
        self.item.setRotation(self.new_rotation)
        self.item.setScale(self.new_scale)
    
    def undo(self) -> None:
        self.item.setRotation(self.old_rotation)
        self.item.setScale(self.old_scale)


class ImageEditAction(UndoableAction):
    """Undo/redo image pixel edits (crop, filter, etc.)."""
    
    def __init__(self, item, old_pixmap: QPixmap, new_pixmap: QPixmap, description: str):
        super().__init__(description)
        self.item = item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
    
    def execute(self) -> None:
        self.item.setPixmap(self.new_pixmap)
        if hasattr(self.item, 'updateImageBytes'):
            self.item.updateImageBytes()
    
    def undo(self) -> None:
        self.item.setPixmap(self.old_pixmap)
        if hasattr(self.item, 'updateImageBytes'):
            self.item.updateImageBytes()


class PropertyChangeAction(UndoableAction):
    """Undo/redo any property change."""
    
    def __init__(self, obj, property_name: str, old_value: Any, new_value: Any):
        super().__init__(f"Change {property_name}")
        self.obj = obj
        self.property_name = property_name
        self.old_value = old_value
        self.new_value = new_value
    
    def execute(self) -> None:
        setattr(self.obj, self.property_name, self.new_value)
    
    def undo(self) -> None:
        setattr(self.obj, self.property_name, self.old_value)


class CallbackAction(UndoableAction):
    """Undo/redo using callbacks for custom behavior."""
    
    def __init__(self, description: str, do_callback: Callable, undo_callback: Callable):
        super().__init__(description)
        self._do = do_callback
        self._undo = undo_callback
    
    def execute(self) -> None:
        self._do()
    
    def undo(self) -> None:
        self._undo()
