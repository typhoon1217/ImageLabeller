#!/bin/bash

# MRZ Label Editor - Environment Setup Script
# Run this once to install dependencies

set -e

echo "Setting up environment for MRZ Label Editor..."

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda not found. Please install Anaconda or Miniconda first."
    exit 1
fi

# Install required packages using conda
echo "Installing dependencies with conda..."
conda install -c conda-forge pygobject gtk4 tesseract pytesseract opencv pillow scipy -y

echo "Environment setup complete!"
echo "You can now run the label editor using: ./run_label_editor.sh"
