#!/usr/bin/env python3

import re
from typing import Dict, Any


class ImageOperations:
    """Handles image processing operations for OCR and label processing"""
    
    @staticmethod
    def preprocess_image_by_field_type(image, class_id: int, class_config: Dict[str, Any]):
        """Preprocess image based on field type for optimal OCR results"""
        field_type = None
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                field_type = cls.get("field_type", "text")
                break

        if field_type == "mrz":
            return ImageOperations._preprocess_mrz_image(image)
        elif field_type == "single_char":
            return ImageOperations._preprocess_single_char_image(image)
        else:
            return ImageOperations._preprocess_general_image(image)

    @staticmethod
    def _preprocess_single_char_image(image):
        """Preprocess image for single character recognition"""
        try:
            import cv2
        except ImportError:
            raise ImportError("OpenCV is required for image preprocessing")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        scale_factor = 5
        height, width = thresh.shape
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        scaled = cv2.resize(thresh, (new_width, new_height),
                           interpolation=cv2.INTER_CUBIC)

        return scaled

    @staticmethod
    def _preprocess_general_image(image):
        """Preprocess image for general text recognition"""
        try:
            import cv2
        except ImportError:
            raise ImportError("OpenCV is required for image preprocessing")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 11, 2)

        scale_factor = 2
        height, width = thresh.shape
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        scaled = cv2.resize(thresh, (new_width, new_height),
                           interpolation=cv2.INTER_CUBIC)

        return scaled

    @staticmethod
    def _preprocess_mrz_image(image):
        """Preprocess image for MRZ (Machine Readable Zone) recognition"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            raise ImportError("OpenCV and NumPy are required for MRZ preprocessing")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Bilateral filter for noise reduction
        filtered = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # Otsu's thresholding
        _, binary = cv2.threshold(
            filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological operations to clean up
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # Scale up for better OCR
        scale_factor = 4
        height, width = cleaned.shape
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        scaled = cv2.resize(cleaned, (new_width, new_height),
                           interpolation=cv2.INTER_LANCZOS4)

        # Sharpen the image
        kernel_sharpen = np.array([[-1, -1, -1],
                                  [-1, 9, -1],
                                  [-1, -1, -1]])
        sharpened = cv2.filter2D(scaled, -1, kernel_sharpen)

        return sharpened

    @staticmethod
    def get_tesseract_config_for_class(class_id: int, class_config: Dict[str, Any]) -> str:
        """Get Tesseract configuration for specific class"""
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                return cls.get("tesseract_config", 
                             "--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        return "--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    @staticmethod
    def postprocess_text_by_field_type(text: str, class_id: int, class_config: Dict[str, Any]) -> str:
        """Post-process OCR text based on field type"""
        field_type = None
        regex_pattern = None
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                field_type = cls.get("field_type", "text")
                regex_pattern = cls.get("regex_pattern", None)
                break

        if field_type == "mrz":
            processed_text = ImageOperations._postprocess_mrz_text(text)
        elif field_type == "date":
            processed_text = ImageOperations._postprocess_date_text(text)
        elif field_type == "single_char":
            processed_text = text.upper()[:1] if text else ""
        elif field_type == "alphanumeric":
            processed_text = ''.join(c for c in text.upper() if c.isalnum())
        else:  # text type
            processed_text = text.strip()

        if regex_pattern:
            if not re.match(regex_pattern, processed_text):
                processed_text = ImageOperations._try_autocorrect_with_regex(
                    processed_text, regex_pattern, field_type)

        return processed_text

    @staticmethod
    def _postprocess_mrz_text(text: str) -> str:
        """Post-process MRZ text"""
        # Remove all whitespace
        text = re.sub(r'\s+', '', text)
        
        # Keep only valid MRZ characters
        text = re.sub(r'[^A-Z0-9<]', '', text)
        
        # Common OCR corrections for MRZ
        corrections = {
            'O': '0',  # Common mistake: letter O instead of zero
            'I': '1',  # Common mistake: letter I instead of one
            'S': '5',  # Common mistake: letter S instead of five
            'Z': '2',  # Common mistake: letter Z instead of two
            'B': '8',  # Common mistake: letter B instead of eight
            'G': '6',  # Common mistake: letter G instead of six
        }
        
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        return text

    @staticmethod
    def _postprocess_date_text(text: str) -> str:
        """Post-process date text"""
        text = re.sub(r'\s+', ' ', text.strip())
        text = text.replace('O', '0').replace('I', '1').replace('S', '5')
        return text

    @staticmethod
    def _try_autocorrect_with_regex(text: str, regex_pattern: str, field_type: str) -> str:
        """Try to autocorrect text to match regex pattern"""
        # Document/passport number pattern
        if "^[MPS][0-9]{8}$" in regex_pattern:
            text = text.replace('O', '0').replace('I', '1').replace('S', '5')
            if text and text[0].lower() in ['m', 'p', 's']:
                text = text[0].upper() + text[1:]
        
        # Date field corrections
        elif field_type == "date":
            month_map = {
                'JRN': 'JAN', 'JPN': 'JAN',
                'FES': 'FEB', 'FER': 'FEB',
                'MPR': 'MAR', 'MAB': 'MAR',
                'PPR': 'APR', 'APB': 'APR',
                'MPY': 'MAY', 'MAT': 'MAY',
                'JUN': 'JUN', 'JUL': 'JUL',
                'AUG': 'AUG', 'SEP': 'SEP',
                'OCT': 'OCT', 'NOV': 'NOV',
                'DEC': 'DEC'
            }
            for wrong, correct in month_map.items():
                text = text.replace(wrong, correct)
        
        return text