# Image Rotation Features

## Overview
The Label Editor now includes comprehensive manual image rotation capabilities for correcting image orientation. This feature is particularly useful for images that are not properly positioned or scanned at incorrect angles.

## Features

### 🔄 **Rotation Controls**
- **Toolbar Buttons**: Located in the navigation bar with intuitive symbols
  - `↺` Rotate 90° counter-clockwise
  - `↻` Rotate 90° clockwise  
  - `⟲` Reset to original orientation
  - `💾` Save rotated image (enabled only when rotation is applied)

### ⌨️ **Keyboard Shortcuts**
- `Ctrl+R` → Rotate 90° clockwise
- `Ctrl+Shift+R` → Rotate 90° counter-clockwise
- `F5` → Reset to original orientation

### 💾 **Save Options**
When saving a rotated image, you get two choices:

1. **Save Copy**: Creates a new file with "_rotated" suffix
   - Original file remains unchanged
   - Safe option for testing or keeping both versions

2. **Overwrite**: Replaces the original image
   - Directly overwrites the original image file
   - Updates the current working file

### 🎯 **Smart Features**

#### Automatic Bounding Box Transformation
- All label boxes automatically rotate with the image
- Coordinates are mathematically transformed to match the new orientation
- No manual adjustment needed after rotation

#### Visual Feedback
- Rotation angle displayed in toolbar (0°, 90°, 180°, 270°)
- Save button only enabled when image has unsaved rotation
- Status bar updates confirm successful operations

#### State Management
- Tracks current rotation angle
- Preserves original image data until explicitly saved
- Can reset to original orientation at any time
- Warns about unsaved changes

## Usage Workflow

1. **Load Image**: Open an image that needs rotation correction
2. **Rotate**: Use buttons or keyboard shortcuts to rotate the image
3. **Adjust**: Continue rotating until image is properly oriented
4. **Save**: Choose save option based on your needs
   - Use "Save Copy" for testing or keeping both versions
   - Use "Overwrite" to replace the original image file directly

## Settings Configuration

Rotation behavior can be customized in the settings profiles:

```json
"rotation": {
  "default_save_format": "copy",
  "rotated_suffix": "_rotated",
  "confirm_overwrite": true
}
```

### Settings Options:
- `default_save_format`: Default to "copy" or "overwrite" mode  
- `rotated_suffix`: Suffix for copied rotated files
- `confirm_overwrite`: Show confirmation dialog before overwriting

## Safety Features

### Data Protection
- Original data preserved until explicitly saved
- Clear save options to prevent accidental overwrites

### Error Handling
- Comprehensive error messages for save failures
- Graceful fallback if rotation operations fail
- Status updates keep user informed of operation results

### Data Integrity
- Bounding box coordinates mathematically transformed
- No data loss during rotation operations
- Original label data preserved through coordinate transformations

## Technical Details

### Supported Rotations
- 90° increments (90°, 180°, 270°)
- Clockwise and counter-clockwise
- Multiple rotations compound correctly
- Reset returns to exact original state

### File Format Support
- JPEG (.jpg, .jpeg) - High quality (95%) compression
- PNG (.png) - Lossless compression  
- BMP (.bmp) - Uncompressed
- Unknown formats default to PNG

### Memory Efficiency
- Original image data cached for multiple rotations
- Efficient pixbuf operations using GdkPixbuf
- Minimal memory overhead for rotation state

## Integration

The rotation system integrates seamlessly with:
- **Modular Settings System**: Profile-based configuration
- **File Management**: Directory navigation and file tracking
- **Label System**: Automatic coordinate transformation
- **OCR Operations**: Works with all OCR engines
- **Validation System**: Maintains label validation after rotation

This feature enhances the Label Editor's usability for handling real-world document scanning scenarios where images may not be properly oriented.

## Fixed Issues (v1.3)

### ✅ **Proper Corner-Based Rotation Transformation (v1.6)**
- **Issue**: Labels still appeared in wrong positions after 90° and 270° rotations
- **Root Cause**: Simplified rotation formulas were mathematically incorrect for bounding box transformation
- **Solution**: Implemented proper corner-based rotation transformation:
  - **90° rotation**: Transform all four corners using `(x,y) -> (y, orig_width-x)`, then find bounding box
  - **180° rotation**: Transform all four corners using `(x,y) -> (orig_width-x, orig_height-y)`, then find bounding box  
  - **270° rotation**: Transform all four corners using `(x,y) -> (orig_height-y, x)`, then find bounding box
  - **Mathematically accurate**: Each corner is individually transformed, then new bounding box is calculated
  - **Boundary clamping**: Safe bounds checking prevents out-of-bounds coordinates

### ✅ **No-Backup Overwrite (v1.4)**
- **Change**: Removed automatic backup creation when overwriting original images
- **Reason**: User requested simpler workflow without automatic backups
- **Implementation**: 
  - "Overwrite" option now directly replaces original image file
  - No backup files created automatically
  - Cleaner, more direct save workflow
  - Updated dialog text to reflect no backup creation

### ✅ **Critical Rotation Bugs Fixed (v1.3)**
- **Issue**: TypeError: 'bool' object is not iterable when rotating images
- **Issue**: AttributeError: 'MessageDialog' object has no attribute 'run' in GTK4
- **Issue**: Rotation buttons causing crashes and preventing image rotation
- **Solution**: Complete GTK4 compatibility and safety system:
  - **Safety checks**: `self.boxes` is always a list, preventing boolean iteration errors
  - **GTK4 dialogs**: Replaced deprecated `.run()` with proper async `connect('response')` + `present()` pattern
  - **Error prevention**: Multiple validation layers prevent crashes in all scenarios
  - **Robust rotation**: Image rotation works reliably with buttons, keyboard shortcuts, and save operations
  - **Both save paths**: Ctrl+S and toolbar 💾 button use identical, reliable save logic

### ✅ **Image File Rotation Save (v1.2)**
- **Issue**: User wanted original image file to be actually rotated and saved, not just label coordinates
- **Solution**: Simplified save logic so "Save Both" option now:
  - **Save Both**: Saves the rotated image file (overwrites original with backup) and current label positions as they appear on screen
  - **Labels Only**: Keep original image file, save transformed label coordinates

### ✅ **Image-Label Synchronization (v1.1)**
- **Issue**: When saving with Ctrl+S, labels were saved with rotated coordinates but image remained unrotated
- **Solution**: Added intelligent save dialog that offers two options:
  - **Save Labels Only**: Keep original image, save rotated label coordinates
  - **Save Both**: Save rotated image and correctly positioned labels

### ✅ **Coordinate Transformation**
- **Issue**: Bounding box coordinates weren't properly fitting rotated images  
- **Solution**: Fixed coordinate transformation algorithm to properly handle:
  - Multiple rotation cycles maintaining accuracy
  - Edge cases at image boundaries
  - Reverse transformations for saving

### ✅ **Auto-Save Integration**
- **Issue**: Auto-save wasn't aware of rotation state
- **Solution**: Auto-save now detects rotation and only saves labels (safer), with status message indicating image rotation not auto-saved

### ✅ **State Management**
- **Issue**: Rotation state not properly maintained across operations
- **Solution**: Added proper state tracking with original box caching and reset functionality

## How the Fixed System Works (v1.2)

### When You Rotate an Image:
1. Image is visually rotated using efficient pixbuf operations
2. Original bounding boxes are cached for reference
3. Displayed boxes are transformed to match rotated image
4. Rotation angle and unsaved state are tracked

### When You Save (Ctrl+S):
- **If No Rotation**: Normal save of labels
- **If Rotated**: Smart dialog appears with options:
  - **Save Both**: Image file is rotated and saved (replaces original with backup), current label positions saved as they appear
  - **Save Labels Only**: Original image file kept unchanged, transformed label coordinates saved

### Auto-Save Behavior:
- Only saves label coordinates (never auto-saves rotated images for safety)
- Shows status message when rotation is detected
- Prevents accidental image overwriting

This robust system ensures data integrity while providing flexible options for different workflows.