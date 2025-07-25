#!/usr/bin/env python3
"""
Image rotation operations including transformation and saving
"""

import gi
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gdk', '4.0')
from gi.repository import GdkPixbuf, Gdk
from pathlib import Path
from typing import List, Tuple, Optional
import math
from .data_types import BoundingBox


class ImageRotator:
    """Handles image rotation operations"""
    
    @staticmethod
    def rotate_pixbuf(pixbuf: GdkPixbuf.Pixbuf, angle: int) -> GdkPixbuf.Pixbuf:
        """
        Rotate a pixbuf by the specified angle
        
        Args:
            pixbuf: Source pixbuf
            angle: Rotation angle in degrees (90, 180, 270, or multiples)
            
        Returns:
            Rotated pixbuf
        """
        if not pixbuf:
            return None
        
        # Normalize angle to 0, 90, 180, 270
        angle = angle % 360
        
        if angle == 0:
            return pixbuf.copy()
        elif angle == 90:
            return pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.CLOCKWISE)
        elif angle == 180:
            return pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.UPSIDEDOWN)
        elif angle == 270:
            return pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE)
        else:
            # For arbitrary angles, we'll need to use Cairo (more complex)
            return ImageRotator._rotate_arbitrary_angle(pixbuf, angle)
    
    @staticmethod
    def _rotate_arbitrary_angle(pixbuf: GdkPixbuf.Pixbuf, angle: int) -> GdkPixbuf.Pixbuf:
        """
        Rotate pixbuf by arbitrary angle using Cairo
        This is more complex but handles any angle
        """
        import cairo
        
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        
        # Calculate new dimensions after rotation
        angle_rad = math.radians(angle)
        cos_a = abs(math.cos(angle_rad))
        sin_a = abs(math.sin(angle_rad))
        
        new_width = int(width * cos_a + height * sin_a)
        new_height = int(width * sin_a + height * cos_a)
        
        # Create new surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, new_width, new_height)
        ctx = cairo.Context(surface)
        
        # Set background to white
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()
        
        # Transform and draw the image
        ctx.translate(new_width / 2, new_height / 2)
        ctx.rotate(angle_rad)
        ctx.translate(-width / 2, -height / 2)
        
        # Convert pixbuf to surface and draw
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
        ctx.paint()
        
        # Convert back to pixbuf
        buf = surface.get_data()
        new_pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            buf, GdkPixbuf.Colorspace.RGB, True, 8,
            new_width, new_height, new_width * 4
        )
        
        return new_pixbuf.copy()
    
    @staticmethod
    def rotate_bounding_boxes(boxes: List[BoundingBox], angle: int, 
                            orig_width: int, orig_height: int) -> List[BoundingBox]:
        """
        Rotate bounding boxes to match rotated image
        
        Args:
            boxes: List of bounding boxes
            angle: Rotation angle in degrees
            orig_width: Original image width before ANY rotation
            orig_height: Original image height before ANY rotation
            
        Returns:
            List of rotated bounding boxes
        """
        if not boxes or angle % 360 == 0:
            return [BoundingBox(box.x, box.y, box.width, box.height, box.class_id, box.ocr_text) 
                   for box in boxes]
        
        angle = angle % 360
        rotated_boxes = []
        
        for box in boxes:
            if angle == 90:
                # 90° clockwise: (x,y) -> (y, orig_width-x-width)
                # New image dimensions: orig_height x orig_width
                new_x = box.y
                new_y = orig_width - box.x - box.width
                new_width = box.height
                new_height = box.width
            elif angle == 180:
                # 180°: (x,y) -> (orig_width-x-width, orig_height-y-height)
                # New image dimensions: orig_width x orig_height (same)
                new_x = orig_width - box.x - box.width
                new_y = orig_height - box.y - box.height
                new_width = box.width
                new_height = box.height
            elif angle == 270:
                # 270° clockwise (90° counter-clockwise): (x,y) -> (orig_height-y-height, x)
                # New image dimensions: orig_height x orig_width
                new_x = orig_height - box.y - box.height
                new_y = box.x
                new_width = box.height
                new_height = box.width
            else:
                # For arbitrary angles, use transformation matrix
                new_x, new_y, new_width, new_height = ImageRotator._transform_box_arbitrary(
                    box, angle, orig_width, orig_height
                )
            
            rotated_box = BoundingBox(
                int(new_x), int(new_y), int(new_width), int(new_height),
                box.class_id, box.ocr_text
            )
            rotated_boxes.append(rotated_box)
        
        return rotated_boxes
    
    @staticmethod
    def _transform_box_arbitrary(box: BoundingBox, angle: int, 
                               orig_width: int, orig_height: int) -> Tuple[float, float, float, float]:
        """Transform bounding box for arbitrary rotation angle"""
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Get box corners
        corners = [
            (box.x, box.y),
            (box.x + box.width, box.y),
            (box.x + box.width, box.y + box.height),
            (box.x, box.y + box.height)
        ]
        
        # Transform corners around image center
        center_x, center_y = orig_width / 2, orig_height / 2
        transformed_corners = []
        
        for x, y in corners:
            # Translate to origin
            tx = x - center_x
            ty = y - center_y
            
            # Rotate
            rx = tx * cos_a - ty * sin_a
            ry = tx * sin_a + ty * cos_a
            
            # Translate back
            transformed_corners.append((rx + center_x, ry + center_y))
        
        # Find bounding box of transformed corners
        xs = [corner[0] for corner in transformed_corners]
        ys = [corner[1] for corner in transformed_corners]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return min_x, min_y, max_x - min_x, max_y - min_y


class ImageSaver:
    """Handles saving rotated images"""
    
    @staticmethod
    def save_rotated_image(original_path: str, pixbuf: GdkPixbuf.Pixbuf, 
                          suffix: str = "_rotated") -> Optional[str]:
        """
        Save rotated image to disk
        
        Args:
            original_path: Path to original image
            pixbuf: Rotated pixbuf to save
            suffix: Suffix to add to filename
            
        Returns:
            Path to saved file or None if failed
        """
        try:
            original_path = Path(original_path)
            
            # Create new filename
            new_filename = f"{original_path.stem}{suffix}{original_path.suffix}"
            save_path = original_path.parent / new_filename
            
            # Determine format from extension
            extension = original_path.suffix.lower()
            if extension in ['.jpg', '.jpeg']:
                format_type = 'jpeg'
                options = {'quality': '95'}
            elif extension == '.png':
                format_type = 'png'
                options = {}
            elif extension == '.bmp':
                format_type = 'bmp'
                options = {}
            else:
                # Default to PNG for unknown formats
                format_type = 'png'
                save_path = save_path.with_suffix('.png')
                options = {}
            
            # Save the image
            pixbuf.savev(str(save_path), format_type, 
                        list(options.keys()), list(options.values()))
            
            return str(save_path)
            
        except Exception as e:
            print(f"Error saving rotated image: {e}")
            return None
    
    @staticmethod
    def overwrite_original(original_path: str, pixbuf: GdkPixbuf.Pixbuf) -> bool:
        """
        Overwrite the original image with rotated version
        
        Args:
            original_path: Path to original image
            pixbuf: Rotated pixbuf to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save rotated image over original (no backup)
            original_path = Path(original_path)
            extension = original_path.suffix.lower()
            
            if extension in ['.jpg', '.jpeg']:
                format_type = 'jpeg'
                options = {'quality': '95'}
            elif extension == '.png':
                format_type = 'png'
                options = {}
            elif extension == '.bmp':
                format_type = 'bmp'
                options = {}
            else:
                format_type = 'png'
                options = {}
            
            pixbuf.savev(str(original_path), format_type,
                        list(options.keys()), list(options.values()))
            
            return True
            
        except Exception as e:
            print(f"Error overwriting original image: {e}")
            return False
    
    @staticmethod
    def create_backup(original_path: str, suffix: str = "_backup") -> Optional[str]:
        """
        Create a backup of the original image
        
        Args:
            original_path: Path to original image
            suffix: Suffix for backup filename
            
        Returns:
            Path to backup file or None if failed
        """
        try:
            import shutil
            
            original_path = Path(original_path)
            backup_filename = f"{original_path.stem}{suffix}{original_path.suffix}"
            backup_path = original_path.parent / backup_filename
            
            # Copy original to backup
            shutil.copy2(original_path, backup_path)
            
            return str(backup_path)
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None


class RotationManager:
    """Manages image rotation state and operations"""
    
    def __init__(self):
        self.current_rotation = 0  # Current rotation angle
        self.original_pixbuf = None  # Original unrotated pixbuf
        self.rotated_pixbuf = None  # Current rotated pixbuf
        self.image_path = None
        self.has_unsaved_rotation = False
        self.on_rotation_changed = None  # Callback for rotation changes
    
    def load_image(self, file_path: str) -> bool:
        """Load new image and reset rotation state"""
        try:
            self.original_pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
            self.rotated_pixbuf = self.original_pixbuf.copy()
            self.current_rotation = 0
            self.image_path = file_path
            self.has_unsaved_rotation = False
            return True
        except Exception as e:
            print(f"Error loading image for rotation: {e}")
            return False
    
    def rotate(self, angle: int) -> bool:
        """
        Rotate image by specified angle
        
        Args:
            angle: Angle to rotate (typically 90, -90, 180)
            
        Returns:
            True if successful
        """
        if not self.original_pixbuf:
            return False
        
        self.current_rotation = (self.current_rotation + angle) % 360
        
        # Apply total rotation to original image
        self.rotated_pixbuf = ImageRotator.rotate_pixbuf(
            self.original_pixbuf, self.current_rotation
        )
        
        # Update rotation state
        self.has_unsaved_rotation = (self.current_rotation != 0)
        
        # Notify callback
        if self.on_rotation_changed:
            self.on_rotation_changed(self.current_rotation, self.has_unsaved_rotation)
        
        return True
    
    def rotate_bounding_boxes(self, boxes: List[BoundingBox]) -> List[BoundingBox]:
        """Rotate bounding boxes to match current image rotation"""
        if not self.original_pixbuf or self.current_rotation == 0:
            return boxes
        
        return ImageRotator.rotate_bounding_boxes(
            boxes, self.current_rotation,
            self.original_pixbuf.get_width(),
            self.original_pixbuf.get_height()
        )
    
    def get_current_pixbuf(self) -> Optional[GdkPixbuf.Pixbuf]:
        """Get current rotated pixbuf"""
        return self.rotated_pixbuf
    
    def get_current_rotation(self) -> int:
        """Get current rotation angle"""
        return self.current_rotation
    
    def reset_rotation(self):
        """Reset to original orientation"""
        if self.original_pixbuf:
            self.rotated_pixbuf = self.original_pixbuf.copy()
            self.current_rotation = 0
            self.has_unsaved_rotation = False
            
            if self.on_rotation_changed:
                self.on_rotation_changed(self.current_rotation, self.has_unsaved_rotation)
    
    def save_rotated_image(self, overwrite: bool = False) -> Optional[str]:
        """
        Save the current rotated image
        
        Args:
            overwrite: If True, overwrite original. If False, save with suffix.
            
        Returns:
            Path to saved file or None if failed
        """
        if not self.rotated_pixbuf or not self.image_path:
            return None
        
        if self.current_rotation == 0:
            return self.image_path  # No rotation to save
        
        if overwrite:
            success = ImageSaver.overwrite_original(self.image_path, self.rotated_pixbuf)
            if success:
                # Update state - now the "original" is the rotated version
                self.original_pixbuf = self.rotated_pixbuf.copy()
                self.current_rotation = 0
                self.has_unsaved_rotation = False
                
                if self.on_rotation_changed:
                    self.on_rotation_changed(self.current_rotation, self.has_unsaved_rotation)
                
                return self.image_path
            return None
        else:
            saved_path = ImageSaver.save_rotated_image(self.image_path, self.rotated_pixbuf)
            return saved_path