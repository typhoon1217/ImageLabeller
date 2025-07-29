#!/usr/bin/env python3

import re
from typing import Dict, Any, Optional
from enum import Enum


class CharacterPolicy(Enum):
    """Character preservation policies for universal language support"""
    UNICODE_PRESERVE = "unicode_preserve"      # Preserve all Unicode characters (any language)
    ASCII_ONLY = "ascii_only"                  # ASCII letters/numbers only (MRZ, codes)  
    NUMERIC_ONLY = "numeric_only"              # Digits and specified punctuation
    ALPHANUMERIC_UNICODE = "alphanumeric_unicode"  # Letters/numbers from any script
    CUSTOM = "custom"                          # Use custom whitelist/blacklist rules


class ImageOperations:
    """Handles image processing operations for OCR and label processing"""
    
    @staticmethod
    def _get_character_policy_for_class(class_id: int, class_config: Dict[str, Any]) -> CharacterPolicy:
        """Get character policy for a specific class with backwards compatibility"""
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                # Check for explicit character policy (new system)
                policy_str = cls.get("character_policy")
                if policy_str:
                    try:
                        return CharacterPolicy(policy_str)
                    except ValueError:
                        pass  # Fall through to field type mapping
                
                # Backwards compatibility: map field types to policies
                field_type = cls.get("field_type", "text")
                return ImageOperations._map_field_type_to_policy(field_type)
        
        # Default policy for unknown classes
        return CharacterPolicy.UNICODE_PRESERVE
    
    @staticmethod
    def _map_field_type_to_policy(field_type: str) -> CharacterPolicy:
        """Map legacy field types to character policies for backwards compatibility"""
        field_type_mapping = {
            "mrz": CharacterPolicy.ASCII_ONLY,
            "numeric": CharacterPolicy.NUMERIC_ONLY,
            "single_char": CharacterPolicy.ASCII_ONLY,
            "alphanumeric": CharacterPolicy.ALPHANUMERIC_UNICODE,
            "date": CharacterPolicy.ALPHANUMERIC_UNICODE,
            # All text-like fields preserve Unicode for any language
            "text": CharacterPolicy.UNICODE_PRESERVE,
            "address": CharacterPolicy.UNICODE_PRESERVE,
            "enum": CharacterPolicy.UNICODE_PRESERVE,
            "header": CharacterPolicy.UNICODE_PRESERVE,
            "table": CharacterPolicy.UNICODE_PRESERVE,
            "image": CharacterPolicy.UNICODE_PRESERVE,
        }
        
        return field_type_mapping.get(field_type, CharacterPolicy.UNICODE_PRESERVE)
    
    @staticmethod
    def _apply_character_policy(text: str, policy: CharacterPolicy, filter_rules: Optional[Dict[str, Any]] = None) -> str:
        """Apply character filtering policy for universal language support"""
        if not text:
            return text
            
        # Get filter rules with defaults
        rules = filter_rules or {}
        
        if policy == CharacterPolicy.UNICODE_PRESERVE:
            # Preserve all Unicode characters - suitable for any language
            return text.strip()
            
        elif policy == CharacterPolicy.ASCII_ONLY:
            # Keep only ASCII letters, numbers, and specified punctuation
            allowed_punct = rules.get("allow_punctuation", "<>")
            allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" + allowed_punct)
            return ''.join(c for c in text.upper() if c in allowed_chars)
            
        elif policy == CharacterPolicy.NUMERIC_ONLY:
            # Keep only digits and specified punctuation
            allowed_punct = rules.get("allow_punctuation", "./-")
            return ''.join(c for c in text if c.isdigit() or c in allowed_punct)
            
        elif policy == CharacterPolicy.ALPHANUMERIC_UNICODE:
            # Keep letters and numbers from any Unicode script
            # This supports multilingual alphanumeric text
            allowed_punct = rules.get("allow_punctuation", " ")
            return ''.join(c for c in text if c.isalnum() or c in allowed_punct).strip()
            
        elif policy == CharacterPolicy.CUSTOM:
            # Apply custom whitelist/blacklist rules
            custom_whitelist = rules.get("custom_whitelist")
            remove_chars = rules.get("remove_chars", "")
            
            processed = text
            
            # Apply character removal first
            if remove_chars:
                for char in remove_chars:
                    processed = processed.replace(char, "")
            
            # Apply whitelist if specified
            if custom_whitelist:
                processed = ''.join(c for c in processed if c in custom_whitelist)
            
            return processed.strip()
        
        # Fallback to Unicode preserve
        return text.strip()
    
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
        """Get Tesseract configuration using universal character policies"""
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                # Check for explicit Tesseract config override first
                explicit_config = cls.get("tesseract_config")
                if explicit_config:
                    return explicit_config
                
                # Use character policy to determine appropriate config
                policy = ImageOperations._get_character_policy_for_class(class_id, class_config)
                
                if policy in [CharacterPolicy.UNICODE_PRESERVE, CharacterPolicy.ALPHANUMERIC_UNICODE]:
                    # No character whitelist - supports any Unicode language
                    return "--oem 3 --psm 8"
                elif policy == CharacterPolicy.ASCII_ONLY:
                    # ASCII whitelist for controlled fields (MRZ, codes, etc.)
                    filter_rules = cls.get("char_filter_rules", {})
                    allowed_punct = filter_rules.get("allow_punctuation", "<>")
                    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" + allowed_punct
                    return f"--oem 3 --psm 8 -c tessedit_char_whitelist={whitelist}"
                elif policy == CharacterPolicy.NUMERIC_ONLY:
                    # Numeric whitelist
                    filter_rules = cls.get("char_filter_rules", {})
                    allowed_punct = filter_rules.get("allow_punctuation", "./-")
                    whitelist = "0123456789" + allowed_punct
                    return f"--oem 3 --psm 8 -c tessedit_char_whitelist={whitelist}"
                elif policy == CharacterPolicy.CUSTOM:
                    # Custom whitelist from filter rules
                    filter_rules = cls.get("char_filter_rules", {})
                    custom_whitelist = filter_rules.get("custom_whitelist", "")
                    if custom_whitelist:
                        return f"--oem 3 --psm 8 -c tessedit_char_whitelist={custom_whitelist}"
                    else:
                        return "--oem 3 --psm 8"  # Fallback to no whitelist
        
        # Default config - supports Unicode for universal language support
        return "--oem 3 --psm 8"

    @staticmethod
    def postprocess_text_by_field_type(text: str, class_id: int, class_config: Dict[str, Any]) -> str:
        """Post-process OCR text using universal character policies"""
        # Get class configuration and regex pattern
        regex_pattern = None
        filter_rules = None
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                regex_pattern = cls.get("regex_pattern", None)
                filter_rules = cls.get("char_filter_rules", {})
                break

        # Legacy handling for special field types that need custom processing
        field_type = None
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                field_type = cls.get("field_type", "text")
                break
        
        # Special cases that bypass normal policy processing
        if field_type == "mrz":
            processed_text = ImageOperations._postprocess_mrz_text(text)
        elif field_type == "date":
            processed_text = ImageOperations._postprocess_date_text(text)
        elif field_type == "single_char":
            # Single character extraction - apply policy then take first char
            policy = ImageOperations._get_character_policy_for_class(class_id, class_config)
            temp_processed = ImageOperations._apply_character_policy(text, policy, filter_rules)
            processed_text = temp_processed[:1] if temp_processed else ""
        else:
            # Universal policy-based processing for all other field types
            policy = ImageOperations._get_character_policy_for_class(class_id, class_config)
            processed_text = ImageOperations._apply_character_policy(text, policy, filter_rules)

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
