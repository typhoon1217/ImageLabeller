# VietOCR Integration Usage

## Overview
VietOCR has been successfully integrated into the Label Editor GUI as a fourth OCR engine option, specifically optimized for Vietnamese National ID document processing.

## Installation

### Using Conda Environment (Recommended)
```bash
# Activate the existing OCR environment
source /home/jungwoo/miniconda3/etc/profile.d/conda.sh
conda activate ocr

# Install VietOCR (already installed in the ocr environment)
pip install vietocr
```

### System-wide Installation (Alternative)
```bash
# If using pipx
pipx install vietocr

# Or with virtual environment
python -m venv vietocr_env
source vietocr_env/bin/activate
pip install vietocr
```

## Usage

1. **Start the Application**:
   ```bash
   source /home/jungwoo/miniconda3/etc/profile.d/conda.sh
   conda activate ocr
   python app.py
   ```

2. **Select VietOCR Engine**:
   - In the right sidebar, locate the "OCR Model" dropdown
   - Select "VietOCR (Vietnamese)" from the dropdown options
   - This engine is now ready for Vietnamese text recognition

3. **Run OCR on Vietnamese Text**:
   - Select a bounding box around Vietnamese text
   - Click the "🔍 Run OCR" button
   - VietOCR will process the selected region and extract Vietnamese text

## Features

### VietOCR Specific Features
- **Transformer Architecture**: Uses VGG + Transformer model optimized for Vietnamese
- **High Accuracy**: Specifically trained on Vietnamese text patterns
- **CPU/GPU Support**: Automatically uses CPU, can be configured for GPU
- **Image Preprocessing**: Includes automatic image scaling for small text regions
- **Memory Management**: Automatic cleanup to prevent memory leaks

### Integration Features
- **Seamless UI**: Same interface as other OCR engines
- **Error Handling**: Graceful fallback if VietOCR unavailable
- **Threading**: Non-blocking OCR processing
- **Postprocessing**: Uses existing field-specific text processing pipeline

## Technical Details

### Model Information
- **Model**: VGG + Transformer architecture
- **Language**: Optimized for Vietnamese text
- **Input**: PIL Images
- **Output**: Extracted Vietnamese text strings

### Configuration
- **Device**: Defaults to CPU (configurable for GPU)
- **Beam Search**: Disabled for faster processing
- **Image Scaling**: Automatic scaling for images < 32px

### Error Messages
- "VietOCR not available. Install: pip install vietocr" - Install VietOCR package
- "VietOCR config error" - Configuration loading failed
- "VietOCR predictor initialization failed" - Model loading failed
- "VietOCR prediction error" - OCR processing failed

## Performance

### Expected Performance
- **Accuracy**: High accuracy for Vietnamese text, especially printed text
- **Speed**: Moderate speed (slower than Tesseract, comparable to PaddleOCR)
- **Memory**: Moderate memory usage with automatic cleanup

### Optimization Tips
- Use VietOCR specifically for Vietnamese text regions
- Ensure good image quality for best results
- Consider GPU acceleration for batch processing

## Troubleshooting

### Common Issues
1. **Import Error**: Ensure VietOCR is installed in the active environment
2. **Model Download**: First use may download pretrained models
3. **Memory Issues**: Automatic cleanup prevents most memory problems
4. **GPU Issues**: Defaults to CPU if GPU unavailable

### Environment Setup
Make sure to use the conda OCR environment:
```bash
source /home/jungwoo/miniconda3/etc/profile.d/conda.sh
conda activate ocr
```

## Comparison with Other Engines

| Engine | Language | Accuracy | Speed | Best For |
|--------|----------|----------|-------|----------|
| Tesseract | Multi-language | Good | Fast | General text |
| EasyOCR | Multi-language | Good | Medium | Multiple languages |
| PaddleOCR | Multi-language | Good | Medium | General OCR |
| **VietOCR** | **Vietnamese** | **High** | **Medium** | **Vietnamese NID/Documents** |

## Development Notes

### Code Architecture
- `_run_vietocr_ocr()` method in `OCRProcessor` class
- Engine selection in `_run_ocr_thread()` method
- UI dropdown option in `main_window.py`
- Consistent error handling and cleanup patterns

### Future Enhancements
- GPU configuration options
- Vietnamese-specific preprocessing
- Custom model loading
- Batch processing optimization