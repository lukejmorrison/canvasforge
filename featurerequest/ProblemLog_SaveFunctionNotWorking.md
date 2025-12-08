# Problem Log: Save Function Not Working Properly

**Date Created:** 2025-12-08  
**Status:** ✅ Closed (Resolved 2025-12-08)  
**Date Resolved:** 2025-12-08  
**Severity:** Low (UI/UX confusion)  
**Affects:** File > Save functionality

**Resolution:** Created unified Preferences dialog (Edit > Preferences...) that clearly organizes folder settings with descriptions. Users can now easily distinguish between "Save canvas to" (export destination) and "Screenshot folder" (image library source).

---

## Problem Description

User expected **File > Save** to save to `/home/luke/Pictures/Screenshots/1CanvasForge/` after changing folder settings, but the file was saved to `~/Pictures/CanvasForge/` instead.

---

## Root Cause: Two Different Folder Settings (Confusing UI)

The user changed **"Change Image Library Folder..."** (which controls where the screenshot browser looks for source images), but expected it to change where **File > Save** exports images.

These are **two separate settings**:

| Menu Option | QSettings Key | Purpose | Affects |
|-------------|---------------|---------|---------|
| **Edit > Change Image Library Folder...** | `screenshot_library_dir` | Where to browse screenshots FROM | Left sidebar image library |
| **Edit > Change Save Folder...** | `default_save_dir` | Where to save canvas exports TO | File > Save destination |

---

## Resolution

**To change where File > Save exports images:**
1. Go to **Edit > Change Save Folder...**
2. Select the desired folder (e.g., `/home/luke/Pictures/Screenshots/1CanvasForge/`)
3. Future saves will go to that location

**Debug output confirmed save is working:**
```
DEBUG save_canvas: default_save_dir = /home/luke/Pictures/CanvasForge
DEBUG save_canvas: Directory exists = True
DEBUG save_canvas: Attempting to save to /home/luke/Pictures/CanvasForge/2025-12-08_CanvasForge_4.png
DEBUG save_canvas: Save result = True
```

---

## UX Improvement Recommendation

The current menu naming may be confusing. Consider:
1. Renaming "Change Image Library Folder..." to "Set Screenshot Source Folder..."
2. Renaming "Change Save Folder..." to "Set Export Destination..."
3. Adding tooltips or a Settings dialog that groups these together with clear descriptions

---

## Technical Context

### Current Save Implementation (`main.py`)

**Save Directory Initialization (lines ~1385-1390):**
```python
self.settings = QSettings("CanvasForge", "CanvasForge")
default_pictures = Path.home() / "Pictures" / "CanvasForge"
saved_dir = self.settings.value("default_save_dir", str(default_pictures))
self.default_save_dir = Path(saved_dir)
self._ensure_save_directory()
```

**Save Canvas Method (lines ~1689-1704):**
```python
def save_canvas(self):
    image = self._capture_scene_image()
    if image is None:
        self._status_bar.showMessage("Nothing to save", 4000)
        return
    self._ensure_save_directory()
    base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge"
    counter = 1
    while True:
        candidate = self.default_save_dir / f"{base_name}_{counter}.png"
        if not candidate.exists():
            break
        counter += 1
    image.save(str(candidate))
    self._status_bar.showMessage(f"Saved canvas to {candidate}", 5000)
```

**Change Save Directory Method (lines ~1705-1712):**
```python
def change_save_directory(self):
    new_dir = QFileDialog.getExistingDirectory(self, "Select Save Folder", str(self.default_save_dir))
    if new_dir:
        self.default_save_dir = Path(new_dir)
        self._ensure_save_directory()
        self.settings.setValue("default_save_dir", str(self.default_save_dir))
        self._status_bar.showMessage(f"Default save folder set to {self.default_save_dir}", 5000)
```

---

## Potential Issues to Investigate

### 1. QImage.save() Return Value Not Checked
The `image.save()` method returns `True` on success, `False` on failure, but the return value is not checked:
```python
image.save(str(candidate))  # No error handling!
```

**Fix:** Check return value and show error if save fails.

### 2. Flatpak Sandbox Permissions
The Flatpak manifest may not have permission to write to the user-specified folder. Current permissions in `com.lukejmorrison.CanvasForge.yml`:
- `--filesystem=home` (should allow access to home directory)

**Check:** Verify the specified folder is within the sandbox's allowed paths.

### 3. Path Resolution Issues
- Is `self.default_save_dir` being updated correctly when user changes the folder?
- Is the path being converted to string properly for `image.save()`?

### 4. Image Capture Returning None
The `_capture_scene_image()` method returns `None` if the scene is empty. Check if the status bar shows "Nothing to save".

### 5. QSettings Persistence
- QSettings may not be persisting correctly in Flatpak environment
- Settings location may differ between dev environment and Flatpak

---

## Debugging Steps

### Step 1: Add Debug Logging
Add print statements to track the save operation:
```python
def save_canvas(self):
    print(f"DEBUG: save_canvas called, default_save_dir = {self.default_save_dir}")
    image = self._capture_scene_image()
    if image is None:
        print("DEBUG: Image is None, nothing to save")
        self._status_bar.showMessage("Nothing to save", 4000)
        return
    self._ensure_save_directory()
    print(f"DEBUG: Directory exists: {self.default_save_dir.exists()}")
    # ... rest of method
    save_result = image.save(str(candidate))
    print(f"DEBUG: Save result = {save_result}, path = {candidate}")
```

### Step 2: Verify Folder Permissions
```bash
# Check if folder exists and is writable
ls -la /path/to/save/folder
touch /path/to/save/folder/test.txt && rm /path/to/save/folder/test.txt
```

### Step 3: Check QSettings Location
```bash
# For standard app:
cat ~/.config/CanvasForge/CanvasForge.conf

# For Flatpak:
cat ~/.var/app/com.lukejmorrison.CanvasForge/config/CanvasForge/CanvasForge.conf
```

### Step 4: Run from Terminal to See Output
```bash
# Development:
python main.py

# Flatpak:
flatpak run com.lukejmorrison.CanvasForge
```

---

## User Report Details

- **Environment:** Pop!_OS with COSMIC compositor, NVIDIA GPU
- **Running as:** Flatpak (`com.lukejmorrison.CanvasForge`)
- **Custom save folder:** (To be specified)
- **Status bar message after save:** (Did it show success message?)
- **File exists in folder after save:** No

---

## Proposed Fixes

### Fix 1: Add Error Handling to save_canvas()
```python
def save_canvas(self):
    image = self._capture_scene_image()
    if image is None:
        self._status_bar.showMessage("Nothing to save", 4000)
        return
    self._ensure_save_directory()
    base_name = datetime.date.today().strftime("%Y-%m-%d") + "_CanvasForge"
    counter = 1
    while True:
        candidate = self.default_save_dir / f"{base_name}_{counter}.png"
        if not candidate.exists():
            break
        counter += 1
    
    success = image.save(str(candidate))
    if success:
        self._status_bar.showMessage(f"Saved canvas to {candidate}", 5000)
    else:
        self._status_bar.showMessage(f"Failed to save canvas to {candidate}", 5000)
        print(f"ERROR: Failed to save image to {candidate}")
```

### Fix 2: Add Directory Write Check
```python
def _ensure_save_directory(self):
    try:
        self.default_save_dir.mkdir(parents=True, exist_ok=True)
        # Verify directory is writable
        test_file = self.default_save_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
    except PermissionError:
        print(f"ERROR: Cannot write to {self.default_save_dir}")
        # Fallback to default?
```

---

## Testing Checklist

- [ ] Reproduce the issue in Flatpak environment
- [ ] Check status bar message after clicking Save
- [ ] Verify `default_save_dir` value in QSettings
- [ ] Test save to default folder (`~/Pictures/CanvasForge`)
- [ ] Test save to custom folder
- [ ] Add error handling and re-test
- [ ] Verify Flatpak filesystem permissions

---

## Resolution

**Status:** Pending investigation  
**Fix Applied:** None yet  
**Verified Working:** No
