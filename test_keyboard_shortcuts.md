# Keyboard Shortcuts Test Guide

## Vim-Style Keyboard Shortcuts for Label Editing

### Features Implemented:

1. **'i' Key to Enter Insert Mode**
   - Select a label box by clicking on it or using Tab
   - Press 'i' to enter insert/typing mode (like vim)
   - The OCR text field will automatically gain focus
   - The text field will be cleared for fresh input
   - Start typing your text
   - The text will be saved to the selected label

2. **ESC Key to Exit Insert Mode**
   - While editing text in the OCR field, press ESC
   - Focus will return to the canvas (like exiting vim insert mode)
   - You can then use canvas shortcuts again

3. **Existing Canvas Shortcuts** (work when canvas has focus):
   - `Tab` - Cycle through label boxes
   - `Delete` - Delete selected box
   - `+/=` - Zoom in
   - `-` - Zoom out
   - `0` - Reset zoom
   - `ESC` - Deselect current box (when canvas has focus)
   - `i` - Enter insert mode (when a box is selected)

### Testing Steps:

1. **Test 'i' Key Insert Mode**:
   - Open an image with existing labels or create new ones
   - Click on a label box to select it
   - Press 'i' key
   - ✅ The OCR text field should gain focus automatically
   - ✅ The text field should be cleared
   - ✅ You can now type text freely

2. **Test ESC to Exit**:
   - While editing text in the OCR field
   - Press ESC
   - ✅ Focus should return to the canvas
   - ✅ You should be able to use Tab to cycle through boxes again

3. **Test Vim-Like Workflow**:
   - Select a box with Tab or mouse
   - Press 'i' to enter insert mode
   - Type your text (e.g., "ABC123")
   - Press ESC to return to canvas/normal mode
   - Press Tab to go to next box
   - Press 'i' again to edit
   - Type new text
   - Repeat

### Benefits:
- ⚡ Faster data entry - no need to click the text field
- 🎯 More intuitive - just select and type
- ⌨️ Keyboard-only workflow possible
- 🔄 Quick switching between labels with Tab and typing

### Notes:
- The typed text is automatically saved to the selected label
- Changes trigger auto-save after 2 seconds of inactivity
- File list colors update immediately when data is added