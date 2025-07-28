#!/usr/bin/env python3

from typing import Tuple, List, Optional, Dict, Any
from ..core.data_types import BoundingBox


class CanvasState:
    """Manages canvas state including zoom, pan, and scale operations"""
    
    def __init__(self):
        self.scale_factor = 1.0
        self.base_scale_factor = 1.0  # For fit-to-window
        self.zoom_level = 1.0  # User zoom multiplier
        self.offset_x = 0
        self.offset_y = 0
        self.canvas_width = 0
        self.canvas_height = 0
        self.image_width = 0
        self.image_height = 0
        
        # Interaction state
        self.dragging = False
        self.resizing = False
        self.panning = False
        self.creating_box = False
        
        # Mouse state
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Box manipulation state
        self.resize_handle = None
        self.box_start_x = 0
        self.box_start_y = 0
        self.box_start_width = 0
        self.box_start_height = 0
        
        # Callbacks
        self.on_state_changed = None
    
    def set_canvas_size(self, width: int, height: int):
        """Set canvas dimensions"""
        self.canvas_width = width
        self.canvas_height = height
        self._notify_state_changed()
    
    def set_image_size(self, width: int, height: int):
        """Set image dimensions"""
        self.image_width = width
        self.image_height = height
        self._notify_state_changed()
    
    def fit_image_to_canvas(self):
        """Calculate scale factor to fit image to canvas"""
        if self.canvas_width <= 0 or self.canvas_height <= 0:
            return
        
        if self.image_width <= 0 or self.image_height <= 0:
            return
        
        scale_x = self.canvas_width / self.image_width
        scale_y = self.canvas_height / self.image_height
        self.base_scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up
        
        self.scale_factor = self.base_scale_factor * self.zoom_level
        
        # Center the image
        scaled_width = self.image_width * self.scale_factor
        scaled_height = self.image_height * self.scale_factor
        self.offset_x = (self.canvas_width - scaled_width) / 2
        self.offset_y = (self.canvas_height - scaled_height) / 2
        
        self._notify_state_changed()
    
    def zoom_in(self, factor: float = 1.25):
        """Zoom in by factor"""
        self.zoom_level = min(self.zoom_level * factor, 5.0)  # Max 5x zoom
        self._update_scale()
    
    def zoom_out(self, factor: float = 1.25):
        """Zoom out by factor"""
        self.zoom_level = max(self.zoom_level / factor, 0.1)  # Min 0.1x zoom
        self._update_scale()
    
    def reset_zoom(self):
        """Reset zoom to fit image"""
        self.zoom_level = 1.0
        self._update_scale()
    
    def _update_scale(self):
        """Update scale factor after zoom change"""
        old_scale = self.scale_factor
        self.scale_factor = self.base_scale_factor * self.zoom_level
        
        # Adjust offsets to maintain center point
        if old_scale > 0:
            scale_ratio = self.scale_factor / old_scale
            center_x = self.canvas_width / 2
            center_y = self.canvas_height / 2
            
            self.offset_x = center_x - (center_x - self.offset_x) * scale_ratio
            self.offset_y = center_y - (center_y - self.offset_y) * scale_ratio
        else:
            self.fit_image_to_canvas()
        
        self._notify_state_changed()
    
    def image_to_canvas(self, x: int, y: int) -> Tuple[int, int]:
        """Convert image coordinates to canvas coordinates"""
        canvas_x = x * self.scale_factor + self.offset_x
        canvas_y = y * self.scale_factor + self.offset_y
        return int(canvas_x), int(canvas_y)
    
    def canvas_to_image(self, x: int, y: int) -> Tuple[int, int]:
        """Convert canvas coordinates to image coordinates"""
        img_x = (x - self.offset_x) / self.scale_factor
        img_y = (y - self.offset_y) / self.scale_factor
        return int(img_x), int(img_y)
    
    def start_pan(self, x: int, y: int):
        """Start panning operation"""
        self.panning = True
        self.pan_start_x = x
        self.pan_start_y = y
    
    def update_pan(self, x: int, y: int):
        """Update panning"""
        if self.panning:
            dx = x - self.pan_start_x
            dy = y - self.pan_start_y
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start_x = x
            self.pan_start_y = y
            self._notify_state_changed()
    
    def end_pan(self):
        """End panning operation"""
        self.panning = False
    
    def start_drag(self, x: int, y: int):
        """Start dragging operation"""
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y
    
    def start_resize(self, x: int, y: int, handle: str, box: BoundingBox):
        """Start resizing operation"""
        self.resizing = True
        self.resize_handle = handle
        self.drag_start_x = x
        self.drag_start_y = y
        self.box_start_x = box.x
        self.box_start_y = box.y
        self.box_start_width = box.width
        self.box_start_height = box.height
    
    def start_box_creation(self, x: int, y: int):
        """Start box creation"""
        self.creating_box = True
        self.drag_start_x = x
        self.drag_start_y = y
    
    def end_interactions(self):
        """End all interaction states"""
        self.dragging = False
        self.resizing = False
        self.panning = False
        self.creating_box = False
        self.resize_handle = None
    
    def get_zoom_percentage(self) -> int:
        """Get current zoom as percentage"""
        return int(self.zoom_level * 100)
    
    def is_interacting(self) -> bool:
        """Check if any interaction is in progress"""
        return self.dragging or self.resizing or self.panning or self.creating_box
    
    def _notify_state_changed(self):
        """Notify state change callback"""
        if self.on_state_changed:
            self.on_state_changed()


class BoxInteractionManager:
    """Manages box selection and manipulation"""
    
    def __init__(self, canvas_state: CanvasState):
        self.canvas_state = canvas_state
        self.boxes = []
        self.selected_box = None
        self.on_box_selected = None
        self.on_boxes_changed = None
    
    def set_boxes(self, boxes: List[BoundingBox]):
        """Set the list of boxes"""
        self.boxes = boxes
        self.selected_box = None
    
    def find_box_at_point(self, canvas_x: int, canvas_y: int) -> Optional[BoundingBox]:
        """Find box at canvas coordinates"""
        img_x, img_y = self.canvas_state.canvas_to_image(canvas_x, canvas_y)
        
        for box in self.boxes:
            if box.contains_point(img_x, img_y):
                return box
        return None
    
    def find_resize_handle(self, canvas_x: int, canvas_y: int, box: BoundingBox) -> Optional[str]:
        """Find resize handle at canvas coordinates"""
        if not box:
            return None
        
        box_canvas_x, box_canvas_y = self.canvas_state.image_to_canvas(box.x, box.y)
        canvas_width = box.width * self.canvas_state.scale_factor
        canvas_height = box.height * self.canvas_state.scale_factor
        
        # Create temporary box with canvas coordinates for handle detection
        temp_box = BoundingBox(box_canvas_x, box_canvas_y, canvas_width, canvas_height, 0)
        return temp_box.get_resize_handle(canvas_x, canvas_y, 8)
    
    def select_box(self, box: Optional[BoundingBox]):
        """Select a box"""
        if self.selected_box:
            self.selected_box.selected = False
        
        if box:
            box.selected = True
            self.selected_box = box
        else:
            self.selected_box = None
        
        if self.on_box_selected:
            self.on_box_selected(box)
    
    def delete_selected_box(self):
        """Delete the currently selected box"""
        if self.selected_box:
            self.boxes.remove(self.selected_box)
            self.selected_box = None
            self.select_box(None)
            self._notify_boxes_changed()
    
    def create_box(self, start_x: int, start_y: int, end_x: int, end_y: int, class_config: Dict[str, Any]) -> Optional[BoundingBox]:
        """Create a new box from canvas coordinates"""
        start_img_x, start_img_y = self.canvas_state.canvas_to_image(start_x, start_y)
        end_img_x, end_img_y = self.canvas_state.canvas_to_image(end_x, end_y)
        
        # Check minimum size
        if abs(end_img_x - start_img_x) < 10 or abs(end_img_y - start_img_y) < 10:
            return None
        
        box_x = min(start_img_x, end_img_x)
        box_y = min(start_img_y, end_img_y)
        box_width = abs(end_img_x - start_img_x)
        box_height = abs(end_img_y - start_img_y)
        
        # Find appropriate class ID
        available_classes = [cls["id"] for cls in class_config["classes"]]
        used_classes = [b.class_id for b in self.boxes]
        
        class_id = available_classes[0]  # Default to first class
        for cls_id in available_classes:
            if cls_id not in used_classes:
                class_id = cls_id
                break
        
        # Get class name
        class_name = "unknown"
        for cls in class_config["classes"]:
            if cls["id"] == class_id:
                class_name = cls["name"]
                break
        
        new_box = BoundingBox(box_x, box_y, box_width, box_height, class_id, "", class_name)
        self.boxes.append(new_box)
        self.select_box(new_box)
        self._notify_boxes_changed()
        
        return new_box
    
    def update_box_position(self, box: BoundingBox, canvas_dx: int, canvas_dy: int):
        """Update box position from canvas drag"""
        img_dx = canvas_dx / self.canvas_state.scale_factor
        img_dy = canvas_dy / self.canvas_state.scale_factor
        
        box.x = max(0, self.canvas_state.box_start_x + img_dx)
        box.y = max(0, self.canvas_state.box_start_y + img_dy)
        self._notify_boxes_changed()
    
    def update_box_size(self, box: BoundingBox, canvas_dx: int, canvas_dy: int, handle: str):
        """Update box size from canvas resize"""
        img_dx = canvas_dx / self.canvas_state.scale_factor
        img_dy = canvas_dy / self.canvas_state.scale_factor
        
        if handle == "nw":
            box.x = self.canvas_state.box_start_x + img_dx
            box.y = self.canvas_state.box_start_y + img_dy
            box.width = self.canvas_state.box_start_width - img_dx
            box.height = self.canvas_state.box_start_height - img_dy
        elif handle == "ne":
            box.y = self.canvas_state.box_start_y + img_dy
            box.width = self.canvas_state.box_start_width + img_dx
            box.height = self.canvas_state.box_start_height - img_dy
        elif handle == "sw":
            box.x = self.canvas_state.box_start_x + img_dx
            box.width = self.canvas_state.box_start_width - img_dx
            box.height = self.canvas_state.box_start_height + img_dy
        elif handle == "se":
            box.width = self.canvas_state.box_start_width + img_dx
            box.height = self.canvas_state.box_start_height + img_dy
        elif handle == "n":
            box.y = self.canvas_state.box_start_y + img_dy
            box.height = self.canvas_state.box_start_height - img_dy
        elif handle == "s":
            box.height = self.canvas_state.box_start_height + img_dy
        elif handle == "w":
            box.x = self.canvas_state.box_start_x + img_dx
            box.width = self.canvas_state.box_start_width - img_dx
        elif handle == "e":
            box.width = self.canvas_state.box_start_width + img_dx
        
        # Ensure minimum size
        if box.width < 10:
            box.width = 10
        if box.height < 10:
            box.height = 10
        
        self._notify_boxes_changed()
    
    def _notify_boxes_changed(self):
        """Notify boxes changed callback"""
        if self.on_boxes_changed:
            self.on_boxes_changed()
