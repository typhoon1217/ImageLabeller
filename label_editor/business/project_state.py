#!/usr/bin/env python3

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from ..core.validation import ValidationEngine


class ProjectManager:
    """Manages project state including directory loading and file tracking"""
    
    def __init__(self, config_file_path: str):
        self.config_file = Path(config_file_path)
        self.config = self.load_config()
        self.class_config = self._parse_class_config()
        
        # Project state
        self.current_directory = None
        self.image_files = []
        self.current_index = -1
        self.current_image_path = None
        self.current_dat_path = None
        
        # File tracking
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        self.last_save_time = {}
        self.pending_operations = {}
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="gui_ops")
        
        # Validation
        self.validation_engine = ValidationEngine(self.class_config)
        
        # Callbacks
        self.on_directory_loaded = None
        self.on_image_changed = None
        self.on_status_update = None
        self.on_error = None
        
        # Initialize current directory if specified
        default_dir = self.config.get('default_directory')
        if default_dir and Path(default_dir).exists():
            self.current_directory = Path(default_dir)
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from settings.json"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            if self.on_error:
                self.on_error(f"Config load error: {e}")
        return {}
    
    def save_config(self, additional_config: Dict[str, Any] = None):
        """Save configuration to settings.json"""
        try:
            existing_config = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, 'r') as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            
            # Update with current state
            if self.current_directory:
                existing_config['default_directory'] = str(self.current_directory)
            
            # Add any additional config
            if additional_config:
                existing_config.update(additional_config)
            
            with open(self.config_file, 'w') as f:
                json.dump(existing_config, f, indent=2)
                
        except (OSError, ValueError) as e:
            if self.on_error:
                self.on_error(f"Config save error: {e}")
    
    def _parse_class_config(self) -> Dict[str, Any]:
        """Parse class configuration from config"""
        classes_data = self.config.get("classes")
        if classes_data:
            if isinstance(classes_data, dict) and "classes" in classes_data:
                return classes_data
            elif isinstance(classes_data, dict) and "classes" not in classes_data:
                return {"classes": classes_data} if isinstance(classes_data, list) else classes_data
            else:
                return {"classes": classes_data} if isinstance(classes_data, list) else {"classes": []}
        else:
            return {"classes": []}
    
    def load_directory(self, directory_path: str) -> bool:
        """Load a directory and scan for image files"""
        try:
            self.current_directory = Path(directory_path)
            self.image_files = []
            
            # Scan for image files
            for file_path in self.current_directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.image_extensions:
                    self.image_files.append(file_path)
            
            self.image_files.sort()
            
            # Validate files
            self.validation_engine.validation_cache = self.validation_engine.validate_all_files(
                self.image_files, self.image_extensions)
            
            # Reset current image
            self.current_index = -1
            self.current_image_path = None
            self.current_dat_path = None
            
            # Load first image if available
            if self.image_files:
                self.current_index = 0
                self.current_image_path = str(self.image_files[0])
                self.current_dat_path = self.image_files[0].with_suffix('.dat')
            
            # Save directory to config
            self.save_config()
            
            if self.on_directory_loaded:
                self.on_directory_loaded(len(self.image_files))
            
            if self.on_status_update:
                self.on_status_update(f"Loaded {len(self.image_files)} images from {directory_path}")
            
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Error loading directory: {e}")
            return False
    
    def navigate_to_image(self, index: int) -> bool:
        """Navigate to specific image by index"""
        if 0 <= index < len(self.image_files):
            self.current_index = index
            self.current_image_path = str(self.image_files[index])
            self.current_dat_path = self.image_files[index].with_suffix('.dat')
            
            if self.on_image_changed:
                self.on_image_changed(self.current_image_path, self.current_dat_path)
            
            return True
        return False
    
    def navigate_next(self) -> bool:
        """Navigate to next image"""
        if self.current_index < len(self.image_files) - 1:
            return self.navigate_to_image(self.current_index + 1)
        return False
    
    def navigate_previous(self) -> bool:
        """Navigate to previous image"""
        if self.current_index > 0:
            return self.navigate_to_image(self.current_index - 1)
        return False
    
    def get_current_image_info(self) -> Dict[str, Any]:
        """Get information about current image"""
        if self.current_image_path:
            return {
                'path': self.current_image_path,
                'dat_path': str(self.current_dat_path),
                'index': self.current_index,
                'total': len(self.image_files),
                'filename': Path(self.current_image_path).name,
                'dat_exists': self.current_dat_path.exists() if self.current_dat_path else False
            }
        return {}
    
    def get_navigation_state(self) -> Dict[str, bool]:
        """Get navigation button states"""
        return {
            'can_go_previous': self.current_index > 0,
            'can_go_next': self.current_index < len(self.image_files) - 1
        }
    
    def get_file_list(self) -> List[Dict[str, Any]]:
        """Get list of files with validation status"""
        file_list = []
        for i, file_path in enumerate(self.image_files):
            validation = self.validation_engine.validation_cache.get(str(file_path), {})
            file_list.append({
                'index': i,
                'name': file_path.name,
                'path': str(file_path),
                'validation_status': self.validation_engine.get_file_validation_status(str(file_path)),
                'is_current': i == self.current_index,
                'has_dat': file_path.with_suffix('.dat').exists(),
                'box_count': validation.get('box_count', 0)
            })
        return file_list
    
    def get_directory_stats(self) -> Dict[str, Any]:
        """Get directory statistics"""
        if not self.current_directory:
            return {'loaded': False}
        
        validation_summary = self.validation_engine.get_validation_summary(
            self.validation_engine.validation_cache)
        
        return {
            'loaded': True,
            'directory': str(self.current_directory),
            'total_files': len(self.image_files),
            'current_index': self.current_index,
            'validation_summary': validation_summary
        }
    
    # Removed find_first_unconfirmed_image - using simple next image navigation
    
    def perform_background_save(self, image_path: str, boxes_snapshot: List):
        """Perform background save operation"""
        def save_operation():
            try:
                from ..core.file_io import DATParser
                image_path_obj = Path(image_path)
                dat_path = image_path_obj.with_suffix('.dat')
                
                if boxes_snapshot:
                    DATParser.save_dat_file(str(dat_path), boxes_snapshot)
                    self.last_save_time[image_path] = time.time()
                    
            except Exception as e:
                if self.on_error:
                    self.on_error(f"Error saving in background: {e}")
        
        self.executor.submit(save_operation)
    
# File permission changes removed - confirmation now only records status
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)


class FileTracker:
    """Tracks file states and operations"""
    
    def __init__(self):
        self.last_save_time = {}
        self.confirmation_status = {}
        self.pending_operations = {}
    
    def mark_saved(self, file_path: str):
        """Mark file as saved"""
        self.last_save_time[file_path] = time.time()
    
    def get_last_save_time(self, file_path: str) -> Optional[float]:
        """Get last save time for file"""
        return self.last_save_time.get(file_path)
    
    def set_confirmation_status(self, file_path: str, confirmed: bool):
        """Set confirmation status for file"""
        self.confirmation_status[file_path] = confirmed
    
    def get_confirmation_status(self, file_path: str) -> bool:
        """Get confirmation status for file"""
        return self.confirmation_status.get(file_path, False)
    
    def add_pending_operation(self, operation_key: str, operation):
        """Add pending operation"""
        self.pending_operations[operation_key] = operation
    
    def remove_pending_operation(self, operation_key: str):
        """Remove pending operation"""
        self.pending_operations.pop(operation_key, None)
    
    def get_file_status(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file status"""
        return {
            'last_saved': self.get_last_save_time(file_path),
            'confirmed': self.get_confirmation_status(file_path),
            'has_pending_operations': any(
                key.endswith(file_path) for key in self.pending_operations.keys()
            )
        }