"""
CanvasForge Plugin System

Provides plugin loading, management, and the Plugin API for extending
CanvasForge functionality.
"""

import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QIcon, QPixmap, QAction

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QGraphicsItem
    from undo_manager import UndoManager


@dataclass
class PluginManifest:
    """Plugin metadata from manifest.json"""
    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = ""
    entry_point: str = "plugin.py"
    icon: str = ""
    min_canvasforge_version: str = "1.0.0"
    permissions: List[str] = field(default_factory=list)
    pip_dependencies: List[str] = field(default_factory=list)
    hooks: Dict[str, str] = field(default_factory=dict)
    toolbar_items: List[Dict[str, str]] = field(default_factory=list)
    menu_items: List[Dict[str, str]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginManifest':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', 'Unknown Plugin'),
            version=data.get('version', '1.0.0'),
            description=data.get('description', ''),
            author=data.get('author', ''),
            license=data.get('license', ''),
            entry_point=data.get('entry_point', 'plugin.py'),
            icon=data.get('icon', ''),
            min_canvasforge_version=data.get('min_canvasforge_version', '1.0.0'),
            permissions=data.get('permissions', []),
            pip_dependencies=data.get('pip_dependencies', []),
            hooks=data.get('hooks', {}),
            toolbar_items=data.get('toolbar_items', []),
            menu_items=data.get('menu_items', []),
        )


@dataclass
class LoadedPlugin:
    """Runtime state for a loaded plugin."""
    manifest: PluginManifest
    path: Path
    module: Any = None
    instance: Any = None
    enabled: bool = True
    error: Optional[str] = None


class PluginAPI:
    """
    API exposed to plugins for interacting with CanvasForge.
    
    This class provides a controlled interface for plugins to access
    CanvasForge functionality without direct access to internal objects.
    """
    
    def __init__(self, main_window, undo_manager: 'UndoManager', plugin_id: str = "unknown"):
        self._main_window = main_window
        self._scene = main_window.scene
        self._view = main_window.view
        self._layer_list = main_window.layer_list
        self._undo_manager = undo_manager
        self._settings = QSettings("CanvasForge", "Plugins")
        self._registered_actions: List[QAction] = []
        self._plugin_id = plugin_id
    
    # ========================================================================
    # Item Access
    # ========================================================================
    
    def get_selected_items(self) -> List[Any]:
        """Get all currently selected items."""
        layer_items = set(self._layer_list.graphics_items())
        return [item for item in self._scene.selectedItems() if item in layer_items]
    
    def get_all_items(self) -> List[Any]:
        """Get all items in the layer list."""
        return self._layer_list.graphics_items()
    
    def get_item_by_index(self, index: int) -> Optional[Any]:
        """Get an item by its layer index."""
        items = self._layer_list.graphics_items()
        if 0 <= index < len(items):
            return items[index]
        return None
    
    def select_item(self, item) -> None:
        """Select a specific item."""
        self._scene.clearSelection()
        item.setSelected(True)
    
    def clear_selection(self) -> None:
        """Clear all selections."""
        self._scene.clearSelection()
    
    # ========================================================================
    # Item Properties
    # ========================================================================
    
    def get_item_pixmap(self, item) -> Optional[QPixmap]:
        """Get the pixmap from a raster item."""
        if hasattr(item, 'pixmap'):
            return item.pixmap()
        return None
    
    def set_item_pixmap(self, item, pixmap: QPixmap) -> None:
        """Set the pixmap on a raster item."""
        if hasattr(item, 'setPixmap'):
            item.setPixmap(pixmap)
            if hasattr(item, 'updateImageBytes'):
                item.updateImageBytes()
    
    def get_item_position(self, item) -> tuple:
        """Get item position as (x, y) tuple."""
        pos = item.pos()
        return (pos.x(), pos.y())
    
    def set_item_position(self, item, x: float, y: float) -> None:
        """Set item position."""
        from PyQt6.QtCore import QPointF
        item.setPos(QPointF(x, y))
    
    def get_item_rotation(self, item) -> float:
        """Get item rotation in degrees."""
        return item.rotation()
    
    def set_item_rotation(self, item, degrees: float) -> None:
        """Set item rotation in degrees."""
        item.setRotation(degrees)
    
    def get_item_scale(self, item) -> float:
        """Get item scale factor."""
        return item.scale()
    
    def set_item_scale(self, item, scale: float) -> None:
        """Set item scale factor."""
        item.setScale(scale)
    
    def is_raster_item(self, item) -> bool:
        """Check if item is a raster (pixmap) item."""
        return hasattr(item, 'pixmap') and hasattr(item, 'setPixmap')
    
    # ========================================================================
    # Scene Operations
    # ========================================================================
    
    def add_item(self, item) -> None:
        """Add an item to the canvas."""
        self._view.itemAdded.emit(item)
    
    def delete_items(self, items: List[Any]) -> None:
        """Delete items from the canvas."""
        self._main_window._remove_items(items)
    
    def refresh_scene(self) -> None:
        """Force scene redraw."""
        self._scene.update()
    
    # ========================================================================
    # Undo/Redo
    # ========================================================================
    
    def execute_undoable(self, action) -> None:
        """Execute an action that can be undone."""
        self._undo_manager.execute(action)
    
    def push_undoable(self, action) -> None:
        """Add an already-executed action to undo stack."""
        self._undo_manager.push(action)
    
    def begin_undo_group(self, name: str) -> None:
        """Begin a group of actions that undo together."""
        self._undo_manager.begin_group(name)
    
    def end_undo_group(self) -> None:
        """End the current undo group."""
        self._undo_manager.end_group()
    
    def create_image_edit_action(self, item, old_pixmap: QPixmap, 
                                  new_pixmap: QPixmap, description: str):
        """Create an undoable image edit action."""
        from undo_manager import ImageEditAction
        return ImageEditAction(item, old_pixmap, new_pixmap, description)
    
    # ========================================================================
    # Plugin Settings
    # ========================================================================
    
    def get_setting(self, plugin_id: str, key: str, default=None):
        """Get a plugin setting."""
        return self._settings.value(f"{plugin_id}/{key}", default)
    
    def set_setting(self, plugin_id: str, key: str, value) -> None:
        """Set a plugin setting."""
        self._settings.setValue(f"{plugin_id}/{key}", value)
    
    # ========================================================================
    # UI Registration
    # ========================================================================
    
    def register_toolbar_action(self, text: str, callback: Callable,
                                 icon_path: Optional[str] = None,
                                 shortcut: Optional[str] = None) -> QAction:
        """Register a toolbar action."""
        action = QAction(text, self._main_window)
        
        # Calculate canonical resource name for theming
        # e.g. "Crop Selection" -> "toolbar_icon_crop_selection"
        resource_name = f"toolbar_icon_{text.lower().replace(' ', '_')}"
        
        # Determine strict icon priority:
        # 1. Active Theme (if not default)
        # 2. Plugin's local icon (icon_path)
        # 3. Global default / Fallback (via get_icon_resource)
        
        icon_set = False
        
        # 1. Check Theme
        if hasattr(self._main_window, 'settings'):
            theme = self._main_window.settings.value("appearance/icon_theme", "default")
            if theme != "default":
                # We need to construct the path to check existence
                # Assuming assets structure is standard relative to main window or we use pathlib
                base_dir = Path(self._main_window.default_save_dir).parent.parent / "dev" / "CanvasForge" / "assets" / "toolbar_icons"
                # Fallback to standard relative path if the above hardcoded dev path is risky
                # Better: use __file__ of main module? We don't have access to it directly here easily 
                # but we can assume PluginManager is intantiated with knowledge or search.
                # Actually, relying on main_window.get_icon_resource is safer if we can trust it.
                # But get_icon_resource falls back to global default.
                
                # Let's try to query get_icon_resource but only accept if it matches the theme path?
                # No, get_icon_resource returns a QIcon, hard to inspect.
                
                # Let's perform a manual check similar to MainWindow logic
                # We can access MainWindow class path via the instance?
                import sys
                main_mod = sys.modules.get('__main__')
                if main_mod and hasattr(main_mod, '__file__'):
                    base_dir = Path(main_mod.__file__).parent / "assets" / "toolbar_icons"
                    theme_dir = base_dir / theme
                    
                    if theme_dir.exists():
                        # prioritized SVG
                        if (theme_dir / f"{resource_name}.svg").exists():
                            action.setIcon(QIcon(str(theme_dir / f"{resource_name}.svg")))
                            icon_set = True
                        elif (theme_dir / f"{resource_name}.png").exists():
                            action.setIcon(QIcon(str(theme_dir / f"{resource_name}.png")))
                            icon_set = True

        # 2. Check Plugin Local
        if not icon_set and icon_path and os.path.exists(icon_path):
            action.setIcon(QIcon(icon_path))
            icon_set = True
            
        # 3. Fallback to Global / Placeholder
        if not icon_set and hasattr(self._main_window, 'get_icon_resource'):
            action.setIcon(self._main_window.get_icon_resource(resource_name))

        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        
        # Use the new plugin toolbar registration system
        action_id = f"plugin_{self._plugin_id}_{text.lower().replace(' ', '_')}"
        if hasattr(self._main_window, 'register_plugin_toolbar_action'):
            # Pass resource_name (e.g. "toolbar_icon_crop") so Preferences knows what file to save to
            self._main_window.register_plugin_toolbar_action(action_id, action, resource_name)
        else:
            self._main_window.toolbar.addAction(action)
        
        self._registered_actions.append(action)
        return action
    
    def register_menu_action(self, menu_name: str, text: str, callback: Callable,
                              shortcut: Optional[str] = None) -> QAction:
        """Register a menu action."""
        # Find or create the menu
        menu_bar = self._main_window.menuBar()
        target_menu = None
        for action in menu_bar.actions():
            if action.text() == menu_name:
                target_menu = action.menu()
                break
        
        if not target_menu:
            target_menu = menu_bar.addMenu(menu_name)
        
        action = QAction(text, self._main_window)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        target_menu.addAction(action)
        self._registered_actions.append(action)
        return action
    
    def show_status_message(self, message: str, timeout_ms: int = 4000) -> None:
        """Show a message in the status bar."""
        self._main_window._status_bar.showMessage(message, timeout_ms)
    
    # ========================================================================
    # View Event Handling (for tool plugins)
    # ========================================================================
    
    def set_active_tool_plugin(self, plugin_instance) -> None:
        """Set this plugin as the active tool (receives mouse events)."""
        self._main_window.set_active_plugin_tool(plugin_instance)
    
    def clear_active_tool_plugin(self) -> None:
        """Clear the active tool plugin."""
        self._main_window.set_active_plugin_tool(None)
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    def cleanup(self) -> None:
        """Remove all registered actions (called on plugin unload)."""
        for action in self._registered_actions:
            # Remove from toolbar
            self._main_window.toolbar.removeAction(action)
            # Remove from any menus
            for menu_action in self._main_window.menuBar().actions():
                menu = menu_action.menu()
                if menu:
                    menu.removeAction(action)
        self._registered_actions.clear()
        # Clear tool plugin if this was active
        self._main_window.set_active_plugin_tool(None)


class PluginManager(QObject):
    """
    Manages plugin discovery, loading, and lifecycle.
    """
    
    pluginLoaded = pyqtSignal(str)  # plugin_id
    pluginUnloaded = pyqtSignal(str)  # plugin_id
    pluginError = pyqtSignal(str, str)  # plugin_id, error_message
    
    def __init__(self, main_window, undo_manager: 'UndoManager'):
        super().__init__()
        self._main_window = main_window
        self._undo_manager = undo_manager
        self._plugins: Dict[str, LoadedPlugin] = {}
        self._plugin_apis: Dict[str, PluginAPI] = {}
        self._settings = QSettings("CanvasForge", "Plugins")
        
        # Plugin directories
        self._user_plugin_dir = Path.home() / ".canvasforge" / "plugins"
        self._builtin_plugin_dir = Path(__file__).parent / "plugins"
        
        # Ensure directories exist
        self._user_plugin_dir.mkdir(parents=True, exist_ok=True)
        self._builtin_plugin_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def user_plugin_dir(self) -> Path:
        return self._user_plugin_dir
    
    @property
    def builtin_plugin_dir(self) -> Path:
        return self._builtin_plugin_dir
    
    def discover_plugins(self) -> List[PluginManifest]:
        """Scan plugin directories for available plugins."""
        manifests = []
        
        for plugin_dir in [self._builtin_plugin_dir, self._user_plugin_dir]:
            if not plugin_dir.exists():
                continue
            
            for item in plugin_dir.iterdir():
                if item.is_dir():
                    manifest_path = item / "manifest.json"
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, 'r') as f:
                                data = json.load(f)
                            manifest = PluginManifest.from_dict(data)
                            manifests.append(manifest)
                        except Exception as e:
                            print(f"Error reading manifest from {item}: {e}")
        
        return manifests
    
    def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin by ID."""
        if plugin_id in self._plugins:
            return True  # Already loaded
        
        # Find the plugin directory
        plugin_path = None
        for plugin_dir in [self._builtin_plugin_dir, self._user_plugin_dir]:
            candidate = plugin_dir / plugin_id
            if candidate.exists() and (candidate / "manifest.json").exists():
                plugin_path = candidate
                break
        
        if not plugin_path:
            self.pluginError.emit(plugin_id, f"Plugin directory not found: {plugin_id}")
            return False
        
        try:
            # Load manifest
            with open(plugin_path / "manifest.json", 'r') as f:
                manifest = PluginManifest.from_dict(json.load(f))
            
            # Check if disabled in settings
            enabled = self._settings.value(f"{plugin_id}/enabled", True, type=bool)
            
            # Create LoadedPlugin entry
            loaded = LoadedPlugin(
                manifest=manifest,
                path=plugin_path,
                enabled=enabled
            )
            
            if not enabled:
                self._plugins[plugin_id] = loaded
                return True
            
            # Load the Python module
            entry_file = plugin_path / manifest.entry_point
            if not entry_file.exists():
                loaded.error = f"Entry point not found: {manifest.entry_point}"
                self._plugins[plugin_id] = loaded
                self.pluginError.emit(plugin_id, loaded.error)
                return False
            
            # Import the module
            spec = importlib.util.spec_from_file_location(
                f"canvasforge_plugin_{plugin_id}",
                entry_file
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            loaded.module = module
            
            # Create API instance for this plugin
            api = PluginAPI(self._main_window, self._undo_manager, plugin_id)
            self._plugin_apis[plugin_id] = api
            
            # Instantiate plugin class if defined
            if hasattr(module, 'Plugin'):
                loaded.instance = module.Plugin(api)
                
                # Call on_load hook if defined
                if hasattr(loaded.instance, 'on_load'):
                    loaded.instance.on_load()
            
            # Register toolbar items from manifest
            for item in manifest.toolbar_items:
                if hasattr(loaded.instance, item.get('callback', '')):
                    callback = getattr(loaded.instance, item['callback'])
                    icon_path = None
                    if item.get('icon'):
                        # Try to find the icon file, supporting both png and svg
                        base_icon_name = Path(item['icon']).stem
                        potential_paths = [
                            plugin_path / f"{base_icon_name}.svg",
                            plugin_path / f"{base_icon_name}.png",
                            plugin_path / item['icon']
                        ]
                        
                        for p in potential_paths:
                            if p.exists():
                                icon_path = str(p)
                                break
                                
                    api.register_toolbar_action(
                        item.get('text', 'Action'),
                        callback,
                        icon_path,
                        item.get('shortcut')
                    )
            
            # Register menu items from manifest
            for item in manifest.menu_items:
                callback_name = item.get('callback', '')
                if hasattr(loaded.instance, callback_name):
                    callback = getattr(loaded.instance, callback_name)
                    api.register_menu_action(
                        item.get('menu', 'Plugins'),
                        item.get('text', 'Action'),
                        callback,
                        item.get('shortcut')
                    )
            
            self._plugins[plugin_id] = loaded
            self.pluginLoaded.emit(plugin_id)
            return True
            
        except Exception as e:
            error_msg = f"Failed to load plugin: {str(e)}"
            self.pluginError.emit(plugin_id, error_msg)
            if plugin_id in self._plugins:
                self._plugins[plugin_id].error = error_msg
            return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        loaded = self._plugins[plugin_id]
        
        try:
            # Call on_unload hook
            if loaded.instance and hasattr(loaded.instance, 'on_unload'):
                loaded.instance.on_unload()
            
            # Cleanup API (remove registered actions)
            if plugin_id in self._plugin_apis:
                self._plugin_apis[plugin_id].cleanup()
                del self._plugin_apis[plugin_id]
            
            # Remove from sys.modules
            module_name = f"canvasforge_plugin_{plugin_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            del self._plugins[plugin_id]
            self.pluginUnloaded.emit(plugin_id)
            return True
            
        except Exception as e:
            self.pluginError.emit(plugin_id, f"Error unloading: {str(e)}")
            return False
    
    def reload_plugin(self, plugin_id: str) -> bool:
        """Reload a plugin (unload then load)."""
        self.unload_plugin(plugin_id)
        return self.load_plugin(plugin_id)
    
    def enable_plugin(self, plugin_id: str, enabled: bool) -> None:
        """Enable or disable a plugin."""
        self._settings.setValue(f"{plugin_id}/enabled", enabled)
        
        if plugin_id in self._plugins:
            self._plugins[plugin_id].enabled = enabled
            
            if enabled:
                self.reload_plugin(plugin_id)
            else:
                self.unload_plugin(plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[LoadedPlugin]:
        """Get a loaded plugin by ID."""
        return self._plugins.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, LoadedPlugin]:
        """Get all loaded plugins."""
        return self._plugins.copy()
    
    def load_all_plugins(self) -> None:
        """Load all discovered plugins."""
        for manifest in self.discover_plugins():
            self.load_plugin(manifest.id)
    
    def get_plugin_api(self, plugin_id: str) -> Optional[PluginAPI]:
        """Get the API instance for a plugin."""
        return self._plugin_apis.get(plugin_id)
