# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Get the current directory
current_dir = Path(__file__).parent

# Application data
app_name = 'LabelEditor'
main_script = 'app.py'

# Collect all label_editor package files
label_editor_datas = []
label_editor_path = current_dir / 'label_editor'
for root, dirs, files in os.walk(label_editor_path):
    for file in files:
        if file.endswith('.py'):
            src_path = os.path.join(root, file)
            dest_path = os.path.relpath(src_path, current_dir)
            label_editor_datas.append((src_path, os.path.dirname(dest_path)))

# Additional data files
datas = [
    ('keymap.json', '.'),
    ('config', 'config'),
] + label_editor_datas

# Hidden imports for GTK and related libraries
hiddenimports = [
    'gi',
    'gi.repository.Gtk',
    'gi.repository.Gdk',
    'gi.repository.GdkPixbuf',
    'gi.repository.GLib',
    'gi.repository.GObject',
    'gi.repository.Pango',
    'gi.repository.PangoCairo',
    'cairo',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'pytesseract',
    'concurrent.futures',
    'threading',
    'pathlib',
    'json',
    'label_editor',
    'label_editor.core',
    'label_editor.core.data_types',
    'label_editor.core.file_io',
    'label_editor.core.image_ops',
    'label_editor.core.keymap',
    'label_editor.core.validation',
    'label_editor.business',
    'label_editor.business.canvas_logic',
    'label_editor.business.label_logic',
    'label_editor.business.project_state',
    'label_editor.ui',
    'label_editor.ui.canvas_widget',
    'label_editor.ui.main_window',
    'label_editor.ui.event_handlers',
    'label_editor.ui.filter_modal',
]

# Platform-specific configurations
if sys.platform == 'win32':
    icon_file = None  # Add .ico file if available
    console = False
    target_arch = None
elif sys.platform == 'darwin':
    icon_file = None  # Add .icns file if available
    console = False
    target_arch = None
else:  # Linux
    icon_file = None  # Add .png file if available
    console = False
    target_arch = None

# Analysis
a = Analysis(
    [main_script],
    pathex=[str(current_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Executable configuration
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=console,
    disable_windowed_traceback=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# Collection (directory with all files)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{app_name}.app',
        icon=icon_file,
        bundle_identifier=f'com.labeleditor.{app_name.lower()}',
        info_plist={
            'CFBundleDisplayName': 'Label Editor',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.14',
        },
    )