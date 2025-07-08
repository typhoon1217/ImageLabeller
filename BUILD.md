# Build Instructions for Label Editor

## Quick Start

### Using Make (Recommended)
```bash
# Build the application
make build

# Build with automatic dependency installation
make build-deps

# Clean build artifacts
make clean

# Run the application
make run
```

### Using Python Script
```bash
# Build only
python build-local.py

# Build with dependency installation
python build-local.py --install-deps
```

## Prerequisites

### All Platforms
- Python 3.9+ 
- pip package manager

### Platform-Specific Requirements

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y \
  libgirepository1.0-dev \
  libcairo2-dev \
  libpango1.0-dev \
  libgdk-pixbuf2.0-dev \
  libgtk-4-dev \
  gobject-introspection \
  tesseract-ocr \
  tesseract-ocr-eng
```

#### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install gtk4 gobject-introspection cairo pango gdk-pixbuf tesseract
```

#### Windows
```powershell
# Install Chocolatey if not already installed
# Run as Administrator
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install dependencies
choco install gtk-runtime -y
choco install tesseract -y
```

## Build Process

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Build Application
```bash
pyinstaller --clean --noconfirm build.spec
```

### 3. Locate Built Application
- **Linux/macOS**: `dist/LabelEditor/LabelEditor`
- **Windows**: `dist/LabelEditor/LabelEditor.exe`

## Development Workflow

### Setup Development Environment
```bash
# Install dependencies
make deps
make system-deps

# Run in development mode
make dev
```

### Quality Checks
```bash
# Format code
make format

# Lint code
make lint

# Type checking
make typecheck

# Run all checks
make check
```

### Testing
```bash
# Run tests
make test
```

## Distribution

### Create Distribution Archive
```bash
# Build and create distribution
make dist
```

Archives will be created in the `releases/` directory:
- Linux: `LabelEditor-linux-x86_64.tar.gz`
- macOS: `LabelEditor-darwin-x86_64.tar.gz`
- Windows: `LabelEditor-windows-x86_64.zip`

## GitHub Actions

### Automatic Builds
The repository includes GitHub Actions workflows for:

1. **Continuous Integration** (`.github/workflows/build.yml`)
   - Runs on push/PR to main branch
   - Tests on Python 3.9, 3.10, 3.11
   - Builds on Ubuntu, Windows, macOS

2. **Release Automation** (`.github/workflows/release.yml`)
   - Triggers on version tags (v*)
   - Creates GitHub release
   - Uploads platform-specific binaries

### Creating a Release
```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will automatically:
# 1. Build for all platforms
# 2. Create a GitHub release
# 3. Upload distribution archives
```

## Troubleshooting

### Common Issues

#### GTK4 Not Found
- **Linux**: Install `libgtk-4-dev` package
- **macOS**: Install via Homebrew: `brew install gtk4`
- **Windows**: Install GTK runtime via Chocolatey

#### Tesseract Not Found
- **Linux**: Install `tesseract-ocr` package
- **macOS**: Install via Homebrew: `brew install tesseract`
- **Windows**: Install via Chocolatey: `choco install tesseract`

#### Python Package Issues
```bash
# Clear pip cache
pip cache purge

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

#### Build Fails
```bash
# Clean previous builds
make clean

# Rebuild
make build
```

## Advanced Configuration

### Custom Build Options
Edit `build.spec` to customize:
- Application name and icon
- Hidden imports
- Data files inclusion
- Platform-specific settings

### Environment Variables
- `PYTHONPATH`: Add custom module paths
- `PKG_CONFIG_PATH`: GTK library paths
- `TESSDATA_PREFIX`: Tesseract data directory

## File Structure
```
dist/
├── LabelEditor/          # Main application directory
│   ├── LabelEditor       # Executable (Linux/macOS)
│   ├── LabelEditor.exe   # Executable (Windows)
│   ├── keymap.json       # Keyboard shortcuts
│   ├── config/           # Configuration files
│   └── _internal/        # Python runtime and libraries
└── releases/             # Distribution archives
```