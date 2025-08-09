#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from pathlib import Path
from typing import Optional, Dict, Any
from ..business.label_logic import LabelManager, OCRProcessor
from ..business.project_state import ProjectManager
from ..core.keymap import KeymapManager


class EventHandlerMixin:
    """Mixin class containing all event handlers for LabelEditorWindow"""
    
    def setup_event_handlers(self):
        """Initialize event handlers"""
        # Initialize keymap manager
        try:
            self.keymap_manager = KeymapManager()
        except Exception as e:
            print(f"Error initializing keymap: {e}")
            print("Please ensure keymap.json exists in the settings directory")
            raise
        
        # Setup global key bindings
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect('key-pressed', self.on_window_key_pressed)
        self.add_controller(self.key_controller)
        
        # Window events
        self.connect('notify::default-width', self.on_size_changed)
        self.connect('notify::default-height', self.on_size_changed)
        self.connect('close-request', self.on_close_request)
    
    # Navigation handlers
    def on_prev_clicked(self, button):
        """Handle previous button click"""
        if hasattr(self, 'project_manager') and self.project_manager.navigate_previous():
            self.auto_save_current()
            self.load_current_image()
            self.update_navigation_buttons()
            # Ensure canvas gets focus for immediate interaction
            if hasattr(self, 'canvas'):
                self.canvas.grab_focus()
    
    def on_next_clicked(self, button):
        """Handle next button click"""
        if hasattr(self, 'project_manager') and self.project_manager.navigate_next():
            self.auto_save_current()
            self.load_current_image()
            self.update_navigation_buttons()
            # Ensure canvas gets focus for immediate interaction
            if hasattr(self, 'canvas'):
                self.canvas.grab_focus()
    
    # Zoom handlers
    def on_zoom_out_clicked(self, button):
        """Handle zoom out button click"""
        if hasattr(self, 'canvas'):
            self.canvas.zoom_out()
            self.update_navigation_buttons()
    
    def on_zoom_in_clicked(self, button):
        """Handle zoom in button click"""
        if hasattr(self, 'canvas'):
            self.canvas.zoom_in()
            self.update_navigation_buttons()
    
    def on_reset_zoom_clicked(self, button):
        """Handle reset zoom button click"""
        if hasattr(self, 'canvas'):
            self.canvas.reset_zoom()
            self.update_navigation_buttons()
    
    # Box selection handlers
    def on_box_selected(self, box):
        """Handle box selection"""
        if box:
            # Remember this class for future auto-selection
            self._last_selected_class_id = box.class_id
            class_info = None
            if hasattr(self, 'project_manager'):
                for cls in self.project_manager.class_config["classes"]:
                    if cls["id"] == box.class_id:
                        class_info = cls
                        break
            
            info_text = f"<b>Selected:</b> {box.name}\n<b>Position:</b> {box.x}, {box.y}\n<b>Size:</b> {box.width} x {box.height}\n<b>Class ID:</b> {box.class_id}"
            
            if class_info and "regex_pattern" in class_info and box.ocr_text:
                import re
                regex_pattern = class_info["regex_pattern"]
                if re.match(regex_pattern, box.ocr_text):
                    info_text += "\n<span color='green'>✓ Valid format</span>"
                else:
                    info_text += "\n<span color='red'>✗ Invalid format</span>"
            
            if hasattr(self, 'selected_info'):
                self.selected_info.set_markup(info_text)
            
            if hasattr(self, 'ocr_text'):
                buffer = self.ocr_text.get_buffer()
                buffer.set_text(box.ocr_text, -1)
            
            if hasattr(self, 'class_combo'):
                class_index = 0
                if hasattr(self, 'project_manager'):
                    for i, cls in enumerate(self.project_manager.class_config["classes"]):
                        if cls["id"] == box.class_id:
                            class_index = i
                            break
                self.class_combo.set_selected(class_index)
            
            self.set_editing_enabled(True)
        else:
            if hasattr(self, 'selected_info'):
                self.selected_info.set_markup("<i>No box selected</i>")
            if hasattr(self, 'ocr_text'):
                self.ocr_text.get_buffer().set_text("", -1)
            self.set_editing_enabled(False)
        
        self.update_all_labels_display()
    
    def on_boxes_changed(self):
        """Handle boxes changed event"""
        self.unsaved_changes = True
        self._editing_in_progress = True
        self.update_title()
        
        # Update file list colors since validation status may have changed
        self.update_file_list_colors()
        # Update directory statistics
        self.update_directory_stats()
        
        if hasattr(self, 'canvas') and self.canvas.selected_box:
            box = self.canvas.selected_box
            if hasattr(self, 'selected_info'):
                self.selected_info.set_markup(
                    f"<b>Selected:</b> {box.name}\n<b>Position:</b> {box.x}, {box.y}\n<b>Size:</b> {box.width} x {box.height}\n<b>Class ID:</b> {box.class_id}\n<b>Confidence:</b> {getattr(box, 'confidence', 'N/A')}")
        
        self.update_all_labels_display()
    
    # File list handlers
    def on_list_setup(self, factory, list_item):
        """Setup list item widget"""
        label = Gtk.Label()
        label.set_halign(Gtk.Align.START)
        list_item.set_child(label)
    
    def on_list_bind(self, factory, list_item):
        """Bind data to list item"""
        label = list_item.get_child()
        string_object = list_item.get_item()
        if string_object:
            filename = string_object.get_string()
            label.set_text(filename)
        else:
            label.set_text("")
            return
        
        # Apply validation status styling
        if hasattr(self, 'file_list_data') and self.file_list_data:
            # Find the file info for this item
            position = list_item.get_position()
            
            # Use filtered list if available, otherwise use full list
            display_files = self._filtered_file_list if hasattr(self, '_filtered_file_list') and self._filtered_file_list is not None else self.file_list_data
            
            if position < len(display_files):
                file_info = display_files[position]
                validation_status = file_info.get('validation_status', 'normal')
                
                # Check if file is confirmed
                file_path = file_info.get('path', '')
                is_confirmed = False
                if hasattr(self, 'confirmation_manager'):
                    is_confirmed = self.confirmation_manager.get_confirmation(file_path)
                
                # Debug: print binding info
                print(f"Binding item {position}: {filename} - validation: {validation_status}, confirmed: {is_confirmed}")
                
                # Remove existing style classes
                label.remove_css_class('file-normal')
                label.remove_css_class('file-saved')
                label.remove_css_class('file-valid')
                label.remove_css_class('file-no-dat')
                label.remove_css_class('file-missing-classes')
                label.remove_css_class('file-invalid-regex')
                label.remove_css_class('file-error')
                label.remove_css_class('file-confirmed')
                
                # Check if file is confirmed
                file_path = file_info.get('path', '')
                is_confirmed = False
                if hasattr(self, 'confirmation_manager'):
                    is_confirmed = self.confirmation_manager.get_confirmation(file_path)
                
                # Apply appropriate style class (confirmed status takes precedence)
                if is_confirmed:
                    label.add_css_class('file-confirmed')
                elif validation_status == 'valid':
                    label.add_css_class('file-valid')
                elif validation_status == 'no_dat':
                    label.add_css_class('file-no-dat')
                elif validation_status == 'missing_classes':
                    label.add_css_class('file-missing-classes')
                elif validation_status == 'invalid_regex':
                    label.add_css_class('file-invalid-regex')
                elif validation_status == 'error':
                    label.add_css_class('file-error')
                else:
                    label.add_css_class('file-normal')
    
    def on_file_selected(self, selection, param=None):
        """Handle file selection in list"""
        if self._updating_selection:
            return
        selected = selection.get_selected()
        if (selected != Gtk.INVALID_LIST_POSITION and 
            hasattr(self, 'project_manager')):
            
            # Use filtered list if available, otherwise use full list
            display_files = self._filtered_file_list if hasattr(self, '_filtered_file_list') and self._filtered_file_list is not None else self.file_list_data
            
            if selected < len(display_files):
                # Get the actual file path from the selected item
                file_info = display_files[selected]
                file_path = file_info.get('path', '')
                
                # Find the index in the original file list
                original_index = -1
                for i, original_file in enumerate(self.project_manager.image_files):
                    if str(original_file) == file_path:
                        original_index = i
                        break
                
                if original_index != -1 and original_index != self.project_manager.current_index:
                    self.auto_save_current()
                    if self.project_manager.navigate_to_image(original_index):
                        self.load_current_image()
                        # Ensure canvas gets focus for immediate interaction
                        if hasattr(self, 'canvas'):
                            self.canvas.grab_focus()
    
    def auto_save_current(self):
        """Auto-save current image data before navigating to another image"""
        if (hasattr(self, 'project_manager') and 
            self.project_manager.current_dat_path and 
            hasattr(self, 'unsaved_changes') and 
            self.unsaved_changes):
            try:
                self.save_dat_file(str(self.project_manager.current_dat_path))
            except Exception as e:
                print(f"Auto-save failed: {e}")
    
    # Menu action handlers
    def on_open_directory(self, action, param):
        """Handle open directory action"""
        dialog = Gtk.FileDialog()
        dialog.select_folder(self, None, self.on_open_directory_response)
    
    def on_open_directory_response(self, dialog, result):
        """Handle open directory dialog response"""
        try:
            folder = dialog.select_folder_finish(result)
            if folder and hasattr(self, 'project_manager'):
                self.project_manager.load_directory(folder.get_path())
                self.load_current_image()
                self.update_navigation_buttons()
        except Exception as e:
            self.show_error(f"Error opening directory: {e}")
    
    def on_open_image(self, action, param):
        """Handle open image action"""
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self.on_open_image_response)
    
    def on_open_image_response(self, dialog, result):
        """Handle open image dialog response"""
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_image(file.get_path())
        except Exception as e:
            self.show_error(f"Error opening image: {e}")
    
    def quick_delete_selected(self):
        """Quick delete selected label with Y key"""
        if hasattr(self, 'label_manager') and self.label_manager.selected_box:
            current_image_path = getattr(self.project_manager, 'current_image_path', None)
            if self.label_manager.delete_selected_box(current_image_path):
                self.on_boxes_changed()
                if hasattr(self, 'canvas'):
                    self.canvas.queue_draw()
    
    def restore_deleted_label(self):
        """Restore last deleted label with U key"""
        if hasattr(self, 'label_manager'):
            current_image_path = getattr(self.project_manager, 'current_image_path', None)
            if self.label_manager.restore_deleted_label(current_image_path):
                self.on_boxes_changed()
                if hasattr(self, 'canvas'):
                    self.canvas.queue_draw()
    
    def on_save(self, action, param):
        """Handle save action"""
        if hasattr(self, 'project_manager') and self.project_manager.current_dat_path:
            # Check if image has been rotated
            if hasattr(self, 'canvas') and self.canvas.has_unsaved_rotation():
                self._save_with_rotation()
            else:
                self.save_dat_file(str(self.project_manager.current_dat_path))
    
    def _save_with_rotation(self):
        """Save both rotated image and adjusted labels"""
        # Show save options for rotated content
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Save Rotated Content"
        )
        dialog.set_property("secondary-text",
            "This image has been rotated. How would you like to save?\n\n"
            "• Save Both: Overwrite original image file with rotated version and save current label positions\n"
            "• Labels Only: Keep original image, save rotated label coordinates"
        )
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Labels Only", Gtk.ResponseType.NO)
        dialog.add_button("Save Both", Gtk.ResponseType.YES)
        dialog.set_default_response(Gtk.ResponseType.YES)
        
        # GTK4 compatible dialog handling
        def on_dialog_response(dialog, response_id):
            dialog.destroy()
            if response_id == Gtk.ResponseType.YES:
                # Save rotated image and current label positions
                self._save_rotated_image_and_current_labels()
            elif response_id == Gtk.ResponseType.NO:
                # Save only labels with rotated coordinates 
                self.save_dat_file(str(self.project_manager.current_dat_path))
        
        dialog.connect('response', on_dialog_response)
        dialog.present()
    
    def _save_rotated_image_and_current_labels(self):
        """Save rotated image file and current label positions as they appear"""
        try:
            # Save rotated image (overwrite original with backup)
            saved_image_path = self.canvas.save_rotated_image(overwrite=True)
            if saved_image_path:
                # Get current boxes as they appear on screen
                current_boxes = self.canvas.boxes
                
                # Save current box positions - these are perfect for the rotated image
                if current_boxes is not None:
                    self.label_manager.boxes = current_boxes
                    self.save_dat_file(str(self.project_manager.current_dat_path))
                    
                    # Reset rotation state since image is now saved rotated
                    self.canvas.rotation_manager.current_rotation = 0
                    self.canvas.rotation_manager.has_unsaved_rotation = False
                    
                    # Clear rotation cache
                    if hasattr(self.canvas, '_original_boxes'):
                        delattr(self.canvas, '_original_boxes')
                    
                    # Reload the now-rotated image to reset everything
                    self.canvas.load_image(self.project_manager.current_image_path)
                    self.canvas.boxes = current_boxes
                    
                    self.update_status("Original image overwritten with rotated version and labels saved")
                    self.unsaved_changes = False
                    self.update_title()
                else:
                    self.show_error("Failed to retrieve original label coordinates")
            else:
                self.show_error("Failed to save rotated image")
        except Exception as e:
            self.show_error(f"Error saving rotated content: {e}")
    
    
    # Text editing handlers
    def on_ocr_text_changed(self, buffer):
        """Handle OCR text change"""
        if hasattr(self, 'canvas') and self.canvas.selected_box:
            start = buffer.get_start_iter()
            end = buffer.get_end_iter()
            text = buffer.get_text(start, end, False)
            self.canvas.selected_box.ocr_text = text
            self.on_boxes_changed()
            
            # Trigger delayed auto-save
            if hasattr(self, '_auto_save_timeout') and self._auto_save_timeout:
                GLib.source_remove(self._auto_save_timeout)
            self._auto_save_timeout = GLib.timeout_add(2000, self._delayed_auto_save)
    
    def on_text_focus_in(self, controller):
        """Handle text focus in"""
        self._text_editing_active = True
    
    def on_text_focus_out(self, controller):
        """Handle text focus out"""
        self._text_editing_active = False
    
    def on_class_changed(self, combo, param=None):
        """Handle class combo change"""
        if hasattr(self, 'canvas') and self.canvas.selected_box and hasattr(self, 'project_manager'):
            selected_idx = combo.get_selected()
            if selected_idx < len(self.project_manager.class_config["classes"]):
                new_class = self.project_manager.class_config["classes"][selected_idx]
                self.canvas.selected_box.class_id = new_class["id"]
                self.canvas.selected_box.name = new_class["name"]
                self.on_boxes_changed()
                self.canvas.queue_draw()
    
    # Button handlers
    def on_delete_clicked(self, button):
        """Handle delete button click"""
        if hasattr(self, 'canvas') and self.canvas.selected_box:
            self.canvas.boxes.remove(self.canvas.selected_box)
            self.canvas.selected_box = None
            self.on_box_selected(None)
            self.on_boxes_changed()
            self.canvas.queue_draw()
    
    def on_ocr_clicked(self, button):
        """Handle OCR button click"""
        print("[OCR] on_ocr_clicked called")
        
        if (not hasattr(self, 'canvas') or not self.canvas.selected_box or 
            not hasattr(self, 'project_manager') or not self.project_manager.current_image_path):
            print("[OCR] Validation failed - missing canvas, selected_box, or current_image_path")
            self.show_error("Please select a label first")
            return
        
        print(f"[OCR] Selected box: {self.canvas.selected_box}")
        print(f"[OCR] Current image: {self.project_manager.current_image_path}")
        
        button.set_label("⏳ Processing...")
        button.set_sensitive(False)
        
        # Setup OCR processor
        if not hasattr(self, 'ocr_processor'):
            print("[OCR] Creating new OCRProcessor")
            self.ocr_processor = OCRProcessor(self.project_manager.class_config)
            self.ocr_processor.on_ocr_complete = lambda text, current: self._ocr_complete(button, text)
            self.ocr_processor.on_ocr_error = lambda error: self._ocr_error(button, error)
        else:
            print("[OCR] Using existing OCRProcessor")
        
        # Get selected OCR engine from dropdown
        ocr_engine = "tesseract"  # Default
        if hasattr(self, 'ocr_model_combo'):
            ocr_engine = self.ocr_model_combo.get_active_id()
            print(f"[OCR] Selected OCR engine: {ocr_engine}")
        
        print("[OCR] Starting OCR processing...")
        self.ocr_processor.process_ocr(
            self.project_manager.current_image_path, 
            self.canvas.selected_box,
            ocr_engine
        )
        print("[OCR] OCR processing started")
    
    def on_confirm_toggled(self, checkbox):
        """Handle confirmation checkbox toggle"""
        if hasattr(self, 'project_manager') and self.project_manager.current_image_path:
            is_confirmed = checkbox.get_active()
            
            # Update confirmation status
            if hasattr(self, 'confirmation_manager'):
                self.confirmation_manager.set_confirmation(
                    self.project_manager.current_image_path, is_confirmed)
            
            # Update file list colors to reflect confirmation change
            self.update_file_list_colors()
            
            # Only advance to next image when confirming (not when unconfirming)
            if is_confirmed and self.project_manager.get_navigation_state()['can_go_next']:
                # Go to next image
                self.on_next_clicked(None)
            # When unconfirming, stay on current image (no navigation)
    
    # Keyboard handlers
    def on_window_key_pressed(self, controller, keyval, keycode, state):
        """Handle global key press events using keymap configuration"""
        focused_widget = self.get_focus()
        
        is_text_editing = (focused_widget and
                          (isinstance(focused_widget, Gtk.Text) or
                           isinstance(focused_widget, Gtk.Entry) or
                           isinstance(focused_widget, Gtk.TextView)))
        
        # Get action from keymap
        action = self.keymap_manager.get_action_for_key(keyval, state)
        
        # Handle escape key specially
        if keyval == Gdk.KEY_Escape:
            if is_text_editing:
                self.set_focus(None)
                if hasattr(self, 'canvas'):
                    self.canvas.grab_focus()
                return True
            else:
                return False
        
        # Allow certain shortcuts even while text editing
        if is_text_editing:
            ctrl_pressed = (state & Gdk.ModifierType.CONTROL_MASK) != 0
            if ctrl_pressed and keyval in [Gdk.KEY_s, Gdk.KEY_o]:
                pass  # Will be handled below
            else:
                return False
        
        # Handle actions from keymap
        if action:
            if action == "navigation.previous_image":
                if hasattr(self, 'prev_button') and self.prev_button.get_sensitive():
                    self.on_prev_clicked(None)
                return True
            elif action == "navigation.next_image":
                if hasattr(self, 'next_button') and self.next_button.get_sensitive():
                    self.on_next_clicked(None)
                return True
            elif action == "system.save":
                self.on_save(None, None)
                return True
            elif action == "system.open_directory":
                self.on_open_directory(None, None)
                return True
            elif action == "system.next_image_ctrl":
                if hasattr(self, 'next_button') and self.next_button.get_sensitive():
                    self.on_next_clicked(None)
                return True
            elif action == "system.previous_image_ctrl":
                if hasattr(self, 'prev_button') and self.prev_button.get_sensitive():
                    self.on_prev_clicked(None)
                return True
            elif action == "system.show_help":
                self.show_help_dialog()
                return True
            elif action == "system.reset_zoom":
                if hasattr(self, 'canvas'):
                    self.canvas.reset_zoom()
                    self.update_navigation_buttons()
                return True
            elif action == "system.zoom_in":
                if hasattr(self, 'canvas'):
                    self.canvas.zoom_in()
                    self.update_navigation_buttons()
                return True
            elif action == "system.zoom_out":
                if hasattr(self, 'canvas'):
                    self.canvas.zoom_out()
                    self.update_navigation_buttons()
                return True
            elif action == "editing.toggle_confirmation":
                self.toggle_confirmation()
                return True
            elif action == "editing.focus_ocr_textbox":
                self.focus_ocr_textbox()
                return True
            elif action == "editing.run_ocr":
                print("[OCR] run_ocr action triggered from keyboard")
                if hasattr(self, 'ocr_button'):
                    print("[OCR] Calling on_ocr_clicked")
                    self.on_ocr_clicked(self.ocr_button)
                else:
                    print("[OCR] No ocr_button found")
                return True
            elif action == "editing.quick_delete":
                self.quick_delete_selected()
                return True
            elif action == "editing.restore_deleted":
                self.restore_deleted_label()
                return True
            elif action.startswith("label_selection.focus_label_"):
                # Extract label number from action
                label_num = action.split("_")[-1]
                try:
                    if label_num == "10":  # Special case for 0 key -> label 10
                        label_index = 9  # 0-based index for 10th label
                    else:
                        label_index = int(label_num) - 1  # Convert to 0-based index
                    self.focus_label_by_index(label_index)
                    return True
                except ValueError:
                    pass
            elif action.startswith("label_adjustment."):
                # Handle label adjustment actions
                if hasattr(self, 'canvas') and self.canvas.selected_box:
                    self.handle_label_adjustment(action, state)
                    return True
        
        return False
    
    def focus_label_by_index(self, label_index: int):
        """Focus on a specific label by index (0-based)"""
        if not hasattr(self, 'canvas') or not self.canvas.boxes:
            return
        
        if 0 <= label_index < len(self.canvas.boxes):
            # Sort boxes by class_id to match visual order
            sorted_boxes = sorted(self.canvas.boxes, key=lambda b: b.class_id)
            
            if label_index < len(sorted_boxes):
                target_box = sorted_boxes[label_index]
                
                # Deselect current box
                if self.canvas.selected_box:
                    self.canvas.selected_box.selected = False
                
                # Select target box
                target_box.selected = True
                self.canvas.selected_box = target_box
                
                # Update UI
                self.on_box_selected(target_box)
                self.canvas.queue_draw()
                
                # Ensure canvas has focus
                self.canvas.grab_focus()
    
    def focus_ocr_textbox(self):
        """Focus on the OCR text box for editing"""
        if hasattr(self, 'ocr_text') and hasattr(self, 'canvas') and self.canvas.selected_box:
            self.ocr_text.grab_focus()
    
    def handle_label_adjustment(self, action: str, state):
        """Handle label position and size adjustment"""
        if not hasattr(self, 'canvas') or not self.canvas.selected_box:
            return
        
        box = self.canvas.selected_box
        
        # Check if Shift is pressed for fine adjustment
        shift_pressed = (state & Gdk.ModifierType.SHIFT_MASK) != 0
        
        adjustment_step = 1 if shift_pressed else 5  # pixels for movement
        resize_step = 1 if shift_pressed else 5      # pixels for resizing
        
        if action == "label_adjustment.move_up":
            box.y = max(0, box.y - adjustment_step)
        elif action == "label_adjustment.move_down":
            box.y += adjustment_step
        elif action == "label_adjustment.move_left":
            box.x = max(0, box.x - adjustment_step)
        elif action == "label_adjustment.move_right":
            box.x += adjustment_step
        elif action == "label_adjustment.resize_width_decrease":
            box.width = max(10, box.width - resize_step)
        elif action == "label_adjustment.resize_width_increase":
            box.width += resize_step
        elif action == "label_adjustment.resize_height_decrease":
            box.height = max(10, box.height - resize_step)
        elif action == "label_adjustment.resize_height_increase":
            box.height += resize_step
        
        # Update UI
        self.on_boxes_changed()
        self.canvas.queue_draw()
    
    # Window event handlers
    def on_size_changed(self, window, param):
        """Handle window size change"""
        if hasattr(self, 'project_manager'):
            self.project_manager.save_config({
                'window_width': int(self.get_width()),
                'window_height': int(self.get_height())
            })
    
    def on_close_request(self, window):
        """Handle window close request"""
        self.auto_save_current()
        if hasattr(self, 'project_manager'):
            self.project_manager.save_config()
        return False
    
    # Helper methods for OCR
    def _ocr_complete(self, button, extracted_text):
        """Handle OCR completion"""
        print(f"[OCR] _ocr_complete called with text: '{extracted_text}'")
        
        def update_ui():
            print("[OCR] Updating UI in main thread")
            try:
                button.set_label("🔍 Run OCR")
                button.set_sensitive(True)
                
                if not extracted_text.strip():
                    print("[OCR] No text extracted, showing info dialog")
                    self.show_info("No text detected in the selected region")
                    return False
                
                current_text = ""
                if hasattr(self, 'canvas') and self.canvas.selected_box:
                    current_text = self.canvas.selected_box.ocr_text or ""
                
                print(f"[OCR] Creating dialog, current_text: '{current_text}'")
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text="OCR Text Extracted"
                )
                
                dialog_text = f"""Extracted text: {extracted_text}

Current text: {current_text}

Replace current text with extracted text?"""
                dialog.set_property("secondary-text", dialog_text)
                
                def on_response(d, response):
                    print(f"[OCR] Dialog response: {response}")
                    if response == Gtk.ResponseType.YES and hasattr(self, 'ocr_text'):
                        buffer = self.ocr_text.get_buffer()
                        buffer.set_text(extracted_text, -1)
                        print("[OCR] Text updated in buffer")
                    d.destroy()
                
                dialog.connect('response', on_response)
                dialog.present()
                print("[OCR] Dialog presented")
                return False  # Don't repeat this idle callback
            except Exception as e:
                print(f"[OCR] Error in UI update: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Use GLib.idle_add to marshal to main thread
        GLib.idle_add(update_ui)
    
    def _ocr_error(self, button, error_message):
        """Handle OCR error"""
        print(f"[OCR] _ocr_error called with message: '{error_message}'")
        
        def update_ui():
            print("[OCR] Updating UI after error in main thread")
            try:
                button.set_label("🔍 Run OCR")
                button.set_sensitive(True)
                self.show_error(error_message)
                print("[OCR] Error dialog shown")
                return False  # Don't repeat this idle callback
            except Exception as e:
                print(f"[OCR] Error in error UI update: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Use GLib.idle_add to marshal to main thread
        GLib.idle_add(update_ui)
    
    def on_profile_manager(self, action, param):
        """Handle profile manager action"""
        from .profile_selector_gtk4 import show_profile_selector
        
        selected_profile = show_profile_selector(self, self.project_manager.settings_manager)
        if selected_profile:
            # Profile was changed, update the UI
            self._handle_profile_change(selected_profile)
    
    def _handle_profile_change(self, profile_name):
        """Handle profile change and update UI accordingly"""
        try:
            # Update project manager configuration
            self.project_manager.config = self.project_manager._get_config_from_settings()
            
            # Update class configuration and label manager
            self.project_manager.class_config = self.project_manager._parse_class_config()
            self.label_manager = LabelManager(self.project_manager.class_config)
            
            # Update validation engine with new classes
            if hasattr(self.project_manager, 'validation_engine'):
                self.project_manager.validation_engine = ValidationEngine(self.project_manager.class_config)
            
            # Update window title to show active profile
            profile_display = profile_name if profile_name != "Base Settings" else "Default"
            self.set_title(f"MRZ Label Editor - {profile_display}")
            
            # Refresh UI components with new profile data
            GLib.idle_add(self._refresh_profile_ui)
            
            # Update default directory if specified and load new directory
            new_directory = self.project_manager.settings_manager.get('default_directory')
            if new_directory and Path(new_directory).exists():
                self.project_manager.current_directory = Path(new_directory)
                # Load directory and refresh file list
                GLib.idle_add(self._load_directory_and_refresh, new_directory)
            else:
                # If no directory specified, clear current state
                GLib.idle_add(self._clear_directory_state)
            
            # Save current profile for next session
            state_file = self.project_manager.settings_manager.base_dir / "last_profile.txt"
            try:
                with open(state_file, 'w') as f:
                    f.write(profile_name)
            except Exception:
                pass
            
            self.update_status(f"Switched to profile: {profile_display}")
            
        except Exception as e:
            self.show_error(f"Error switching profiles: {e}")
    
    def _load_directory_and_refresh(self, directory_path):
        """Load directory and refresh all related UI components"""
        try:
            # Load the directory through project manager
            if hasattr(self.project_manager, 'load_directory'):
                self.project_manager.load_directory(directory_path)
            else:
                # Fallback: manual directory loading
                self.project_manager.current_directory = Path(directory_path)
                self._manual_directory_load(directory_path)
            
            # Refresh file list and navigation
            self.update_file_list()
            self.update_navigation_buttons()
            
            # Load first image if available
            if (hasattr(self.project_manager, 'image_files') and 
                self.project_manager.image_files and 
                len(self.project_manager.image_files) > 0):
                self.project_manager.current_index = 0
                self.load_current_image()
            else:
                # Clear canvas if no images
                if hasattr(self, 'canvas'):
                    self.canvas.clear_image()
                    self.canvas.queue_draw()
            
        except Exception as e:
            self.update_status(f"Error loading directory: {e}")
    
    def _manual_directory_load(self, directory_path):
        """Manual directory loading when project manager method isn't available"""
        directory = Path(directory_path)
        if directory.exists() and directory.is_dir():
            # Get image files
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
            image_files = []
            
            for ext in image_extensions:
                image_files.extend(directory.glob(f"*{ext}"))
                image_files.extend(directory.glob(f"*{ext.upper()}"))
            
            # Sort files
            image_files.sort()
            
            # Update project manager state
            self.project_manager.image_files = [str(f) for f in image_files]
            self.project_manager.current_index = -1
            self.project_manager.current_image_path = None
    
    def _clear_directory_state(self):
        """Clear directory-related state when no directory is specified"""
        self.project_manager.image_files = []
        self.project_manager.current_index = -1
        self.project_manager.current_image_path = None
        
        # Clear UI elements
        if hasattr(self, 'canvas'):
            self.canvas.clear_image()
            self.canvas.queue_draw()
        
        if hasattr(self, 'file_list'):
            self.file_list.remove_all()
        
        self.update_navigation_buttons()
        self.update_status("No directory loaded")
    
    def _refresh_file_list(self):
        """Refresh the file list display"""
        if not hasattr(self, 'file_list'):
            return
        
        # Clear existing items
        self.file_list.remove_all()
        
        # Add new items
        if hasattr(self.project_manager, 'image_files'):
            for image_file in self.project_manager.image_files:
                filename = Path(image_file).name
                self.file_list.append(filename)
        
        # Update directory statistics
        self._update_directory_stats()
    
    # Dialog helpers
    def show_help_dialog(self):
        """Show help dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Keyboard Shortcuts"
        )
        
        # Set dialog size
        dialog.set_default_size(600, 500)
        
        # Build help text from actual keymap
        help_sections = []
        
        # Navigation section
        nav_keys = []
        if hasattr(self, 'keymap_manager'):
            prev_keys = self.keymap_manager.get_keys_for_action('navigation.previous_image')
            next_keys = self.keymap_manager.get_keys_for_action('navigation.next_image')
            if prev_keys and next_keys:
                nav_keys.append(f"• {'/'.join(prev_keys)} - Previous image")
                nav_keys.append(f"• {'/'.join(next_keys)} - Next image")
        
        if nav_keys:
            help_sections.append("Navigation:\n" + "\n".join(nav_keys))
        
        # Label Selection section
        label_keys = []
        if hasattr(self, 'keymap_manager'):
            for i in range(1, 11):
                action = f'label_selection.focus_label_{i}'
                keys = self.keymap_manager.get_keys_for_action(action)
                if keys:
                    label_num = "10" if i == 10 else str(i)
                    label_keys.append(f"• {'/'.join(keys)} - Focus on label {label_num}")
        
        if label_keys:
            help_sections.append("\nLabel Selection:\n" + "\n".join(label_keys))
        
        # Editing section
        edit_keys = []
        if hasattr(self, 'keymap_manager'):
            edit_actions = [
                ('editing.select_next_label', 'Select next label'),
                ('editing.focus_ocr_textbox', 'Focus OCR text box'),
                ('editing.run_ocr', 'Run OCR on selected label'),
                ('editing.delete_selected', 'Delete selected label'),
                ('editing.quick_delete', 'Quick delete (no confirmation)'),
                ('editing.restore_deleted', 'Restore last deleted label'),
                ('editing.toggle_confirmation', 'Toggle confirmation status'),
                ('editing.exit_editing', 'Exit text editing / Deselect all')
            ]
            
            for action, description in edit_actions:
                keys = self.keymap_manager.get_keys_for_action(action)
                if keys:
                    edit_keys.append(f"• {'/'.join(keys)} - {description}")
        
        if edit_keys:
            help_sections.append("\nLabel Editing:\n" + "\n".join(edit_keys))
        
        # Label Adjustment section
        adjust_keys = []
        if hasattr(self, 'keymap_manager'):
            adjust_actions = [
                ('label_adjustment.move_up', 'Move label up (5px, or 1px with Shift)'),
                ('label_adjustment.move_down', 'Move label down (5px, or 1px with Shift)'),
                ('label_adjustment.move_left', 'Move label left (5px, or 1px with Shift)'),
                ('label_adjustment.move_right', 'Move label right (5px, or 1px with Shift)'),
                ('label_adjustment.resize_width_decrease', 'Decrease width (5px, or 1px with Shift)'),
                ('label_adjustment.resize_width_increase', 'Increase width (5px, or 1px with Shift)'),
                ('label_adjustment.resize_height_decrease', 'Decrease height (5px, or 1px with Shift)'),
                ('label_adjustment.resize_height_increase', 'Increase height (5px, or 1px with Shift)')
            ]
            
            for action, description in adjust_actions:
                keys = self.keymap_manager.get_keys_for_action(action)
                if keys:
                    adjust_keys.append(f"• {'/'.join(keys)} - {description}")
        
        if adjust_keys:
            help_sections.append("\nLabel Adjustment (when selected):\n" + "\n".join(adjust_keys))
        
        # System section
        system_keys = []
        if hasattr(self, 'keymap_manager'):
            system_actions = [
                ('system.save', 'Manual save current labels'),
                ('system.open_directory', 'Open directory'),
                ('system.show_help', 'Show this help'),
                ('system.zoom_in', 'Zoom in'),
                ('system.zoom_out', 'Zoom out'),
                ('system.reset_zoom', 'Reset zoom (fit to window)')
            ]
            
            for action, description in system_actions:
                keys = self.keymap_manager.get_keys_for_action(action)
                if keys:
                    system_keys.append(f"• {'/'.join(keys)} - {description}")
        
        if system_keys:
            help_sections.append("\nSystem:\n" + "\n".join(system_keys))
        
        # Additional info
        additional_info = [
            "\nText Editing:",
            "• Global shortcuts work everywhere except when typing in text boxes",
            "• Esc - Exit text editing mode and return to global shortcuts",
            "• Ctrl+S/O - Work even when typing in text boxes",
            "\nMouse Controls:",
            "• Click and drag - Create new bounding box",
            "• Click on box - Select box",
            "• Scroll wheel - Zoom in/out",
            "• Middle click + drag - Pan image",
            "\nOther:",
            "• Labels are auto-saved automatically",
            "\nConfiguration:",
            "• Keyboard shortcuts are configurable in settings/keymap.json"
        ]
        
        help_text = "\n".join(help_sections + additional_info)
        
        # Create a scrollable text view for the help content
        content_area = dialog.get_content_area()
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_size_request(580, 400)
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_margin_top(10)
        text_view.set_margin_bottom(10)
        text_view.set_margin_start(10)
        text_view.set_margin_end(10)
        
        buffer = text_view.get_buffer()
        buffer.set_text(help_text)
        
        scrolled_window.set_child(text_view)
        content_area.append(scrolled_window)
        
        dialog.connect('response', lambda d, r: d.destroy())
        dialog.present()
    
    def show_error(self, message: str):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.connect('response', lambda d, r: d.destroy())
        dialog.present()
    
    def show_info(self, message: str):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.connect('response', lambda d, r: d.destroy())
        dialog.present()
