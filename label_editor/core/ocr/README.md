# OCR Module

This module provides a modular OCR (Optical Character Recognition) system that makes it easy to swap between different OCR implementations.

## Architecture

The OCR module follows a plugin architecture with:
- `OCREngine`: Abstract base class that all OCR implementations must inherit from
- `OCRResult`: Standardized result container with text, confidence, and metadata
- `OCRFactory`: Factory pattern for creating and managing OCR engines

## Available Engines

### 1. Tesseract OCR (`tesseract`)
Basic Tesseract implementation without field-specific processing.

### 2. Tesseract Field OCR (`tesseract-field`)
Enhanced Tesseract with field-specific preprocessing and postprocessing based on document field types (MRZ, dates, etc.).

### 3. EasyOCR (`easyocr`)
Ready-to-use OCR with 80+ supported languages. More robust than Tesseract for multilingual text.

### 4. EasyOCR Field OCR (`easyocr-field`)
Enhanced EasyOCR with field-specific preprocessing and postprocessing for document field types.

### 5. PaddleOCR (`paddleocr`)
PaddleOCR is a practical ultra-lightweight OCR system with excellent Asian language support.

### 6. PaddleOCR Field OCR (`paddleocr-field`)
Enhanced PaddleOCR with field-specific preprocessing and postprocessing for document field types.

## Usage

```python
from label_editor.core.ocr import OCRFactory

# Create a Tesseract OCR engine
ocr = OCRFactory.create_engine('tesseract-field', config={'class_config': class_config})

# Or create an EasyOCR engine
ocr = OCRFactory.create_engine('easyocr-field', config={
    'languages': ['en', 'es', 'fr'],  # Multiple languages
    'gpu': False,  # Use CPU (set to True for GPU if available)
    'class_config': class_config
})

# Extract text from an image
result = ocr.extract_text(image_array, class_id=1)
print(f"Text: {result.text}")
print(f"Confidence: {result.confidence}")
print(f"Languages: {result.metadata.get('languages', [])}")
```

### EasyOCR Configuration Options

```python
config = {
    'languages': ['en', 'es', 'fr'],  # Supported languages
    'gpu': True,  # Use GPU if available
    'model_dir': './models/',  # Custom model directory
    'download_enabled': True,  # Allow model downloads
    'class_config': {...}  # For field-specific processing
}
```

## Adding a New OCR Engine

To add a new OCR engine (e.g., Google Vision, AWS Textract, PaddleOCR):

1. Create a new file in `core/ocr/` (e.g., `google_vision_ocr.py`)

2. Implement the OCREngine interface:

```python
from . import OCREngine, OCRResult, OCRFactory

class GoogleVisionOCR(OCREngine):
    def is_available(self) -> bool:
        # Check if Google Vision API is configured
        try:
            from google.cloud import vision
            return True
        except ImportError:
            return False
    
    def extract_text(self, image: np.ndarray, **kwargs) -> OCRResult:
        # Implement Google Vision API call
        client = vision.ImageAnnotatorClient()
        # ... API implementation ...
        return OCRResult(text=extracted_text, confidence=confidence)
    
    def get_requirements(self) -> Dict[str, str]:
        return {
            'packages': 'pip install google-cloud-vision',
            'system': 'Google Cloud credentials required'
        }

# Register the engine
OCRFactory.register_engine('google-vision', GoogleVisionOCR)
```

3. Import your engine in `__init__.py`:

```python
try:
    from . import google_vision_ocr
except ImportError:
    pass
```

## Switching OCR Engines

The OCRProcessor in `label_logic.py` supports runtime engine switching:

```python
# Get available engines
engines = ocr_processor.get_available_engines()
print(engines)  # {'tesseract': True, 'tesseract-field': True, 'easyocr': True, 'easyocr-field': True}

# Switch to a different engine
ocr_processor.set_ocr_engine('easyocr-field')
```

## Engine Comparison

| Feature | Tesseract | Tesseract-Field | EasyOCR | EasyOCR-Field | PaddleOCR | PaddleOCR-Field |
|---------|-----------|----------------|---------|---------------|-----------|-----------------|
| Languages | 100+ | 100+ | 80+ | 80+ | 80+ | 80+ |
| GPU Support | No | No | Yes | Yes | Yes | Yes |
| Setup Complexity | Medium | Medium | Easy | Easy | Easy | Easy |
| Accuracy (English) | Good | Good | Very Good | Very Good | Very Good | Very Good |
| Accuracy (Asian) | Fair | Fair | Excellent | Excellent | Excellent | Excellent |
| Speed | Fast | Fast | Medium | Medium | Fast | Fast |
| Memory Usage | Low | Low | Medium | Medium | Medium | Medium |
| Dependencies | tesseract binary | tesseract binary | Python only | Python only | Python only | Python only |
| Best For | English docs | English docs | Multilingual | Multilingual | Asian text | Asian text |

## Installation Requirements

### For Tesseract engines:
```bash
# System dependencies
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
brew install tesseract              # macOS
choco install tesseract             # Windows

# Python packages
pip install pytesseract pillow opencv-python
```

### For EasyOCR engines:
```bash
# Python packages only
pip install easyocr opencv-python

# Optional: For GPU support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### For PaddleOCR engines:
```bash
# Python packages only
pip install paddleocr opencv-python

# For GPU support
pip install paddlepaddle-gpu paddleocr

# For CPU only
pip install paddlepaddle paddleocr
```

## Conda Environment Setup

For the best experience with different OCR engines, use separate conda environments:

```bash
# Use your custom activation command
cload

# Create separate environments
conda create -n tesseract-ocr python=3.10 -y
conda create -n easyocr-env python=3.10 -y
conda create -n paddleocr-env python=3.10 -y

# Or create combined environment
conda create -n ocr-combined python=3.10 -y
```

For detailed conda setup instructions, see `CONDA_SETUP.md`.

## Configuration

Each OCR engine can accept configuration through the `config` parameter:

```python
config = {
    'api_key': 'your-api-key',
    'endpoint': 'https://api.example.com',
    'timeout': 30,
    'class_config': {...}  # For field-specific processing
}
ocr = OCRFactory.create_engine('custom-engine', config)
```

## Error Handling

The module provides clear error messages when engines are not available:

```
OCR engine 'google-vision' is not available.
Python packages: pip install google-cloud-vision
System requirements: Google Cloud credentials required
```
