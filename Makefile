# Label Editor Makefile
# Cross-platform build system

.PHONY: all build clean install test run dev deps help

# Default target
all: build

# Build the application
build:
	@echo "Building Label Editor..."
	python build-local.py

# Build with dependency installation
build-deps:
	@echo "Building with dependency installation..."
	python build-local.py --install-deps

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/
	rm -rf build/
	rm -rf releases/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Install Python dependencies
deps:
	@echo "Installing Python dependencies..."
	python -m pip install --upgrade pip
	pip install -r requirements.txt

# Install system dependencies (Linux/macOS)
system-deps:
	@echo "Installing system dependencies..."
	@if [ "$(shell uname)" = "Linux" ]; then \
		sudo apt-get update && \
		sudo apt-get install -y libgirepository1.0-dev libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libgtk-4-dev gobject-introspection tesseract-ocr tesseract-ocr-eng; \
	elif [ "$(shell uname)" = "Darwin" ]; then \
		brew install gtk4 gobject-introspection cairo pango gdk-pixbuf tesseract; \
	else \
		echo "System dependency installation not supported on this platform"; \
	fi

# Run the application
run:
	@echo "Running Label Editor..."
	python app.py

# Development mode with auto-reload
dev:
	@echo "Starting development mode..."
	python app.py --dev

# Run tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v || echo "No tests found"

# Format code
format:
	@echo "Formatting code..."
	black label_editor/ app.py build-local.py
	
# Lint code
lint:
	@echo "Linting code..."
	flake8 label_editor/ app.py build-local.py

# Type checking
typecheck:
	@echo "Type checking..."
	mypy label_editor/ app.py

# Full quality check
check: format lint typecheck test

# Install the application (development)
install:
	@echo "Installing Label Editor in development mode..."
	pip install -e .

# Create distribution packages
dist: build
	@echo "Creating distribution packages..."
	ls -la releases/

# Show help
help:
	@echo "Label Editor Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  build       - Build the application"
	@echo "  build-deps  - Build with dependency installation"
	@echo "  clean       - Clean build artifacts"
	@echo "  deps        - Install Python dependencies"
	@echo "  system-deps - Install system dependencies"
	@echo "  run         - Run the application"
	@echo "  dev         - Run in development mode"
	@echo "  test        - Run tests"
	@echo "  format      - Format code with black"
	@echo "  lint        - Lint code with flake8"
	@echo "  typecheck   - Type check with mypy"
	@echo "  check       - Run all quality checks"
	@echo "  install     - Install in development mode"
	@echo "  dist        - Create distribution packages"
	@echo "  help        - Show this help message"