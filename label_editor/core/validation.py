#!/usr/bin/env python3

import re
from pathlib import Path
from typing import Dict, List, Any
from .data_types import BoundingBox
from .file_io import DATParser


class ValidationEngine:
    """Handles validation of DAT files, labels, and OCR text"""
    
    def __init__(self, class_config: Dict[str, Any]):
        self.class_config = class_config
        self.validation_cache = {}
        
    def validate_all_files(self, image_files: List[Path], image_extensions: set) -> Dict[str, Dict[str, Any]]:
        """Validate all files in the directory"""
        validation_cache = {}
        
        for file_path in image_files:
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                dat_path = file_path.with_suffix('.dat')
                
                if dat_path.exists():
                    validation_result = self.validate_dat_file(str(dat_path))
                    validation_cache[str(file_path)] = validation_result
                else:
                    validation_result = {
                        'valid': False,
                        'no_dat': True,
                        'missing_classes': False,
                        'regex_errors': False,
                        'box_count': 0
                    }
                    validation_cache[str(file_path)] = validation_result
        
        return validation_cache
    
    def validate_dat_file(self, dat_path: str) -> Dict[str, Any]:
        """Validate a single DAT file"""
        try:
            boxes = DATParser.parse_dat_file(dat_path)
            
            # Check for missing classes
            missing_classes = self._check_missing_classes(boxes)
            
            # Check for regex errors
            regex_errors = self._check_regex_errors(boxes)
            
            return {
                'valid': len(boxes) > 0 and not missing_classes and not regex_errors,
                'no_dat': False,
                'missing_classes': missing_classes,
                'regex_errors': regex_errors,
                'box_count': len(boxes),
                'boxes': boxes
            }
        except Exception as e:
            return {
                'valid': False,
                'no_dat': False,
                'missing_classes': False,
                'regex_errors': True,
                'box_count': 0,
                'error': str(e)
            }
    
    def _check_missing_classes(self, boxes: List[BoundingBox]) -> bool:
        """Check if any required classes are missing"""
        required_classes = [cls["id"] for cls in self.class_config["classes"] if cls.get("required", False)]
        present_classes = [box.class_id for box in boxes]
        
        return any(req_cls not in present_classes for req_cls in required_classes)
    
    def _check_regex_errors(self, boxes: List[BoundingBox]) -> bool:
        """Check if any OCR text fails regex validation"""
        for box in boxes:
            if not self.validate_ocr_text(box.ocr_text, box.class_id):
                return True
        return False
    
    def validate_ocr_text(self, ocr_text: str, class_id: int) -> bool:
        """Validate OCR text against class regex pattern"""
        if not ocr_text:
            return True  # Empty text is considered valid
            
        class_info = self._get_class_info(class_id)
        if not class_info or "regex_pattern" not in class_info:
            return True
            
        regex_pattern = class_info["regex_pattern"]
        try:
            return bool(re.match(regex_pattern, ocr_text))
        except re.error:
            return False
    
    def get_validation_status(self, ocr_text: str, class_id: int) -> Dict[str, Any]:
        """Get detailed validation status for OCR text"""
        class_info = self._get_class_info(class_id)
        
        if not class_info:
            return {
                'valid': False,
                'error': f'Unknown class ID: {class_id}'
            }
        
        if "regex_pattern" not in class_info:
            return {
                'valid': True,
                'message': 'No validation pattern defined'
            }
        
        if not ocr_text:
            return {
                'valid': True,
                'message': 'Empty text'
            }
        
        regex_pattern = class_info["regex_pattern"]
        try:
            is_valid = bool(re.match(regex_pattern, ocr_text))
            return {
                'valid': is_valid,
                'message': '✓ Valid format' if is_valid else '✗ Invalid format',
                'pattern': regex_pattern
            }
        except re.error as e:
            return {
                'valid': False,
                'error': f'Invalid regex pattern: {e}'
            }
    
    def _get_class_info(self, class_id: int) -> Dict[str, Any]:
        """Get class information by ID"""
        for cls in self.class_config["classes"]:
            if cls["id"] == class_id:
                return cls
        return None
    
    def get_file_validation_status(self, file_path: str) -> str:
        """Get CSS class name for file validation status"""
        validation = self.validation_cache.get(file_path)
        if not validation:
            return "file-normal"
        
        if validation.get('error'):
            return "file-error"
        elif validation.get('no_dat'):
            return "file-no-dat"
        elif validation.get('missing_classes'):
            return "file-missing-classes"
        elif validation.get('regex_errors'):
            return "file-invalid-regex"
        elif validation.get('valid'):
            return "file-valid"
        else:
            return "file-normal"
    
    def get_validation_summary(self, validation_cache: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        """Get summary of validation results"""
        summary = {
            'total': len(validation_cache),
            'valid': 0,
            'no_dat': 0,
            'missing_classes': 0,
            'regex_errors': 0,
            'errors': 0
        }
        
        for validation in validation_cache.values():
            if validation.get('error'):
                summary['errors'] += 1
            elif validation.get('no_dat'):
                summary['no_dat'] += 1
            elif validation.get('missing_classes'):
                summary['missing_classes'] += 1
            elif validation.get('regex_errors'):
                summary['regex_errors'] += 1
            elif validation.get('valid'):
                summary['valid'] += 1
        
        return summary