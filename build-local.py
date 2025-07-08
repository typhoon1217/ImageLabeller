#!/usr/bin/env python3
"""
Local build script for Label Editor
Supports building on Windows, Linux, and macOS
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return success status"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True, 
                              capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def install_system_dependencies():
    """Install system dependencies based on platform"""
    system = platform.system().lower()
    
    if system == 'linux':
        print("Installing Linux dependencies...")
        commands = [
            "sudo apt-get update",
            "sudo apt-get install -y libgirepository1.0-dev libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libgtk-4-dev gobject-introspection tesseract-ocr tesseract-ocr-eng"
        ]
        for cmd in commands:
            if not run_command(cmd):
                print(f"Failed to install Linux dependencies")
                return False
    
    elif system == 'darwin':
        print("Installing macOS dependencies...")
        commands = [
            "brew install gtk4 gobject-introspection cairo pango gdk-pixbuf tesseract"
        ]
        for cmd in commands:
            if not run_command(cmd):
                print(f"Failed to install macOS dependencies")
                return False
    
    elif system == 'windows':
        print("Installing Windows dependencies...")
        commands = [
            "choco install gtk-runtime -y",
            "choco install tesseract -y"
        ]
        for cmd in commands:
            if not run_command(cmd):
                print(f"Failed to install Windows dependencies")
                return False
    
    return True

def build_application():
    """Build the application using PyInstaller"""
    print("Building application...")
    
    # Clean previous builds
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    # Install Python dependencies
    if not run_command("python -m pip install --upgrade pip"):
        return False
    
    if not run_command("pip install -r requirements.txt"):
        return False
    
    # Build with PyInstaller
    if not run_command("pyinstaller --clean --noconfirm build.spec"):
        return False
    
    print("Build completed successfully!")
    return True

def create_distribution():
    """Create distribution archives"""
    system = platform.system().lower()
    
    if not os.path.exists('dist'):
        print("No dist directory found!")
        return False
    
    # Create releases directory
    os.makedirs('releases', exist_ok=True)
    
    app_name = 'LabelEditor'
    
    if system == 'windows':
        # Create ZIP for Windows
        archive_name = f"{app_name}-{system}-{platform.machine()}.zip"
        shutil.make_archive(
            f'releases/{archive_name[:-4]}', 
            'zip', 
            'dist'
        )
    else:
        # Create tar.gz for Linux/macOS
        archive_name = f"{app_name}-{system}-{platform.machine()}.tar.gz"
        shutil.make_archive(
            f'releases/{archive_name[:-7]}', 
            'gztar', 
            'dist'
        )
    
    print(f"Created distribution: releases/{archive_name}")
    return True

def main():
    """Main build process"""
    print("Label Editor Build Script")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--install-deps':
        if not install_system_dependencies():
            print("Failed to install system dependencies")
            return 1
    
    if not build_application():
        print("Build failed!")
        return 1
    
    if not create_distribution():
        print("Distribution creation failed!")
        return 1
    
    print("Build process completed successfully!")
    return 0

if __name__ == '__main__':
    sys.exit(main())