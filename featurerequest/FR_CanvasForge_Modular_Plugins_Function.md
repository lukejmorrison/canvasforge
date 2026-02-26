# Feature Request: CanvasForge Modular Plugin System

## Document Metadata

| Field | Value |
| --- | --- |
| Doc ID | FR-20251209-PluginSystem |
| Version | v2.0 |
| Date | 2025-12-09 |
| Owner / Author | Luke Morrison |
| Status | 📋 Design Complete - Ready for Phase 1 |
| Priority | High |
| Related Files | TBD |

---

## Executive Summary

Implement a modular plugin architecture that allows users to view, edit, and create plugins directly within CanvasForge. Plugins will be Python scripts that users can modify in real-time, share with others, and extend the application's functionality without modifying core code.

The first plugin to deploy using this system will be **Crop** - demonstrating the full plugin lifecycle from installation to customization.

---

## Goals

1. **Transparency**: Users can see the actual code powering each feature
2. **Customizability**: Edit plugin code via the app or external editors (VS Code, etc.)
3. **Real-time Updates**: Changes to plugin code take effect immediately without restart
4. **Shareability**: Package and share plugins with other users
5. **Community**: GitHub-based plugin repository and user discussion forum
6. **Future Extensibility**: Framework supports multi-language plugins eventually

---

## Decisions Made

### 🟢 Confirmed Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Editor Integration | Configurable via UI | Users set their preferred editor in Preferences |
| Built-in Plugins | Editable but recoverable | Core tools are plugins, can reset to defaults |
| Multi-language | Python-only initially | Framework designed for future expansion |
| Core Tools as Plugins | Yes, but "locked by default" | Prevents accidental breakage |

---

## Plugin API Scope

### API Categories for Phase 1 (MVP)

Based on analysis of standard image editing features, plugins need access to:

#### 1. Scene API (`canvasforge.scene`)

| Method | Description | Used By |
| --- | --- | --- |
| `scene.get_items()` | List all items on canvas | All tools |
| `scene.get_selected_items()` | Get currently selected items | Crop, Transform, Effects |
| `scene.add_item(item)` | Add new item to canvas | Import, Generate |
| `scene.remove_item(item)` | Remove item from canvas | Delete, Merge |
| `scene.clear_selection()` | Deselect all | Tools switching |
| `scene.select_items(items)` | Select specific items | Multi-select operations |

#### 2. Item API (`canvasforge.item`)

| Method | Description | Used By |
| --- | --- | --- |
| `item.get_pixmap()` | Get QPixmap of raster item | Crop, Effects, AI Edit |
| `item.set_pixmap(pixmap)` | Replace item's image data | Crop, Effects, AI Edit |
| `item.get_bounds()` | Get bounding rectangle | Crop, Resize |
| `item.set_bounds(rect)` | Set position/size | Transform |
| `item.get_transform()` | Get rotation/scale/position | Transform |
| `item.set_transform(transform)` | Apply transformation | Rotate, Scale |
| `item.clone()` | Create copy of item | Duplicate |
| `item.get_type()` | Returns 'raster', 'vector', 'text', 'shape' | Type-specific operations |

#### 3. Toolbar/Menu API (`canvasforge.ui`)

| Method | Description | Used By |
| --- | --- | --- |
| `ui.register_tool(tool)` | Add tool to toolbar | All tool plugins |
| `ui.register_menu_item(menu, item)` | Add menu item | Effects, Export |
| `ui.register_context_menu(item)` | Add right-click option | Quick actions |
| `ui.set_cursor(cursor)` | Change mouse cursor | Crop, Draw |
| `ui.show_dialog(dialog)` | Display modal dialog | Settings, AI prompts |
| `ui.show_toast(message)` | Show status message | Feedback |

#### 4. Settings API (`canvasforge.settings`)

| Method | Description | Used By |
| --- | --- | --- |
| `settings.get(key, default)` | Read plugin setting | All plugins |
| `settings.set(key, value)` | Save plugin setting | All plugins |
| `settings.get_plugin_dir()` | Get plugin's data directory | Caching, temp files |

#### 5. Undo/Redo API (`canvasforge.history`)

| Method | Description | Used By |
| --- | --- | --- |
| `history.begin_macro(name)` | Start undoable operation | Crop, Effects, AI Edit |
| `history.end_macro()` | Complete undoable operation | All destructive operations |
| `history.push(command)` | Add undoable command | Fine-grained undo |

#### 6. Image Processing API (`canvasforge.image`)

| Method | Description | Used By |
| --- | --- | --- |
| `image.to_pil(pixmap)` | Convert QPixmap to PIL Image | AI plugins, Effects |
| `image.from_pil(pil_image)` | Convert PIL Image to QPixmap | AI plugins, Effects |
| `image.to_numpy(pixmap)` | Convert to numpy array | Advanced processing |
| `image.from_numpy(array)` | Convert numpy to QPixmap | Advanced processing |
| `image.crop(pixmap, rect)` | Crop image | Crop tool |
| `image.resize(pixmap, size)` | Resize image | Resize tool |

---

## Preferences > Plugins Tab Design

### Layout Wireframe

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Plugins                                                                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ External Editor                                                          │
│ ┌────────────────────────────────────────────────────────────────────┐  │
│ │ Editor Command: [code --wait %FILE%                          ] [📁] │  │
│ │                                                                     │  │
│ │ ℹ️ Use %FILE% as placeholder for the file path                     │  │
│ │   Examples: "code --wait %FILE%", "gedit %FILE%", "vim %FILE%"     │  │
│ └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ Installed Plugins                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐  │
│ │ ☑ 🔧 Crop Tool                  v1.0.0  [Core]    ⚙️ 📝 🗑️        │  │
│ │     Crop selected images to a rectangular region                   │  │
│ │ ────────────────────────────────────────────────────────────────── │  │
│ │ ☑ 🔧 Transform Tools            v1.0.0  [Core]    ⚙️ 📝           │  │
│ │     Move, rotate, scale selected items                            │  │
│ │ ────────────────────────────────────────────────────────────────── │  │
│ │ ☑ 🎨 Basic Shapes               v1.0.0  [Core]    ⚙️ 📝           │  │
│ │     Rectangle, ellipse, text tools                                │  │
│ │ ────────────────────────────────────────────────────────────────── │  │
│ │ ☐ 🤖 AI Image Edit              v0.1.0  [User]    ⚙️ 📝 🗑️        │  │
│ │     Edit images using Qwen-Image AI                               │  │
│ │ ────────────────────────────────────────────────────────────────── │  │
│ │ ☑ ✂️ Selection to Clipboard     v1.0.0  [User]    ⚙️ 📝 🗑️        │  │
│ │     Copy selected region to system clipboard                      │  │
│ └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ Legend: ⚙️=Settings  📝=Edit Code  🗑️=Delete (user plugins only)        │
│                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ [Install from ZIP...]  [Open Plugins Folder]  [Refresh]  [New...] ││
│ └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│ Selected: Crop Tool                                                      │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ Plugin Details                                                        ││
│ │ ─────────────────────────────────────────────────────────────────── ││
│ │ Name:       Crop Tool                                               ││
│ │ Version:    1.0.0                                                   ││
│ │ Author:     CanvasForge Team                                        ││
│ │ Type:       Core (built-in)                                         ││
│ │ Status:     ✅ Enabled                                              ││
│ │ Location:   ~/.canvasforge/plugins/crop/                            ││
│ │                                                                     ││
│ │ Files:                                                              ││
│ │   📄 manifest.json                              [View]              ││
│ │   📄 __init__.py                                [View] [Edit]       ││
│ │   📄 crop_tool.py                               [View] [Edit]       ││
│ │   🖼️ icon.png                                   [View]              ││
│ │   📄 README.md                                  [View]              ││
│ │                                                                     ││
│ │ [Reset to Default]  [Export as ZIP]  [Open in Editor]              ││
│ └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ Code Preview (crop_tool.py)                            [▼ Expand]   ││
│ │ ┌────────────────────────────────────────────────────────────────┐ ││
│ │ │ 1  from canvasforge.plugin_api import CanvasForgePlugin       │ ││
│ │ │ 2  from canvasforge.scene import scene                        │ ││
│ │ │ 3  from canvasforge.ui import ui                              │ ││
│ │ │ 4                                                              │ ││
│ │ │ 5  class CropPlugin(CanvasForgePlugin):                        │ ││
│ │ │ 6      """Crop selected items to a rectangular region."""     │ ││
│ │ │ 7                                                              │ ││
│ │ │ 8      def register(self, app):                                │ ││
│ │ │ 9          self.app = app                                      │ ││
│ │ │10          ui.register_tool(                                   │ ││
│ │ │11              name="Crop",                                    │ ││
│ │ │12              icon="crop.png",                                │ ││
│ │ │13              callback=self.activate_crop                     │ ││
│ │ │14          )                                                   │ ││
│ │ │   ...                                                          │ ││
│ │ └────────────────────────────────────────────────────────────────┘ ││
│ └──────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

### Button Functions

| Button | Action |
| --- | --- |
| **Install from ZIP** | File dialog to select .zip, extract to plugins folder, validate manifest |
| **Open Plugins Folder** | Open `~/.canvasforge/plugins/` in system file manager |
| **Refresh** | Rescan plugins folder, reload changed plugins |
| **New...** | Create new plugin from template |
| **Settings (⚙️)** | Open plugin-specific settings dialog |
| **Edit Code (📝)** | Open plugin in external editor (uses configured command) |
| **Delete (🗑️)** | Remove user plugin (with confirmation) |
| **Reset to Default** | Restore core plugin to original code |
| **Export as ZIP** | Package plugin as distributable ZIP |
| **Open in Editor** | Open entire plugin folder in external editor |

---

## Plugin Examples

### Example 1: Crop Tool Plugin

```python
# ~/.canvasforge/plugins/crop/crop_tool.py

from canvasforge.plugin_api import CanvasForgePlugin, ToolPlugin
from canvasforge.scene import scene
from canvasforge.ui import ui
from canvasforge.history import history
from canvasforge.image import image
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QCursor, QPixmap

class CropPlugin(CanvasForgePlugin, ToolPlugin):
    """Crop selected raster items to a rectangular region."""
    
    PLUGIN_ID = "com.canvasforge.crop"
    PLUGIN_NAME = "Crop Tool"
    PLUGIN_VERSION = "1.0.0"
    
    def register(self, app):
        self.app = app
        self.crop_rect = None
        self.target_item = None
        
        # Register as a tool in the toolbar
        ui.register_tool(
            id="crop",
            name="Crop",
            icon=self.get_resource("icon.png"),
            shortcut="C",
            callback=self.activate,
            group="transform"
        )
        
        # Also add to right-click context menu
        ui.register_context_menu(
            id="crop_selected",
            name="Crop Selected",
            callback=self.crop_selection,
            condition=lambda: len(scene.get_selected_items()) == 1
        )
    
    def unregister(self, app):
        ui.unregister_tool("crop")
        ui.unregister_context_menu("crop_selected")
    
    def activate(self):
        """Called when tool is selected from toolbar."""
        selected = scene.get_selected_items()
        if not selected:
            ui.show_toast("Select an image to crop")
            return False
        
        if len(selected) > 1:
            ui.show_toast("Crop works on single items. Select one image.")
            return False
        
        item = selected[0]
        if item.get_type() != 'raster':
            ui.show_toast("Crop only works on raster images")
            return False
        
        self.target_item = item
        ui.set_cursor(Qt.CursorShape.CrossCursor)
        self.show_crop_handles(item)
        return True
    
    def show_crop_handles(self, item):
        """Display the 8-point crop overlay on the item."""
        bounds = item.get_bounds()
        self.crop_rect = CropOverlay(bounds, self.on_crop_complete)
        scene.add_overlay(self.crop_rect)
    
    def on_crop_complete(self, new_rect):
        """Called when user confirms the crop area."""
        if not self.target_item or not new_rect:
            self.cancel()
            return
        
        history.begin_macro("Crop Image")
        
        # Get the pixmap and crop it
        pixmap = self.target_item.get_pixmap()
        cropped = image.crop(pixmap, new_rect)
        
        # Update the item
        self.target_item.set_pixmap(cropped)
        self.target_item.set_bounds(new_rect)
        
        history.end_macro()
        
        self.cleanup()
        ui.show_toast("Image cropped")
    
    def cancel(self):
        """Cancel crop operation."""
        self.cleanup()
        ui.show_toast("Crop cancelled")
    
    def cleanup(self):
        """Remove crop overlay and reset state."""
        if self.crop_rect:
            scene.remove_overlay(self.crop_rect)
            self.crop_rect = None
        self.target_item = None
        ui.set_cursor(Qt.CursorShape.ArrowCursor)


class CropOverlay:
    """Visual overlay showing crop handles and preview."""
    
    def __init__(self, initial_rect, on_complete):
        self.rect = initial_rect
        self.on_complete = on_complete
        self.handles = self._create_handles()
        # ... implementation details ...
```

### Example 2: AI Image Edit Plugin (Qwen-Image Integration)

```python
# ~/.canvasforge/plugins/ai_image_edit/ai_edit.py

from canvasforge.plugin_api import CanvasForgePlugin
from canvasforge.scene import scene
from canvasforge.ui import ui
from canvasforge.history import history
from canvasforge.image import image
from canvasforge.settings import settings
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QProgressBar
import threading

class AIImageEditPlugin(CanvasForgePlugin):
    """Edit images using Qwen-Image AI model."""
    
    PLUGIN_ID = "com.canvasforge.ai_image_edit"
    PLUGIN_NAME = "AI Image Edit"
    PLUGIN_VERSION = "0.1.0"
    
    # Plugin-specific dependencies
    DEPENDENCIES = [
        "diffusers>=0.30.0",
        "transformers>=4.51.3",
        "torch",
        "pillow"
    ]
    
    def register(self, app):
        self.app = app
        self.pipeline = None  # Lazy-load the model
        
        # Add to Edit menu
        ui.register_menu_item(
            menu="Edit",
            id="ai_edit",
            name="AI Image Edit...",
            shortcut="Ctrl+Shift+E",
            callback=self.show_dialog,
            condition=lambda: len(scene.get_selected_items()) == 1
        )
        
        # Also in context menu
        ui.register_context_menu(
            id="ai_edit_context",
            name="Edit with AI...",
            callback=self.show_dialog,
            condition=lambda: self._can_edit_selected()
        )
    
    def unregister(self, app):
        ui.unregister_menu_item("Edit", "ai_edit")
        ui.unregister_context_menu("ai_edit_context")
        self._unload_model()
    
    def _can_edit_selected(self):
        selected = scene.get_selected_items()
        return len(selected) == 1 and selected[0].get_type() == 'raster'
    
    def show_dialog(self):
        """Show the AI edit prompt dialog."""
        selected = scene.get_selected_items()
        if not selected:
            ui.show_toast("Select an image first")
            return
        
        dialog = AIEditDialog(self, selected[0])
        dialog.exec()
    
    def _load_model(self, progress_callback=None):
        """Lazy-load the Qwen-Image-Edit pipeline."""
        if self.pipeline is not None:
            return self.pipeline
        
        try:
            import torch
            from diffusers import QwenImageEditPlusPipeline
            
            if progress_callback:
                progress_callback("Loading Qwen-Image-Edit model...")
            
            model_name = settings.get("ai_edit/model", "Qwen/Qwen-Image-Edit-2509")
            
            self.pipeline = QwenImageEditPlusPipeline.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32
            )
            
            if torch.cuda.is_available():
                self.pipeline.to('cuda')
            
            return self.pipeline
            
        except ImportError as e:
            ui.show_error(
                "Missing Dependencies",
                f"Please install required packages:\n{e}\n\n"
                f"Run: pip install {' '.join(self.DEPENDENCIES)}"
            )
            return None
    
    def _unload_model(self):
        """Free GPU memory."""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def edit_image(self, item, prompt, progress_callback=None):
        """Apply AI edit to the image."""
        pipeline = self._load_model(progress_callback)
        if not pipeline:
            return None
        
        import torch
        
        # Convert item to PIL
        pixmap = item.get_pixmap()
        pil_image = image.to_pil(pixmap)
        
        if progress_callback:
            progress_callback("Generating edited image...")
        
        # Run the AI edit
        inputs = {
            "image": [pil_image],
            "prompt": prompt,
            "generator": torch.manual_seed(0),
            "true_cfg_scale": 4.0,
            "negative_prompt": " ",
            "num_inference_steps": settings.get("ai_edit/steps", 40),
            "guidance_scale": 1.0,
        }
        
        with torch.inference_mode():
            output = pipeline(**inputs)
            result_pil = output.images[0]
        
        # Convert back to QPixmap
        return image.from_pil(result_pil)


class AIEditDialog(QDialog):
    """Dialog for entering AI edit prompts."""
    
    def __init__(self, plugin, target_item):
        super().__init__()
        self.plugin = plugin
        self.target_item = target_item
        self.setWindowTitle("AI Image Edit")
        self.setMinimumWidth(400)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Describe how you want to edit the image:"))
        
        # Prompt input
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Examples:\n"
            "• Change the background to a beach scene\n"
            "• Make the person wear a red hat\n"
            "• Add text saying 'Hello World' at the top"
        )
        self.prompt_edit.setMaximumHeight(100)
        layout.addWidget(self.prompt_edit)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        self.apply_btn = QPushButton("Apply AI Edit")
        self.apply_btn.clicked.connect(self._apply_edit)
        layout.addWidget(self.apply_btn)
    
    def _apply_edit(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            ui.show_toast("Please enter an edit prompt")
            return
        
        self.apply_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate
        
        def run_edit():
            try:
                result = self.plugin.edit_image(
                    self.target_item,
                    prompt,
                    progress_callback=lambda msg: self._update_status(msg)
                )
                
                if result:
                    history.begin_macro("AI Image Edit")
                    self.target_item.set_pixmap(result)
                    history.end_macro()
                    self._finish(success=True)
                else:
                    self._finish(success=False, error="Edit failed")
                    
            except Exception as e:
                self._finish(success=False, error=str(e))
        
        # Run in background thread
        thread = threading.Thread(target=run_edit)
        thread.start()
    
    def _update_status(self, message):
        # Called from worker thread, need to update UI safely
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.status_label, "setText",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, message)
        )
    
    def _finish(self, success, error=None):
        from PyQt6.QtCore import QMetaObject, Qt
        
        def finish_ui():
            self.progress.setVisible(False)
            self.apply_btn.setEnabled(True)
            
            if success:
                ui.show_toast("AI edit applied successfully")
                self.accept()
            else:
                self.status_label.setText(f"Error: {error}")
        
        QMetaObject.invokeMethod(
            self, finish_ui.__name__,
            Qt.ConnectionType.QueuedConnection
        )
```

---

## Multi-Language Framework Design

### Manifest Extension for Language Support

```json
{
  "id": "com.example.native_plugin",
  "name": "Native Filter Plugin",
  "version": "1.0.0",
  "language": "cpp",
  "entry_point": {
    "library": "filter_plugin.so",
    "init_function": "plugin_init",
    "cleanup_function": "plugin_cleanup"
  },
  "api_version": "1.0",
  "platform": {
    "linux": "filter_plugin.so",
    "windows": "filter_plugin.dll",
    "macos": "filter_plugin.dylib"
  }
}
```

### Supported Languages (Future)

| Language | Integration Method | Status |
| --- | --- | --- |
| **Python** | Direct import via importlib | ✅ Phase 1 |
| **JavaScript** | subprocess + JSON-RPC | 🔮 Future |
| **C/C++** | ctypes/cffi FFI | 🔮 Future |
| **Rust** | PyO3 or FFI | 🔮 Future |
| **WASM** | wasmer/wasmtime sandbox | 🔮 Future |

### Python-First Design Principle

For Phase 1, all plugins MUST be Python. The manifest format includes a `language` field defaulting to `"python"`, which allows future expansion without breaking existing plugins.

---

## Open Graphics Plugin Standards Compatibility

### Standards Reviewed

| Standard | Description | Compatibility |
| --- | --- | --- |
| **GIMP Plug-in Protocol** | IPC-based with wire protocol | Partial (can adapt) |
| **OpenFX** | VFX industry standard | Not applicable (video-focused) |
| **8bf (Photoshop Filters)** | Binary filter format | Not compatible |
| **GEGL** | GIMP's graph-based ops | Could wrap with effort |
| **Pillow Plugins** | Image format handlers | Direct Python use |

### Recommended Approach

Rather than implement full compatibility with another standard, CanvasForge should:

1. **Expose PIL/Pillow interop** - Plugins can use any Pillow-compatible image processing
2. **Provide numpy array access** - Enables integration with OpenCV, scikit-image, etc.
3. **Allow subprocess communication** - Plugins can shell out to GIMP/ImageMagick
1.  **Expose PIL/Pillow interop** - Plugins can use any Pillow-compatible image processing
2.  **Provide numpy array access** - Enables integration with OpenCV, scikit-image, etc.
3.  **Allow subprocess communication** - Plugins can shell out to GIMP/ImageMagick

---

## Implementation Phases

### Phase 1: Foundation (MVP) ✅ COMPLETED

- [x] Create `~/.canvasforge/plugins/` directory structure
- [x] Implement `PluginManager` class:
  - [x] `discover_plugins()` - scan for manifest.json files
  - [x] `load_plugin(name)` - import and register plugin
  - [x] `unload_plugin(name)` - cleanup and remove
  - [x] `reload_plugin(name)` - hot-reload modified plugin
- [x] Create `plugin_api.py` (implemented in `plugin_manager.py`) with base classes:
  - [x] `CanvasForgePlugin` - base class (implied by API design)
  - [x] `ToolPlugin` - for toolbar tools (implied)
  - [x] `EffectPlugin` - for image effects (implied)
  - [x] `ExportPlugin` - for export formats (implied)
- [x] Implement APIs:
  - [x] Scene API (`canvasforge.scene`)
  - [x] Item API (`canvasforge.item`)
  - [x] UI API (`canvasforge.ui`) - toolbar/menu registration
  - [x] Settings API (`canvasforge.settings`)
  - [x] History API (`canvasforge.history`) - undo/redo
  - [x] Image API (`canvasforge.image`) - PIL/numpy conversion (basic support)
- [x] Add "Plugins" tab to Preferences dialog:
  - [x] External editor configuration
  - [x] Plugin list with enable/disable
  - [x] Plugin details panel
  - [x] File listing with view/edit buttons (partial/open folder)
  - [ ] Install from ZIP button (De-scoped for now)
  - [x] Open Plugins Folder button
  - [x] Refresh button (Reload plugin)
- [x] Create first plugin: **Crop Tool**
- [ ] Bundle core tools as default plugins (locked by default) - *Pending*

### Phase 2: Developer Experience

- [ ] Hot-reload via watchdog file monitoring
- [ ] "Edit in External Editor" integration
- [ ] Code preview in Preferences (read-only QPlainTextEdit)
- [ ] "New Plugin from Template" wizard
- [ ] Plugin validation and error reporting
- [ ] Plugin dependency installer (pip integration)

### Phase 3: Distribution

- [ ] ZIP package export with manifest validation
- [ ] ZIP package import with dependency checking
- [ ] GitHub plugins repository: `lukejmorrison/canvasforge-plugins`
- [ ] Plugin README viewer in app

### Phase 4: Community & AI

- [ ] GitHub Discussions for plugin ideas
- [ ] Plugin submission guidelines
- [ ] **AI Image Edit plugin** (Qwen-Image integration)
- [ ] Plugin verification/signing (optional)
- [ ] In-app plugin browser (if demand exists)

---

## GitHub Repository Structure

```
canvasforge-plugins/                    # https://github.com/lukejmorrison/canvasforge-plugins
├── README.md                           # Overview, installation guide
├── CONTRIBUTING.md                     # How to submit plugins
├── LICENSE                             # MIT or Apache-2.0
│
├── official/                           # Official CanvasForge plugins
│   ├── crop/
│   │   ├── manifest.json
│   │   ├── __init__.py
│   │   ├── crop_tool.py
│   │   ├── icon.png
│   │   └── README.md
│   ├── transform/
│   ├── shapes/
│   └── selection/
│
├── community/                          # Community-submitted plugins
│   ├── blur_effects/
│   ├── watermark/
│   ├── color_adjustments/
│   └── ai_image_edit/                  # Qwen-Image integration
│       ├── manifest.json
│       ├── __init__.py
│       ├── ai_edit.py
│       ├── requirements.txt            # diffusers, transformers, torch
│       └── README.md
│
├── templates/                          # Starter templates
│   ├── tool_plugin_template/
│   ├── effect_plugin_template/
│   └── export_plugin_template/
│
└── .github/
    ├── ISSUE_TEMPLATE/
    │   └── plugin_idea.md
    └── workflows/
        └── validate_plugins.yml        # CI to validate manifests
```

---

## Timeline

| Date | Milestone |
| --- | --- |
| Week 1 | Phase 1a - PluginManager, plugin_api.py, directory structure |
| Week 2 | Phase 1b - Scene/Item/UI APIs, Preferences Plugins tab |
| Week 3 | Phase 1c - Crop Tool plugin, Settings/History APIs |
| Week 4 | Phase 1d - Core tools converted to plugins, testing |
| TBD | Phase 2 - Developer experience (hot-reload, templates) |
| TBD | Phase 3 - Distribution (ZIP, GitHub repo) |
| TBD | Phase 4 - Community & AI (Qwen-Image plugin) |

---

## Notes

This document is now ready for Phase 1 implementation. All major design decisions have been made. The plugin API is comprehensive enough to support:

1. **Crop Tool** - First plugin demo
2. **Transform Tools** - Move, rotate, scale
3. **Basic Shapes** - Rectangle, ellipse, text
4. **AI Image Edit** - Qwen-Image integration (Phase 4)
5. **Future community plugins** - Effects, filters, exporters

The multi-language framework is designed but Python-only for Phase 1, allowing future expansion without breaking changes.

---

## User Stories

### Basic Plugin Use

- As a user, I want to use the Crop plugin to crop selected items on my canvas
- As a user, I want to see available plugins in Edit > Preferences > Plugins tab

### Plugin Customization

- As a power user, I want to view the source code of any plugin
- As a power user, I want to edit a plugin's code and see changes immediately
- As a developer, I want to open a plugin in VS Code with one click

### Plugin Sharing

- As a user, I want to install plugins from a ZIP file
- As a developer, I want to export my plugin as a shareable package
- As a community member, I want to browse/download plugins from a GitHub repository

---

## Technical Design

### Plugin Architecture

Based on research of open-source graphics applications (Blender, GIMP, Krita, Inkscape), the recommended architecture:

#### Plugin Directory Structure

```
plugins/
├── crop/
│   ├── manifest.json       # Plugin metadata
│   ├── __init__.py         # Entry point
│   ├── crop_tool.py        # Main implementation
│   ├── icon.png            # Toolbar/menu icon (optional)
│   └── README.md           # Documentation
├── another_plugin/
│   └── ...
```

#### Manifest Format (manifest.json)

```json
{
  "id": "com.canvasforge.crop",
  "name": "Crop Tool",
  "version": "1.0.0",
  "description": "Crop selected items on the canvas",
  "author": "CanvasForge Team",
  "license": "MIT",
  "canvasforge_api": "1.0",
  "entry_point": "crop_tool:CropPlugin",
  "hooks": ["tool_register", "context_menu"],
  "permissions": ["scene_access", "item_modify"],
  "icon": "icon.png"
}
```

#### Plugin Base Class

```python
# canvasforge/plugin_api.py
from abc import ABC, abstractmethod

class CanvasForgePlugin(ABC):
    """Base class all plugins must inherit from."""
    
    @abstractmethod
    def register(self, app):
        """Called when plugin is loaded."""
        pass
    
    @abstractmethod
    def unregister(self, app):
        """Called when plugin is unloaded."""
        pass
    
    def get_tools(self):
        """Return list of tools this plugin provides."""
        return []
    
    def get_menu_items(self):
        """Return menu items to add."""
        return []
```

### Dynamic Code Loading

Using Python's `importlib` for real-time loading and reloading:

```python
import importlib.util
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PluginManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.loaded_plugins = {}
        self.observer = None
    
    def load_plugin(self, plugin_name):
        """Load or reload a plugin by name."""
        plugin_path = self.plugin_dir / plugin_name / "__init__.py"
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)
        self.loaded_plugins[plugin_name] = module
        return module
    
    def reload_plugin(self, plugin_name):
        """Hot-reload a modified plugin."""
        if plugin_name in sys.modules:
            importlib.invalidate_caches()
            return importlib.reload(sys.modules[plugin_name])
    
    def start_hot_reload(self):
        """Watch plugin directory for changes."""
        # Uses watchdog library to detect file changes
        # Triggers reload_plugin() on modification
```

### Preferences UI - Plugins Tab

```
┌─────────────────────────────────────────────────────────────────┐
│ Plugins                                                          │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ☑ Crop Tool                              v1.0.0  [Built-in] │ │
│ │   Crop selected items on the canvas                         │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ ☑ Selection Effects                      v1.2.0  [User]     │ │
│ │   Add effects to selected regions                           │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ ☐ Experimental Plugin                    v0.1.0  [User]     │ │
│ │   Work in progress plugin (disabled)                        │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Selected Plugin: Crop Tool                                       │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ [View Code]  [Edit in VS Code]  [Reload]  [Export ZIP]      ││
│ │                                                              ││
│ │ Plugin Code Preview:                                         ││
│ │ ┌──────────────────────────────────────────────────────────┐││
│ │ │class CropPlugin(CanvasForgePlugin):                      │││
│ │ │    def register(self, app):                              │││
│ │ │        self.app = app                                    │││
│ │ │        app.add_tool(CropTool())                          │││
│ │ │    ...                                                   │││
│ │ └──────────────────────────────────────────────────────────┘││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│ [Install from ZIP...]  [Open Plugins Folder]  [Refresh]         │
└─────────────────────────────────────────────────────────────────┘
```

### Plugin Distribution

#### ZIP Package Format

```
crop-plugin-v1.0.0.zip
├── manifest.json
├── __init__.py
├── crop_tool.py
├── icon.png
└── README.md
```

#### Installation Flow

1. User clicks "Install from ZIP..."
2. App extracts to `~/.canvasforge/plugins/`
3. Manifest is validated
4. Plugin is loaded and registered
5. User sees plugin in list

### GitHub Repository Structure

```
canvasforge-plugins/           # Official plugin repository
├── README.md                  # Plugin submission guidelines
├── plugins/
│   ├── crop/                  # Official crop plugin
│   ├── blur/                  # Community-submitted
│   └── watermark/             # Community-submitted
├── templates/
│   └── plugin_template/       # Starter template for new plugins
└── CONTRIBUTING.md            # How to submit plugins
```

---

## First Plugin: Crop Tool

### Crop Functionality Requirements

1. **Activation**: Select an item → Crop tool becomes available in toolbar/menu
2. **Cursor**: Changes to crop cursor when tool is active
3. **Handles**: 8 resize handles appear on selected item (corners + edges)
4. **Drag to Crop**: User drags handles inward to define crop region
5. **Preview**: Real-time preview of cropped result
6. **Confirm/Cancel**: Enter to apply, Escape to cancel
7. **Undo Support**: Crop operation should be undoable

### Crop Modes to Support

- Free crop (any aspect ratio)
- Lock aspect ratio (shift+drag)
- Preset ratios (16:9, 4:3, 1:1, etc.) - future enhancement

---

## Security Considerations

### Risks

- Plugin code has full Python access (file system, network, etc.)
- Malicious plugins could damage user data

### Mitigations (Phased)

1. **Phase 1 (Initial)**: Trust-based - user installs plugins at their own risk
2. **Phase 2**: Permission system in manifest - user approves permissions on install
3. **Phase 3**: Optional sandboxing via RestrictedPython for untrusted plugins
4. **Phase 4**: Plugin signing for verified community plugins

### User Settings

- [ ] Enable plugin hot-reload (development mode)
- [ ] Auto-run plugins on startup
- [ ] Show plugin execution warnings

---

## Design Decisions (Clarified 2025-12-09)

### 1. Built-in vs User Plugins

| Tool | Type | Rationale |
| --- | --- | --- |
| **Select Tool** | ✏️ Editable Plugin | Users can customize selection behavior |
| **Move Tool** | 🔒 Locked Core | Core functionality, not editable |
| **Crop Tool** | ✏️ Plugin | First community plugin example |

### 2. Plugin API Scope

Full comprehensive API including:
- Scene access (read/write items) ✅
- Toolbar/menu registration ✅
- Settings storage ✅
- **Comprehensive Undo/Redo integration** ✅ (works consistently across entire app for every image edit)

### 3. Multi-language Support

**Python-only for MVP.** Manifest format designed to support future languages, but implementation is Python-first.

### 4. Hot Reload

**Basic reload implementation:**
- User-triggered reload via Preferences > Plugins > "Reload" button
- App displays notification when restart is required (e.g., for manifest changes, new toolbar items)
- No automatic file watching in MVP

### 5. Plugin Dependencies

**CLI-based installation:**
- Plugins declare dependencies in `manifest.json` under `"pip_dependencies": ["package1", "package2>=1.0"]`
- Users install via terminal: `pip install -r ~/.canvasforge/plugins/plugin-name/requirements.txt`
- App shows warning if required packages are missing
- Advanced users can manage their own virtual environments

### 6. Plugin Discovery & Updates

**No in-app marketplace.** Community-driven approach:
- **GitHub Discussions** for plugin ideas, requests, and sharing
- Plugins distributed via GitHub releases (ZIP files)
- "Check for New Plugins" button in Preferences queries GitHub API for available plugins
- Manual download and install (no auto-update)

### 7. Editor Integration

Configurable editor path in Preferences (defaults to `code` for VS Code).

---

## Comprehensive Undo/Redo System

Since you want comprehensive undo/redo that works consistently across the entire app, here's the architecture:

### UndoManager Class

```python
class UndoManager:
    """Global undo/redo manager for all operations."""
    
    def __init__(self, max_history: int = 100):
        self._undo_stack: list[UndoableAction] = []
        self._redo_stack: list[UndoableAction] = []
        self._max_history = max_history
        self._group_stack: list[ActionGroup] = []  # For compound operations
    
    def execute(self, action: UndoableAction) -> None:
        """Execute an action and add to undo stack."""
        action.execute()
        self._undo_stack.append(action)
        self._redo_stack.clear()  # Clear redo on new action
        self._trim_history()
    
    def undo(self) -> bool:
        """Undo the last action. Returns True if successful."""
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        action.undo()
        self._redo_stack.append(action)
        return True
    
    def redo(self) -> bool:
        """Redo the last undone action. Returns True if successful."""
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        action.execute()
        self._undo_stack.append(action)
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
```

### UndoableAction Base Class

```python
from abc import ABC, abstractmethod
from typing import Any

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
        self.actions: list[UndoableAction] = []
    
    def add(self, action: UndoableAction) -> None:
        self.actions.append(action)
    
    def execute(self) -> None:
        for action in self.actions:
            action.execute()
    
    def undo(self) -> None:
        for action in reversed(self.actions):
            action.undo()
```

### Built-in Action Types

```python
class AddItemAction(UndoableAction):
    """Undo/redo adding an item to the scene."""
    
    def __init__(self, scene, item_data: dict):
        super().__init__(f"Add {item_data.get('type', 'item')}")
        self.scene = scene
        self.item_data = item_data
        self.item = None
    
    def execute(self) -> None:
        self.item = self.scene._create_item_from_data(self.item_data)
        self.scene.addItem(self.item)
    
    def undo(self) -> None:
        if self.item:
            self.scene.removeItem(self.item)

class RemoveItemAction(UndoableAction):
    """Undo/redo removing an item from the scene."""
    
    def __init__(self, scene, item):
        super().__init__(f"Delete {item.data(0) or 'item'}")
        self.scene = scene
        self.item = item
        self.item_data = self._capture_item_state(item)
    
    def execute(self) -> None:
        self.scene.removeItem(self.item)
    
    def undo(self) -> None:
        self.scene.addItem(self.item)

class TransformItemAction(UndoableAction):
    """Undo/redo item transformations (move, scale, rotate)."""
    
    def __init__(self, item, old_transform: QTransform, new_transform: QTransform):
        super().__init__(f"Transform {item.data(0) or 'item'}")
        self.item = item
        self.old_transform = old_transform
        self.new_transform = new_transform
    
    def execute(self) -> None:
        self.item.setTransform(self.new_transform)
    
    def undo(self) -> None:
        self.item.setTransform(self.old_transform)

class ImageEditAction(UndoableAction):
    """Undo/redo image pixel edits (crop, filter, etc.)."""
    
    def __init__(self, item, old_pixmap: QPixmap, new_pixmap: QPixmap, description: str):
        super().__init__(description)
        self.item = item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
    
    def execute(self) -> None:
        self.item.setPixmap(self.new_pixmap)
    
    def undo(self) -> None:
        self.item.setPixmap(self.old_pixmap)

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
```

### Plugin API for Undo/Redo

```python
# In PluginAPI class:

def execute_undoable(self, action: UndoableAction) -> None:
    """Execute an action that can be undone."""
    self._undo_manager.execute(action)

def begin_undo_group(self, name: str) -> None:
    """Begin a group of actions that undo together."""
    self._undo_manager.begin_group(name)

def end_undo_group(self) -> None:
    """End the current undo group."""
    self._undo_manager.end_group()

def create_image_edit_action(
    self,
    item_id: str,
    old_pixmap: QPixmap,
    new_pixmap: QPixmap,
    description: str
) -> ImageEditAction:
    """Create an undoable image edit action."""
    item = self.get_item(item_id)
    return ImageEditAction(item, old_pixmap, new_pixmap, description)
```

### Example: Plugin Using Undo/Redo

```python
class CropPlugin:
    def apply_crop(self, item_id: str, rect: QRect) -> None:
        """Apply crop with full undo support."""
        item = self.api.get_item(item_id)
        old_pixmap = item.pixmap()
        
        # Perform the crop
        new_pixmap = old_pixmap.copy(rect)
        
        # Create undoable action
        action = self.api.create_image_edit_action(
            item_id, old_pixmap, new_pixmap, "Crop Image"
        )
        self.api.execute_undoable(action)
```

---

## Implementation Phases (Updated)

### Phase 1: Foundation (MVP)

- [ ] Create plugin directory structure (`~/.canvasforge/plugins/`)
- [ ] Implement `PluginManager` class with load/unload
- [ ] Add "Plugins" tab to Preferences dialog
- [ ] Implement basic reload button (with restart notification)
- [ ] Implement comprehensive `UndoManager` with action types
- [ ] Refactor existing operations to use UndoManager
- [ ] Implement first plugin: Crop Tool (with undo support)
- [ ] "Open Plugins Folder" button
- [ ] CLI dependency installation documentation

### Phase 2: Developer Experience

- [ ] "Edit in Editor" button (configurable path)
- [ ] Code preview in Preferences
- [ ] Plugin template generator
- [ ] Select Tool as editable plugin example

### Phase 3: Distribution

- [ ] ZIP package export
- [ ] ZIP package import/install
- [ ] GitHub plugins repository setup
- [ ] Plugin README/documentation viewer
- [ ] "Check for New Plugins" button (GitHub API query)

### Phase 4: Community

- [ ] GitHub Discussions setup for plugin ideas
- [ ] Plugin submission guidelines
- [ ] Community plugin gallery (GitHub README)

---

## Research References

| Project | Relevance |
| --- | --- |
| **Blender Add-ons** | ZIP distribution, `bl_info` manifest, `register()`/`unregister()` pattern |
| **GIMP Python-Fu** | In-app console for testing, IPC for plugin isolation |
| **Krita Scripter** | Built-in code editor with live execution |
| **pluggy** | Hook-based plugin system used by pytest |
| **napari npe2** | YAML manifests, CLI tools, validation |
| **QUndoStack** | Qt's built-in undo framework (inspiration for UndoManager) |
| **watchdog** | File system monitoring (future hot reload enhancement) |

---

## Timeline

| Date | Milestone |
| --- | --- |
| TBD | Phase 1 complete - Crop plugin + UndoManager working |
| TBD | Phase 2 complete - Developer tools |
| TBD | Phase 3 complete - Distribution + GitHub plugin discovery |
| TBD | Phase 4 complete - Community features |

---

## Notes

All design decisions have been clarified. Development can proceed with Phase 1 implementation.
