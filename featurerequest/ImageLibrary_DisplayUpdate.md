# Feature Request: Image Library Display Update

## Document Metadata

| Field | Value |
| --- | --- |
| Doc ID | FR-20251209-LibraryDisplay |
| Version | v1.1 |
| Date | 2025-12-09 |
| Owner / Author | GitHub Copilot |
| Status | ✅ Implemented & Tested |
| Priority | Medium |
| Changelog Tag | [1.2.1] Image Library Display Update |
| Related Files | image_library_panel.py |

## Overview

Update the Image Library Panel's file listing display to show a more informative and readable layout with:
1. Left-justified column text for better readability
2. Small thumbnails (48x48) showing actual image previews instead of generic file icons
3. YYMMDD HHMMSS date/time format visible inline for easier sort verification

## Current State

The Image Library currently uses `QListView` in `IconMode` which:
- Displays large 120x120 system file icons (not actual image thumbnails)
- Shows only filenames below icons
- Uses a grid layout that doesn't show dates inline
- Requires selecting a file to see metadata in the properties panel

## Goals

- **Improve Readability**: Left-justified text in columnar format is easier to scan
- **Show Real Thumbnails**: Display actual image previews to help users identify screenshots quickly
- **Inline Date/Time**: Show YYMMDD HHMMSS format so users can verify sorting without selecting each file
- **Maintain Performance**: Use background thumbnail generation with caching to keep the UI responsive with 500+ files
- **Filename Always Visible**: Filename must always be visible; date flows after and may be clipped by viewport edge

## Requirements

### Functional Requirements

1. **Custom Item Delegate**
   - Create `ImageLibraryDelegate(QStyledItemDelegate)` that paints each row with:
     - 48x48 thumbnail on the left (actual image preview)
     - Left-justified filename text (always visible)
     - Date positioned after filename, may be clipped if panel is narrow

2. **Background Thumbnail Generation**
   - Use `QTimer.singleShot` queue to generate thumbnails asynchronously
   - Cache thumbnails in memory keyed by `(file_path, mtime)` tuple
   - Show placeholder icon while thumbnail is loading
   - Limit concurrent thumbnail operations to prevent UI blocking

3. **View Mode Change**
   - Switch from `IconMode` to `ListMode` for columnar layout

4. **Refresh and Sort Integration**
   - Refresh button must re-apply current sort settings after reloading file list
   - Sort changes should persist across refresh operations
   - Disable wrapping for horizontal rows
   - Adjust row height to accommodate thumbnail + padding (56px)

### UI Layout

```
┌─────────────────────────────────────────────┐
│ [48x48]  Screenshot-38.png    YYMMDD HHMMSS │
│ [thumb]                                     │
├─────────────────────────────────────────────┤
│ [48x48]  Screenshot-39.png    YYMMDD HHMMSS │
│ [thumb]                                     │
├─────────────────────────────────────────────┤
│ [48x48]  Screenshot-40.png    YYMMDD HHMMSS │
│ [thumb]                                     │
└─────────────────────────────────────────────┘
```

### Non-Functional Requirements

- Thumbnail cache should handle 500+ images without excessive memory usage (~10MB max for cache)
- Background generation should not block UI thread
- Visible thumbnails should load within 100ms of scrolling into view
- Cache should invalidate when file mtime changes

## Technical Design

### New Classes

```python
class ThumbnailCache:
    """Thread-safe thumbnail cache with background generation."""
    - _cache: Dict[Tuple[str, int], QPixmap]  # (path, mtime) -> pixmap
    - _pending: Set[str]  # paths currently being generated
    - _queue: List[str]  # paths waiting to be generated
    - thumbnailReady: pyqtSignal(str)  # emitted when thumbnail is ready
    
class ImageLibraryDelegate(QStyledItemDelegate):
    """Custom delegate for list items with thumbnails and dates."""
    - THUMBNAIL_SIZE = 48
    - ROW_HEIGHT = 56
    - DATE_FORMAT = "yyMMdd HHmmss"
    - paint(painter, option, index)
    - sizeHint(option, index) -> QSize
```

### Implementation Steps

1. Add `ThumbnailCache` class to `image_library_panel.py`
2. Add `ImageLibraryDelegate` class with custom paint logic
3. Modify `ImageLibraryPanel.__init__` to:
   - Switch view to `ListMode`
   - Instantiate and set the custom delegate
   - Connect thumbnail cache signals to trigger view updates
4. Update properties panel date format to match

## Success Metrics

- Thumbnails display correctly for PNG, JPG, and other supported formats
- UI remains responsive while scrolling through 200+ images
- Date format clearly shows YYMMDD HHMMSS
- Text is left-justified and easily readable

## Timeline

| Date | Event |
| --- | --- |
| 2025-12-09 | Feature request created, implementation started |
| 2025-12-09 | Implementation complete - ThumbnailCache, ImageLibraryDelegate added, view switched to ListMode |

## Implementation Notes

### Files Modified
- `image_library_panel.py` - Added ThumbnailCache class, ImageLibraryDelegate class, updated ImageLibraryPanel to use ListMode with custom delegate
- `main.py` - Version bumped to 1.2.0
- `CHANGELOG.md` - Added v1.2.0 release notes

### Key Features Implemented
1. **ThumbnailCache** - Background thumbnail generation with:
   - In-memory cache keyed by (file_path, mtime)
   - Queue-based async loading using QTimer
   - LRU eviction when cache exceeds 500 entries
   - Placeholder display while loading

2. **ImageLibraryDelegate** - Custom painting with:
   - 48x48 thumbnail on the left
   - Left-justified filename (always visible)
   - Date flows after filename, may be clipped by viewport edge
   - Selection/hover highlighting

3. **Refresh/Sort Integration** - Refresh button re-applies current sort settings after reloading file list

3. **View Configuration Changes**:
   - Switched from IconMode to ListMode
   - Removed zoom slider (not applicable in list mode)
   - Reduced spacing from 8 to 2 for compact rows
