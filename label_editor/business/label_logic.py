#!/usr/bin/env python3

import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from ..core.data_types import BoundingBox
from ..core.file_io import DATParser
from ..core.image_ops import ImageOperations


class LabelManager:
    """Manages label operations including OCR, creation, editing, and deletion"""
    
    def __init__(self, class_config: Dict[str, Any]):
        self.class_config = class_config
        self.boxes = []
        self.selected_box = None
        self.unsaved_changes = False
        self.last_save_time = {}
        self.confirmation_status = {}
        
        # Callbacks
        self.on_box_selected = None
        self.on_boxes_changed = None
        self.on_status_update = None
        self.on_error = None
        
    def set_boxes(self, boxes: List[BoundingBox]):
        """Set the current list of boxes"""
        self.boxes = boxes
        for box in self.boxes:
            box.name = self.get_class_name(box.class_id)
        self.selected_box = None
        self.unsaved_changes = False
        
    def get_class_name(self, class_id: int) -> str:
        """Get class name by ID"""
        for cls in self.class_config["classes"]:
            if cls["id"] == class_id:
                return cls["name"]
        return f"class_{class_id}"
    
    def get_class_by_id(self, class_id: int) -> Optional[Dict[str, Any]]:
        """Get class configuration by ID"""
        for cls in self.class_config["classes"]:
            if cls["id"] == class_id:
                return cls
        return None
    
    def select_box(self, box: Optional[BoundingBox]):
        """Select a box and trigger callbacks"""
        if self.selected_box:
            self.selected_box.selected = False
        
        if box:
            box.selected = True
            self.selected_box = box
        else:
            self.selected_box = None
            
        if self.on_box_selected:
            self.on_box_selected(box)
    
    def create_box(self, x: int, y: int, width: int, height: int) -> BoundingBox:
        """Create a new bounding box"""
        # Find appropriate class ID
        available_classes = [cls["id"] for cls in self.class_config["classes"]]
        used_classes = [b.class_id for b in self.boxes]
        
        class_id = available_classes[0]  # Default to first class
        for cls_id in available_classes:
            if cls_id not in used_classes:
                class_id = cls_id
                break
        
        class_name = self.get_class_name(class_id)
        new_box = BoundingBox(x, y, width, height, class_id, "", class_name)
        new_box.selected = True
        
        # Deselect previous box
        if self.selected_box:
            self.selected_box.selected = False
        
        self.boxes.append(new_box)
        self.selected_box = new_box
        self.mark_changed()
        
        if self.on_box_selected:
            self.on_box_selected(new_box)
        
        return new_box
    
    def delete_selected_box(self) -> bool:
        """Delete the currently selected box"""
        if self.selected_box:
            self.boxes.remove(self.selected_box)
            self.selected_box = None
            self.mark_changed()
            
            if self.on_box_selected:
                self.on_box_selected(None)
            
            return True
        return False
    
    def update_selected_box_text(self, new_text: str):
        """Update OCR text of selected box"""
        if self.selected_box:
            self.selected_box.ocr_text = new_text
            self.mark_changed()
    
    def update_selected_box_class(self, class_id: int):
        """Update class of selected box"""
        if self.selected_box:
            self.selected_box.class_id = class_id
            self.selected_box.name = self.get_class_name(class_id)
            self.mark_changed()
    
    def select_next_box(self):
        """Select the next box in sequence"""
        if not self.boxes:
            return
        
        current_idx = -1
        if self.selected_box:
            try:
                current_idx = self.boxes.index(self.selected_box)
            except ValueError:
                pass
        
        next_idx = (current_idx + 1) % len(self.boxes)
        self.select_box(self.boxes[next_idx])
    
    def set_box_class_by_key(self, keyval):
        """Set selected box class based on key press"""
        if not self.selected_box:
            return False
        
        for cls in self.class_config["classes"]:
            if keyval == getattr(self, f'KEY_{cls["key"]}', None):
                self.selected_box.class_id = cls["id"]
                self.selected_box.name = cls["name"]
                self.mark_changed()
                return True
        return False
    
    def mark_changed(self):
        """Mark labels as changed"""
        self.unsaved_changes = True
        if self.on_boxes_changed:
            self.on_boxes_changed()
    
    def get_ocr_character_counts(self) -> Dict[str, int]:
        """Get character counts for OCR text by class"""
        counts = {}
        for box in self.boxes:
            class_name = self.get_class_name(box.class_id)
            if class_name not in counts:
                counts[class_name] = 0
            counts[class_name] += len(box.ocr_text)
        return counts
    
    def get_dat_file_content(self) -> str:
        """Get DAT file content as string"""
        lines = []
        for box in sorted(self.boxes, key=lambda b: b.class_id):
            line = f"{box.class_id} {box.x} {box.y} {box.width} {box.height} #{box.ocr_text}"
            lines.append(line)
        return '\n'.join(lines)
    
    def save_to_file(self, file_path: str) -> bool:
        """Save labels to DAT file"""
        try:
            DATParser.save_dat_file(file_path, self.boxes)
            self.unsaved_changes = False
            self.last_save_time[file_path] = time.time()
            
            if self.on_status_update:
                self.on_status_update(f"Saved {len(self.boxes)} labels to {Path(file_path).name}")
            
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Save error: {e}")
            return False
    
    def load_from_file(self, file_path: str) -> bool:
        """Load labels from DAT file"""
        try:
            boxes = DATParser.parse_dat_file(file_path)
            self.set_boxes(boxes)
            
            if self.on_status_update:
                self.on_status_update(f"Loaded {len(boxes)} labels from {Path(file_path).name}")
            
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Load error: {e}")
            return False


class OCRProcessor:
    """Handles OCR processing for labels"""
    
    def __init__(self, class_config: Dict[str, Any]):
        self.class_config = class_config
        self.on_ocr_complete = None
        self.on_ocr_error = None
        self.on_status_update = None
    
    def process_ocr(self, image_path: str, box: BoundingBox, callback: Callable = None):
        """Process OCR for a bounding box"""
        thread = threading.Thread(target=self._run_ocr_thread, args=(image_path, box, callback))
        thread.daemon = True
        thread.start()
    
    def _run_ocr_thread(self, image_path: str, box: BoundingBox, callback: Callable = None):
        """Run OCR in background thread"""
        try:
            # Import dependencies
            try:
                import pytesseract
                from PIL import Image
                import cv2
                import numpy as np
            except ImportError as e:
                error_msg = f"Required OCR libraries not available: {str(e)}\nInstall: pip install pytesseract pillow opencv-python"
                if self.on_ocr_error:
                    self.on_ocr_error(error_msg)
                return
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                if self.on_ocr_error:
                    self.on_ocr_error("Failed to load image")
                return
            
            # Extract ROI
            x, y, w, h = int(box.x), int(box.y), int(box.width), int(box.height)
            img_height, img_width = image.shape[:2]
            
            # Clamp coordinates
            x = max(0, min(x, img_width - 1))
            y = max(0, min(y, img_height - 1))
            w = max(1, min(w, img_width - x))
            h = max(1, min(h, img_height - y))
            
            roi = image[y:y+h, x:x+w]
            
            if roi.size == 0:
                if self.on_ocr_error:
                    self.on_ocr_error("Invalid label region")
                return
            
            # Preprocess image
            processed_roi = ImageOperations.preprocess_image_by_field_type(
                roi, box.class_id, self.class_config)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(processed_roi)
            
            # Get Tesseract config
            custom_config = ImageOperations.get_tesseract_config_for_class(
                box.class_id, self.class_config)
            
            # Run OCR
            extracted_text = pytesseract.image_to_string(
                pil_image, config=custom_config).strip()
            
            # Post-process text
            final_text = ImageOperations.postprocess_text_by_field_type(
                extracted_text, box.class_id, self.class_config)
            
            # Call completion callback
            if self.on_ocr_complete:
                self.on_ocr_complete(final_text, box.ocr_text)
            
            if callback:
                callback(final_text)
                
        except Exception as e:
            if self.on_ocr_error:
                self.on_ocr_error(f"OCR error: {str(e)}")


class ConfirmationManager:
    """Manages confirmation status for files"""
    
    def __init__(self):
        self.confirmation_status = {}
        self.on_confirmation_changed = None
    
    def set_confirmation(self, file_path: str, confirmed: bool):
        """Set confirmation status for a file"""
        self.confirmation_status[file_path] = confirmed
        if self.on_confirmation_changed:
            self.on_confirmation_changed(file_path, confirmed)
    
    def get_confirmation(self, file_path: str) -> bool:
        """Get confirmation status for a file"""
        return self.confirmation_status.get(file_path, False)
    
    def toggle_confirmation(self, file_path: str) -> bool:
        """Toggle confirmation status for a file"""
        current = self.get_confirmation(file_path)
        new_status = not current
        self.set_confirmation(file_path, new_status)
        return new_status
    
    def get_confirmation_summary(self) -> Dict[str, int]:
        """Get summary of confirmation status"""
        confirmed = sum(1 for status in self.confirmation_status.values() if status)
        total = len(self.confirmation_status)
        return {
            'confirmed': confirmed,
            'unconfirmed': total - confirmed,
            'total': total
        }