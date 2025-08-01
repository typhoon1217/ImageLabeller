#!/usr/bin/env python3

import threading
import time
import sqlite3
import json
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
        
        # Deletion history database
        self.db_path = None
        self.max_history_size = 20
        
        # Callbacks
        self.on_box_selected = None
        self.on_boxes_changed = None
        self.on_status_update = None
        self.on_error = None
        
    def set_boxes(self, boxes: List[BoundingBox]):
        """Set the current list of boxes"""
        self.boxes = boxes
    
    def init_deletion_history_db(self, directory_path: str):
        """Initialize deletion history database for current directory"""
        if not directory_path:
            return
        
        try:
            # Create database in the same directory as the images
            db_dir = Path(directory_path)
            self.db_path = db_dir / "deletion_history.db"
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deletion_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT NOT NULL,
                    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    x1 INTEGER NOT NULL,
                    y1 INTEGER NOT NULL,
                    x2 INTEGER NOT NULL,
                    y2 INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    ocr_text TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error initializing deletion history database: {e}")
            self.db_path = None
    
    def sync_deletion_history_with_directory(self, directory_path: str):
        """Sync deletion history database with files in directory"""
        if not self.db_path:
            return
        
        try:
            from pathlib import Path
            
            # Get all image files in directory
            directory = Path(directory_path)
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
            current_files = set()
            
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    current_files.add(str(file_path))
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get all image paths in database
            cursor.execute('SELECT DISTINCT image_path FROM deletion_history')
            db_files = set(row[0] for row in cursor.fetchall())
            
            # Remove entries for files that no longer exist
            removed_files = db_files - current_files
            if removed_files:
                for file_path in removed_files:
                    cursor.execute('DELETE FROM deletion_history WHERE image_path = ?', (file_path,))
                print(f"Removed {len(removed_files)} deleted file entries from deletion history")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error syncing deletion history with directory: {e}")
    
    def save_deleted_box(self, image_path: str, box: BoundingBox):
        """Save deleted box to history database"""
        if not self.db_path:
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Insert deleted box
            cursor.execute('''
                INSERT INTO deletion_history 
                (image_path, x1, y1, x2, y2, class_id, ocr_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (image_path, box.x1, box.y1, box.x2, box.y2, box.class_id, box.ocr_text))
            
            # Keep only last 20 deletions per image
            cursor.execute('''
                DELETE FROM deletion_history 
                WHERE image_path = ? AND id NOT IN (
                    SELECT id FROM deletion_history 
                    WHERE image_path = ? 
                    ORDER BY deleted_at DESC 
                    LIMIT ?
                )
            ''', (image_path, image_path, self.max_history_size))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error saving deleted box: {e}")
    
    def restore_last_deleted_box(self, image_path: str) -> Optional[BoundingBox]:
        """Restore the last deleted box for current image"""
        if not self.db_path:
            return None
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get the most recent deleted box for this image
            cursor.execute('''
                SELECT x1, y1, x2, y2, class_id, ocr_text, id
                FROM deletion_history 
                WHERE image_path = ? 
                ORDER BY deleted_at DESC 
                LIMIT 1
            ''', (image_path,))
            
            result = cursor.fetchone()
            if result:
                x1, y1, x2, y2, class_id, ocr_text, box_id = result
                
                # Remove from history
                cursor.execute('DELETE FROM deletion_history WHERE id = ?', (box_id,))
                conn.commit()
                
                # Create restored box
                restored_box = BoundingBox(x1, y1, x2, y2, class_id, ocr_text or "")
                conn.close()
                return restored_box
            
            conn.close()
            return None
            
        except Exception as e:
            print(f"Error restoring deleted box: {e}")
            return None
        
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
    
    def delete_selected_box(self, current_image_path: str = None) -> bool:
        """Delete the currently selected box"""
        if self.selected_box:
            # Save to deletion history if image path is provided
            if current_image_path:
                self.save_deleted_box(current_image_path, self.selected_box)
            
            self.boxes.remove(self.selected_box)
            self.selected_box = None
            self.mark_changed()
            
            if self.on_box_selected:
                self.on_box_selected(None)
            
            return True
        return False
    
    def restore_deleted_label(self, current_image_path: str) -> bool:
        """Restore the last deleted label for current image"""
        if not current_image_path:
            return False
        
        restored_box = self.restore_last_deleted_box(current_image_path)
        if restored_box:
            self.boxes.append(restored_box)
            self.selected_box = restored_box
            self.mark_changed()
            
            if self.on_box_selected:
                self.on_box_selected(restored_box)
            
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
        """Get character counts for OCR text by class (deprecated - table now handled in UI)"""
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
        self.easyocr_reader = None  # Will be initialized on first use
        # Note: PaddleOCR instances are created fresh each time to avoid threading issues
    
    def process_ocr(self, image_path: str, box: BoundingBox, ocr_engine: str = "tesseract", callback: Callable = None):
        """Process OCR for a bounding box with specified OCR engine"""
        thread = threading.Thread(target=self._run_ocr_thread, args=(image_path, box, ocr_engine, callback))
        thread.daemon = True
        thread.start()
    
    def _run_ocr_thread(self, image_path: str, box: BoundingBox, ocr_engine: str = "tesseract", callback: Callable = None):
        """Run OCR in background thread"""
        try:
            print(f"[OCR] Starting OCR thread for image: {image_path}")
            print(f"[OCR] Box coordinates: x={box.x}, y={box.y}, w={box.width}, h={box.height}, class_id={box.class_id}")
            
            # Import dependencies
            try:
                print("[OCR] Importing dependencies...")
                import pytesseract
                from PIL import Image
                import cv2
                import numpy as np
                print("[OCR] Dependencies imported successfully")
            except ImportError as e:
                print(f"[OCR] Import error: {e}")
                error_msg = f"Required OCR libraries not available: {str(e)}\nInstall: pip install pytesseract pillow opencv-python"
                if self.on_ocr_error:
                    self.on_ocr_error(error_msg)
                return
            
            # Load image
            print(f"[OCR] Loading image: {image_path}")
            image = cv2.imread(image_path)
            if image is None:
                print("[OCR] Failed to load image")
                if self.on_ocr_error:
                    self.on_ocr_error("Failed to load image")
                return
            
            print(f"[OCR] Image loaded successfully, shape: {image.shape}")
            
            # Extract ROI
            x, y, w, h = int(box.x), int(box.y), int(box.width), int(box.height)
            img_height, img_width = image.shape[:2]
            
            print(f"[OCR] Original coordinates: x={x}, y={y}, w={w}, h={h}")
            print(f"[OCR] Image dimensions: {img_width}x{img_height}")
            
            # Clamp coordinates
            x = max(0, min(x, img_width - 1))
            y = max(0, min(y, img_height - 1))
            w = max(1, min(w, img_width - x))
            h = max(1, min(h, img_height - y))
            
            print(f"[OCR] Clamped coordinates: x={x}, y={y}, w={w}, h={h}")
            
            roi = image[y:y+h, x:x+w]
            print(f"[OCR] ROI extracted, shape: {roi.shape}")
            
            if roi.size == 0:
                print("[OCR] ROI size is 0")
                if self.on_ocr_error:
                    self.on_ocr_error("Invalid label region")
                return
            
            # Preprocess image
            print("[OCR] Starting image preprocessing...")
            try:
                processed_roi = ImageOperations.preprocess_image_by_field_type(
                    roi, box.class_id, self.class_config)
                print(f"[OCR] Image preprocessing completed, shape: {processed_roi.shape}")
            except Exception as e:
                print(f"[OCR] Preprocessing error: {e}")
                processed_roi = roi  # Fallback to original ROI
            
            # Convert to PIL Image
            print("[OCR] Converting to PIL Image...")
            try:
                pil_image = Image.fromarray(processed_roi)
                print(f"[OCR] PIL Image created, mode: {pil_image.mode}, size: {pil_image.size}")
            except Exception as e:
                print(f"[OCR] PIL conversion error: {e}")
                # Try with RGB conversion
                if len(processed_roi.shape) == 3:
                    processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(processed_roi)
                print(f"[OCR] PIL Image created after RGB conversion, mode: {pil_image.mode}")
            
            # Run OCR based on selected engine
            print(f"[OCR] Using OCR engine: {ocr_engine}")
            
            if ocr_engine == "tesseract":
                final_text = self._run_tesseract_ocr(pil_image, box)
            elif ocr_engine == "easyocr":
                final_text = self._run_easyocr_ocr(pil_image, box)
            elif ocr_engine == "paddleocr":
                final_text = self._run_paddleocr_ocr(pil_image, box)
            elif ocr_engine == "vietocr":
                final_text = self._run_vietocr_ocr(pil_image, box)
            else:
                raise ValueError(f"Unknown OCR engine: {ocr_engine}")
            
            # Call completion callback
            print("[OCR] Calling completion callback...")
            if self.on_ocr_complete:
                self.on_ocr_complete(final_text, box.ocr_text)
            
            if callback:
                callback(final_text)
            
            print("[OCR] OCR thread completed successfully")
                
        except Exception as e:
            print(f"[OCR] Exception in OCR thread: {str(e)}")
            import traceback
            traceback.print_exc()
            if self.on_ocr_error:
                self.on_ocr_error(f"OCR error: {str(e)}")
    
    def _run_tesseract_ocr(self, pil_image, box: BoundingBox) -> str:
        """Run Tesseract OCR on the image"""
        print("[OCR] Running Tesseract OCR...")
        
        # Import Tesseract
        try:
            import pytesseract
        except ImportError as e:
            raise ImportError("Tesseract not available. Install: pip install pytesseract")
        
        # Get Tesseract config
        print("[OCR] Getting Tesseract config...")
        try:
            custom_config = ImageOperations.get_tesseract_config_for_class(
                box.class_id, self.class_config)
            print(f"[OCR] Tesseract config: {custom_config}")
        except Exception as e:
            print(f"[OCR] Config error: {e}")
            custom_config = ""  # Fallback to default config
        
        # Run OCR
        try:
            extracted_text = pytesseract.image_to_string(
                pil_image, config=custom_config).strip()
            print(f"[OCR] Tesseract completed, extracted text: '{extracted_text}'")
        except Exception as e:
            print(f"[OCR] Tesseract error: {e}")
            raise
        
        # Post-process text
        print("[OCR] Post-processing text...")
        try:
            final_text = ImageOperations.postprocess_text_by_field_type(
                extracted_text, box.class_id, self.class_config)
            print(f"[OCR] Post-processing completed, final text: '{final_text}'")
        except Exception as e:
            print(f"[OCR] Post-processing error: {e}")
            final_text = extracted_text  # Fallback to raw text
        
        return final_text
    
    def _run_easyocr_ocr(self, pil_image, box: BoundingBox) -> str:
        """Run EasyOCR on the image"""
        print("[OCR] Running EasyOCR...")
        
        # Import EasyOCR and numpy
        try:
            import easyocr
            import numpy as np
        except ImportError as e:
            raise ImportError("EasyOCR not available. Install: pip install easyocr")
        
        # Initialize reader if not already done
        if self.easyocr_reader is None:
            print("[OCR] Initializing EasyOCR reader...")
            self.easyocr_reader = easyocr.Reader(['en'])
            print("[OCR] EasyOCR reader initialized")
        
        # Convert PIL image to numpy array
        np_image = np.array(pil_image)
        
        # Run EasyOCR
        try:
            results = self.easyocr_reader.readtext(np_image)
            
            # Extract text from results
            extracted_text = " ".join([result[1] for result in results]).strip()
            print(f"[OCR] EasyOCR completed, extracted text: '{extracted_text}'")
        except Exception as e:
            print(f"[OCR] EasyOCR error: {e}")
            raise
        
        # Post-process text
        print("[OCR] Post-processing text...")
        try:
            final_text = ImageOperations.postprocess_text_by_field_type(
                extracted_text, box.class_id, self.class_config)
            print(f"[OCR] Post-processing completed, final text: '{final_text}'")
        except Exception as e:
            print(f"[OCR] Post-processing error: {e}")
            final_text = extracted_text  # Fallback to raw text
        
        return final_text
    
    def _run_paddleocr_ocr(self, pil_image, box: BoundingBox) -> str:
        """Run PaddleOCR on the image"""
        print("[OCR] Running PaddleOCR...")
        
        # Import PaddleOCR - check what's available
        try:
            from paddleocr import PaddleOCR
            from PIL import Image
            import numpy as np
            print("[OCR] Using PaddleOCR API")
        except ImportError as e:
            raise ImportError("PaddleOCR not available. Install: pip install paddleocr")
        
        # Create a fresh PaddleOCR instance for this OCR operation only
        print("[OCR] Creating fresh PaddleOCR reader instance for this operation...")
        try:
            # Use minimal PaddleOCR configuration to avoid complex state issues
            paddleocr_reader = PaddleOCR()
            print("[OCR] Fresh PaddleOCR reader created successfully")
        except Exception as e:
            print(f"[OCR] Fresh PaddleOCR creation failed: {e}")
            # If we can't create a fresh instance, the system may have deeper issues
            raise e
        
        # Convert PIL image to numpy array and ensure it's in the correct format
        # PaddleOCR works better with higher resolution and good contrast
        
        # Scale up small images for better OCR results
        original_size = pil_image.size
        if min(original_size) < 32:
            # Scale up very small images
            scale_factor = max(2, 64 // min(original_size))
            new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
            pil_image = pil_image.resize(new_size, Image.LANCZOS)
            print(f"[OCR] Scaled up image from {original_size} to {new_size}")
        
        if pil_image.mode != 'RGB':
            print(f"[OCR] Converting image from {pil_image.mode} to RGB")
            pil_image = pil_image.convert('RGB')
        
        np_image = np.array(pil_image)
        print(f"[OCR] Image shape: {np_image.shape}, dtype: {np_image.dtype}")
        
        # Ensure image has 3 dimensions (height, width, channels)
        if len(np_image.shape) == 2:
            # Grayscale image, convert to RGB by stacking
            print("[OCR] Converting grayscale to RGB format")
            np_image = np.stack([np_image] * 3, axis=-1)
        elif len(np_image.shape) == 3 and np_image.shape[2] == 1:
            # Single channel with explicit dimension
            print("[OCR] Converting single channel to RGB format")
            np_image = np.concatenate([np_image] * 3, axis=2)
        elif len(np_image.shape) == 3 and np_image.shape[2] == 4:
            # RGBA image, remove alpha channel
            print("[OCR] Converting RGBA to RGB format")
            np_image = np_image[:, :, :3]
        
        print(f"[OCR] Final image shape for PaddleOCR: {np_image.shape}")
        
        # Run PaddleOCR
        try:
            # Use standard ocr method which is more stable than predict
            results = paddleocr_reader.ocr(np_image)
            print(f"[OCR] PaddleOCR ocr results type: {type(results)}")
            extracted_text = self._parse_standard_paddleocr_results(results)
            
            print(f"[OCR] PaddleOCR completed, extracted text: '{extracted_text}'")
        except Exception as e:
            print(f"[OCR] PaddleOCR error during processing: {e}")
            import traceback
            traceback.print_exc()
            # Return empty string instead of raising to allow graceful fallback
            return ""
        
        # Post-process text
        print("[OCR] Post-processing text...")
        try:
            final_text = ImageOperations.postprocess_text_by_field_type(
                extracted_text, box.class_id, self.class_config)
            print(f"[OCR] Post-processing completed, final text: '{final_text}'")
        except Exception as e:
            print(f"[OCR] Post-processing error: {e}")
            final_text = extracted_text  # Fallback to raw text
        
        # Clean up PaddleOCR instance to prevent state corruption
        print("[OCR] Cleaning up PaddleOCR instance...")
        try:
            if 'paddleocr_reader' in locals() and paddleocr_reader is not None:
                del paddleocr_reader
                print("[OCR] PaddleOCR instance cleaned up successfully")
        except Exception as cleanup_error:
            print(f"[OCR] Cleanup error (non-critical): {cleanup_error}")
        
        return final_text
    
    def _parse_standard_paddleocr_results(self, results) -> str:
        """Parse standard PaddleOCR results format"""
        extracted_text = ""
        
        if results is None:
            print("[OCR] Standard PaddleOCR returned None")
            return ""
        
        try:
            # Debug: print structure (safely)
            print(f"[OCR] Standard PaddleOCR results type: {type(results)}")
            print(f"[OCR] Results length: {len(results) if isinstance(results, list) else 'not a list'}")
            
            # Based on the logs showing complex nested structure, try multiple parsing approaches
            if isinstance(results, list) and len(results) > 0:
                first_result = results[0]
                print(f"[OCR] First result type: {type(first_result)}")
                
                # Approach 1: Standard PaddleOCR format: [[[bbox], (text, confidence)], ...]
                if isinstance(first_result, list):
                    print(f"[OCR] First result is list with {len(first_result)} items")
                    for detection in first_result:
                        try:
                            if isinstance(detection, list) and len(detection) >= 2:
                                # detection[0] is bbox, detection[1] is (text, confidence)
                                text_data = detection[1]
                                if isinstance(text_data, (list, tuple)) and len(text_data) >= 1:
                                    text = str(text_data[0])
                                    if text and text.strip():
                                        extracted_text += text + " "
                                        print(f"[OCR] Extracted text fragment: '{text}'")
                        except (IndexError, TypeError) as e:
                            print(f"[OCR] Error parsing detection: {e}")
                            continue
                
                # Approach 2: Handle complex PaddleX-style nested structure  
                elif isinstance(first_result, dict):
                    print("[OCR] First result is dict, trying to extract text fields")
                    extracted_text = self._extract_text_from_dict(first_result)
                
                # Approach 3: Handle single string result
                elif isinstance(first_result, str):
                    print("[OCR] First result is string")
                    extracted_text = first_result
            
            extracted_text = extracted_text.strip()
            print(f"[OCR] Final extracted text: '{extracted_text}'")
            
        except Exception as e:
            print(f"[OCR] Error parsing standard PaddleOCR results: {e}")
            import traceback
            traceback.print_exc()
            
        return extracted_text
    
    def _extract_text_from_dict(self, result_dict, depth=0) -> str:
        """Extract text from complex nested dictionary structure"""
        if depth > 5:  # Prevent infinite recursion
            return ""
        
        extracted = ""
        
        # Look for common text field names
        text_fields = ['text', 'rec_text', 'ocr_text', 'recognized_text', 'result_text']
        
        for field in text_fields:
            if field in result_dict:
                value = result_dict[field]
                if isinstance(value, str) and value.strip():
                    extracted += value + " "
                    print(f"[OCR] Found text in field '{field}': '{value}'")
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            extracted += item + " "
                        elif isinstance(item, dict):
                            extracted += self._extract_text_from_dict(item, depth + 1)
        
        # If no direct text fields found, search recursively
        if not extracted:
            for key, value in result_dict.items():
                if isinstance(value, dict):
                    extracted += self._extract_text_from_dict(value, depth + 1)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            extracted += self._extract_text_from_dict(item, depth + 1)
                        elif isinstance(item, str) and item.strip():
                            extracted += item + " "
        
        return extracted
    
    def _run_vietocr_ocr(self, pil_image, box: BoundingBox) -> str:
        """Run VietOCR on the image for Vietnamese text recognition"""
        print("[OCR] Running VietOCR...")
        
        # Import VietOCR
        try:
            from vietocr.tool.predictor import Predictor
            from vietocr.tool.config import Cfg
            print("[OCR] VietOCR modules imported successfully")
        except ImportError as e:
            raise ImportError("VietOCR not available. Install: pip install vietocr")
        
        # Get VietOCR configuration
        print("[OCR] Setting up VietOCR configuration...")
        try:
            # Load pretrained Vietnamese transformer model
            config = Cfg.load_config_from_name('vgg_transformer')
            
            # Configure for CPU usage (can be changed to 'cuda:0' if GPU available)
            config['device'] = 'cpu'
            
            # Ensure reproducible results
            config['predictor']['beamsearch'] = False
            
            print(f"[OCR] VietOCR config loaded: device={config['device']}")
        except Exception as e:
            print(f"[OCR] VietOCR config error: {e}")
            raise e
        
        # Initialize VietOCR predictor
        print("[OCR] Initializing VietOCR predictor...")
        try:
            detector = Predictor(config)
            print("[OCR] VietOCR predictor initialized successfully")
        except Exception as e:
            print(f"[OCR] VietOCR predictor initialization failed: {e}")
            raise e
        
        # Scale up small images for better OCR results (similar to PaddleOCR preprocessing)
        original_size = pil_image.size
        if min(original_size) < 32:
            # Scale up very small images
            from PIL import Image
            scale_factor = max(2, 64 // min(original_size))
            new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
            pil_image = pil_image.resize(new_size, Image.LANCZOS)
            print(f"[OCR] Scaled up image from {original_size} to {new_size}")
        
        # Run OCR
        print("[OCR] Running VietOCR prediction...")
        try:
            extracted_text = detector.predict(pil_image, return_prob=False)
            if extracted_text is None:
                extracted_text = ""
            extracted_text = str(extracted_text).strip()
            print(f"[OCR] VietOCR completed, extracted text: '{extracted_text}'")
        except Exception as e:
            print(f"[OCR] VietOCR prediction error: {e}")
            raise
        
        # Post-process text
        print("[OCR] Post-processing text...")
        try:
            final_text = ImageOperations.postprocess_text_by_field_type(
                extracted_text, box.class_id, self.class_config)
            print(f"[OCR] Post-processing completed, final text: '{final_text}'")
        except Exception as e:
            print(f"[OCR] Post-processing error: {e}")
            final_text = extracted_text  # Fallback to raw text
        
        # Clean up VietOCR predictor to prevent memory issues
        print("[OCR] Cleaning up VietOCR predictor...")
        try:
            if 'detector' in locals() and detector is not None:
                del detector
                print("[OCR] VietOCR predictor cleaned up successfully")
        except Exception as cleanup_error:
            print(f"[OCR] Cleanup error (non-critical): {cleanup_error}")
        
        return final_text


class ConfirmationManager:
    """Manages confirmation status for files using SQLite database"""
    
    def __init__(self, directory_path: str = None):
        self.confirmation_status = {}
        self.directory_path = directory_path
        self.db_path = None
        self.on_confirmation_changed = None
        
        # Initialize database if directory provided
        if self.directory_path:
            self.init_database()
    
    def set_confirmation(self, file_path: str, confirmed: bool):
        """Set confirmation status for a file"""
        self.confirmation_status[file_path] = confirmed
        if self.on_confirmation_changed:
            self.on_confirmation_changed(file_path, confirmed)
        
        # Save status to database
        self.save_to_database(file_path, confirmed)
    
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
    
    def init_database(self):
        """Initialize SQLite database for the current directory"""
        if not self.directory_path:
            return
        
        try:
            import sqlite3
            from pathlib import Path
            
            # Create database file in the image directory
            dir_path = Path(self.directory_path)
            self.db_path = dir_path / '.label_editor.db'
            
            # Initialize database schema
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_confirmations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    confirmed INTEGER NOT NULL DEFAULT 0,
                    confirmed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_path ON file_confirmations(file_path)
            ''')
            
            conn.commit()
            conn.close()
            
            # Load existing confirmations into memory
            self.load_from_database()
            
        except Exception as e:
            print(f"Error initializing database: {e}")
    
    def save_to_database(self, file_path: str, confirmed: bool):
        """Save confirmation status to SQLite database"""
        if not self.db_path:
            return
        
        try:
            import sqlite3
            from pathlib import Path
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            filename = Path(file_path).name
            confirmed_at = 'CURRENT_TIMESTAMP' if confirmed else None
            
            # Insert or update confirmation status
            cursor.execute('''
                INSERT OR REPLACE INTO file_confirmations 
                (file_path, filename, confirmed, confirmed_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (file_path, filename, int(confirmed), confirmed_at))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error saving to database: {e}")
    
    def load_from_database(self):
        """Load confirmation status from SQLite database"""
        if not self.db_path:
            return
        
        try:
            import sqlite3
            from pathlib import Path
            
            if not Path(self.db_path).exists():
                return
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Load all confirmations
            cursor.execute('SELECT file_path, confirmed FROM file_confirmations')
            rows = cursor.fetchall()
            
            self.confirmation_status = {}
            for file_path, confirmed in rows:
                self.confirmation_status[file_path] = bool(confirmed)
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading from database: {e}")
            self.confirmation_status = {}
    
    def get_confirmation_stats(self) -> dict:
        """Get detailed confirmation statistics from database"""
        if not self.db_path:
            return {'total': 0, 'confirmed': 0, 'unconfirmed': 0}
        
        try:
            import sqlite3
            from pathlib import Path
            
            if not Path(self.db_path).exists():
                return {'total': 0, 'confirmed': 0, 'unconfirmed': 0}
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get statistics
            cursor.execute('SELECT COUNT(*) FROM file_confirmations')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM file_confirmations WHERE confirmed = 1')
            confirmed = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total': total,
                'confirmed': confirmed,
                'unconfirmed': total - confirmed
            }
            
        except Exception as e:
            print(f"Error getting stats from database: {e}")
            return {'total': 0, 'confirmed': 0, 'unconfirmed': 0}
    
    def sync_confirmation_db_with_directory(self, directory_path: str):
        """Sync confirmation database with files in directory"""
        if not self.db_path:
            return
        
        try:
            import sqlite3
            from pathlib import Path
            
            # Get all image files in directory
            directory = Path(directory_path)
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
            current_files = set()
            
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    current_files.add(str(file_path))
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get all file paths in database
            cursor.execute('SELECT file_path FROM file_confirmations')
            db_files = set(row[0] for row in cursor.fetchall())
            
            # Remove entries for files that no longer exist
            removed_files = db_files - current_files
            if removed_files:
                for file_path in removed_files:
                    cursor.execute('DELETE FROM file_confirmations WHERE file_path = ?', (file_path,))
                print(f"Removed {len(removed_files)} deleted file entries from confirmation database")
            
            conn.commit()
            conn.close()
            
            # Reload confirmation status from database
            self.load_from_database()
            
        except Exception as e:
            print(f"Error syncing confirmation database with directory: {e}")
    
    def set_directory(self, directory_path: str):
        """Set new directory and reinitialize database"""
        self.directory_path = directory_path
        self.confirmation_status = {}
        self.init_database()
    
    def get_confirmed_files(self) -> list:
        """Get list of all confirmed files"""
        if not self.db_path:
            return []
        
        try:
            import sqlite3
            from pathlib import Path
            
            if not Path(self.db_path).exists():
                return []
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT file_path, filename, confirmed_at 
                FROM file_confirmations 
                WHERE confirmed = 1 
                ORDER BY confirmed_at DESC
            ''')
            
            confirmed_files = []
            for row in cursor.fetchall():
                confirmed_files.append({
                    'path': row[0],
                    'filename': row[1],
                    'confirmed_at': row[2]
                })
            
            conn.close()
            return confirmed_files
            
        except Exception as e:
            print(f"Error getting confirmed files: {e}")
            return []
