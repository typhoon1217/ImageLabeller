# Modular Settings System

The Label Editor now uses a modular settings system that allows you to create and manage different configuration profiles for various use cases.

## Directory Structure

```
settings/
├── base.json           # Base settings that all profiles inherit
├── profiles/           # Directory containing profile configurations
│   ├── passport.json   # Passport MRZ scanning profile
│   ├── document_ocr.json   # General document OCR profile
│   ├── invoice_processing.json  # Invoice processing profile
│   └── minimal.json    # Minimal UI profile
└── README.md          # This file
```

## How It Works

1. **Base Settings** (`base.json`): Contains default application settings that all profiles inherit from.

2. **Profiles** (`profiles/*.json`): Each profile only contains settings that differ from the base. This keeps profiles small and focused.

3. **Inheritance**: When a profile is loaded, its settings are merged with the base settings. Profile settings override base settings.

## Available Profiles

### passport
- **Purpose**: Passport MRZ (Machine Readable Zone) scanning
- **Features**: 
  - Pre-configured MRZ classes with regex validation
  - Optimized window size for passport scanning
  - PaddleOCR-field as default OCR engine

### document_ocr
- **Purpose**: General document OCR with layout detection
- **Features**:
  - Classes for title, paragraph, table, and figure
  - Tesseract OCR with English language
  - Confidence score display

### invoice_processing
- **Purpose**: Invoice field extraction and validation
- **Features**:
  - Specific invoice fields (number, date, amount, vendor)
  - Regex validation for structured fields
  - Image preprocessing options

### minimal
- **Purpose**: Simplified UI for basic labeling tasks
- **Features**:
  - Hidden toolbar and status bar
  - Disabled auto-save
  - Single text class

## Using Profiles in Code

```python
from label_editor.core.settings_manager import SettingsManager

# Initialize settings manager
sm = SettingsManager()

# Load a profile
sm.load_profile("passport")

# Get settings
window_width = sm.get("window.width")
classes = sm.get("classes.classes")

# Set settings
sm.set("window.width", 1600)

# Save changes to current profile
sm.save_profile(sm.active_profile)
```

## Creating Custom Profiles

1. **From scratch**: Create a new JSON file in `profiles/` with your settings
2. **Based on existing**: Use the profile selector UI or:
   ```python
   sm.create_profile("my_custom", base_on="passport")
   ```

## Profile File Format

Profiles use nested JSON structure. Only include settings that differ from base:

```json
{
  "window": {
    "width": 1400,
    "height": 900
  },
  "classes": {
    "classes": [
      {
        "id": 0,
        "name": "my_class",
        "color": [1.0, 0.0, 0.0],
        "key": "1"
      }
    ]
  }
}
```

## Migration from Old Settings

If you have an existing `settings.json` file, it will be automatically migrated to a "default" profile when the application starts. The original file is backed up as `settings.json.bak`.

## Settings Categories

- **app**: Application metadata and general settings
- **ui**: User interface preferences
- **performance**: Threading and caching settings
- **file_types**: Supported file extensions
- **validation**: Real-time validation settings
- **shortcuts**: Keyboard shortcuts
- **window**: Window dimensions
- **classes**: Label classes configuration
- **ocr**: OCR engine settings
- **default_directory**: Last used directory