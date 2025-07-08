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
            print("Please ensure keymap.json exists in the project root directory")
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
                buffer.set_text(box.ocr_text)
            
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
                self.ocr_text.get_buffer().set_text("")
            self.set_editing_enabled(False)
        
        self.update_all_labels_display()
    
    def on_boxes_changed(self):
        """Handle boxes changed event"""
        self.unsaved_changes = True
        self._editing_in_progress = True
        self.update_title()
        
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
        filename = string_object.get_string()
        label.set_text(filename)
        
        # Apply validation status styling
        if hasattr(self, 'file_list_data'):
            # Find the file info for this item
            position = list_item.get_position()
            if position < len(self.file_list_data):
                file_info = self.file_list_data[position]
                validation_status = file_info.get('validation_status', 'normal')
                
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
            hasattr(self, 'project_manager') and 
            selected < len(self.project_manager.image_files)):
            if selected != self.project_manager.current_index:
                self.auto_save_current()
                if self.project_manager.navigate_to_image(selected):
                    self.load_current_image()
                    # Ensure canvas gets focus for immediate interaction
                    if hasattr(self, 'canvas'):
                        self.canvas.grab_focus()
    
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
    
    def on_save(self, action, param):
        """Handle save action"""
        if hasattr(self, 'project_manager') and self.project_manager.current_dat_path:
            self.save_dat_file(str(self.project_manager.current_dat_path))
    
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
        if (not hasattr(self, 'canvas') or not self.canvas.selected_box or 
            not hasattr(self, 'project_manager') or not self.project_manager.current_image_path):
            self.show_error("Please select a label first")
            return
        
        button.set_label("⏳ Processing...")
        button.set_sensitive(False)
        
        # Setup OCR processor
        if not hasattr(self, 'ocr_processor'):
            self.ocr_processor = OCRProcessor(self.project_manager.class_config)
            self.ocr_processor.on_ocr_complete = lambda text, current: self._ocr_complete(button, text)
            self.ocr_processor.on_ocr_error = lambda error: self._ocr_error(button, error)
        
        self.ocr_processor.process_ocr(
            self.project_manager.current_image_path, 
            self.canvas.selected_box
        )
    
    def on_confirm_toggled(self, checkbox):
        """Handle confirmation checkbox toggle"""
        if hasattr(self, 'project_manager') and self.project_manager.current_image_path:
            is_confirmed = checkbox.get_active()
            
            # Update confirmation status
            if hasattr(self, 'confirmation_manager'):
                self.confirmation_manager.set_confirmation(
                    self.project_manager.current_image_path, is_confirmed)
            
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
                if hasattr(self, 'ocr_button'):
                    self.on_ocr_clicked(self.ocr_button)
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
                    self.handle_label_adjustment(action)
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
    
    def handle_label_adjustment(self, action: str):
        """Handle label position and size adjustment"""
        if not hasattr(self, 'canvas') or not self.canvas.selected_box:
            return
        
        box = self.canvas.selected_box
        adjustment_step = 5  # pixels for movement
        resize_step = 5      # pixels for resizing
        
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
        button.set_label("🔍 Run OCR")
        button.set_sensitive(True)
        
        if not extracted_text.strip():
            self.show_info("No text detected in the selected region")
            return
        
        current_text = ""
        if hasattr(self, 'canvas') and self.canvas.selected_box:
            current_text = self.canvas.selected_box.ocr_text
        
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
            if response == Gtk.ResponseType.YES and hasattr(self, 'ocr_text'):
                buffer = self.ocr_text.get_buffer()
                buffer.set_text(extracted_text)
            d.destroy()
        
        dialog.connect('response', on_response)
        dialog.present()
    
    def _ocr_error(self, button, error_message):
        """Handle OCR error"""
        button.set_label("🔍 Run OCR")
        button.set_sensitive(True)
        self.show_error(error_message)
    
    # Dialog helpers
    def show_help_dialog(self):
        """Show help dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Keyboard Shortcuts"
        )
        
        help_text = """Navigation:
• A/D or ←→ or Space/Backspace - Previous/Next image
• Ctrl+N/P - Next/Previous image (alternative)

Label Editing:
• Tab - Select next label
• 1-9, 0 - Focus on label N (by class order, 0=label 10)
• X - Focus OCR text box for editing
• Z - Run OCR on selected label
• Delete - Delete selected label
• Esc - Exit text editing / Deselect all labels

Label Adjustment (when selected):
• W/S - Move label up/down
• Q/E - Move label left/right
• R/T - Decrease/increase width
• F/G - Decrease/increase height

Text Editing:
• Global shortcuts work everywhere except when typing in text boxes
• Esc - Exit text editing mode and return to global shortcuts
• Ctrl+S/O - Work even when typing in text boxes

Confirmation:
• Enter or C - Toggle confirmation status (when confirming: go to next image)

Zoom & View:
• +/- or B/V - Zoom in/out
• N - Reset zoom (fit to window)
• Scroll wheel - Zoom in/out
• Middle click + drag - Pan image

File Operations:
• Ctrl+O - Open directory
• Ctrl+S - Manual save current labels
• Labels are auto-saved automatically

Help:
• H / F1 - Show this help

Configuration:
• Keyboard shortcuts are configurable in keymap.json"""
        
        dialog.set_property("secondary-text", help_text)
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