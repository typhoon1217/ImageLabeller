#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, Gio, GLib
from pathlib import Path
from typing import Optional

from ..business.project_state import ProjectManager
from ..business.label_logic import LabelManager, OCRProcessor, ConfirmationManager
from ..core.validation import ValidationEngine
from .canvas_widget import ImageCanvas
from .event_handlers import EventHandlerMixin
from .filter_modal import FilterModal
from .profile_selector import show_profile_selector


class LabelEditorWindow(Gtk.ApplicationWindow, EventHandlerMixin):
    """Main application window - UI structure only"""
    
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("MRZ Label Editor")
        
        # Initialize managers
        config_file = Path(__file__).parent.parent.parent / 'settings.json'
        self.project_manager = ProjectManager(str(config_file))
        self.label_manager = LabelManager(self.project_manager.class_config)
        self.confirmation_manager = ConfirmationManager()
        
        # UI state
        self.unsaved_changes = False
        self._auto_save_timeout = None
        self._updating_selection = False
        self._editing_in_progress = False
        self._text_editing_active = False
        self._filtered_file_list = None  # For filtered results
        self._last_selected_class_id = None  # Remember last selected class for auto-selection
        
        # Setup window
        self._setup_window()
        self._setup_ui()
        self._setup_callbacks()
        self.setup_event_handlers()
        self._setup_css()
        
        # Load default directory if available
        if (self.project_manager.current_directory and 
            self.project_manager.current_directory.exists()):
            GLib.idle_add(self._load_directory_async, str(self.project_manager.current_directory))
    
    def _setup_window(self):
        """Setup window properties"""
        config = self.project_manager.config
        width = int(config.get('window_width', 1400))
        height = int(config.get('window_height', 900))
        self.set_default_size(width, height)
    
    def _setup_ui(self):
        """Setup UI structure"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(main_box)
        
        # Header bar
        self._setup_header_bar()
        
        # Content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)
        content_box.set_spacing(5)
        main_box.append(content_box)
        
        # Left sidebar - file list
        left_sidebar = self._create_file_sidebar()
        content_box.append(left_sidebar)
        
        # Middle area - canvas and navigation
        middle_box = self._create_canvas_area()
        content_box.append(middle_box)
        
        # Right sidebar - label editor
        right_sidebar = self._create_editor_sidebar()
        content_box.append(right_sidebar)
        
        # Status bar
        self.status_bar = Gtk.Label()
        self.status_bar.set_halign(Gtk.Align.START)
        self.status_bar.set_margin_start(10)
        self.status_bar.set_margin_end(10)
        self.status_bar.set_margin_top(5)
        self.status_bar.set_margin_bottom(5)
        main_box.append(self.status_bar)
        
        self.update_status("Ready")
    
    def _setup_header_bar(self):
        """Setup header bar with menu"""
        header_bar = Gtk.HeaderBar()
        self.set_titlebar(header_bar)
        
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        header_bar.pack_end(menu_button)
        
        menu = Gio.Menu()
        menu.append("Open Directory", "win.open-directory")
        menu.append("Open Image", "win.open-image")
        menu.append("Profile Manager", "win.profile-manager")
        menu.append("Keyboard Shortcuts", "win.show-help")
        menu_button.set_menu_model(menu)
        
        self._create_actions()
    
    def _create_actions(self):
        """Create menu actions"""
        actions = [
            ("open-directory", self.on_open_directory),
            ("open-image", self.on_open_image),
            ("save", self.on_save),
            ("profile-manager", self.on_profile_manager),
            ("show-help", lambda a, p: self.show_help_dialog())
        ]
        
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
    
    def _create_file_sidebar(self) -> Gtk.Box:
        """Create file list sidebar"""
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.set_size_request(250, -1)
        sidebar.set_hexpand(False)
        sidebar.set_vexpand(True)
        
        # Title and filter button
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_margin_top(10)
        title_box.set_margin_bottom(10)
        title_box.set_margin_start(10)
        title_box.set_margin_end(10)
        sidebar.append(title_box)
        
        title = Gtk.Label()
        title.set_markup("<b>Image Files</b>")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_box.append(title)
        
        # Filter button
        filter_button = Gtk.Button()
        filter_button.set_icon_name("funnel-symbolic")
        filter_button.set_tooltip_text("Filter and sort images")
        filter_button.connect('clicked', self._on_filter_clicked)
        filter_button.set_halign(Gtk.Align.END)
        title_box.append(filter_button)
        
        # File list
        self.file_list_store = Gtk.StringList()
        self.file_list_data = []  # Initialize file list data
        self.file_list_selection = Gtk.SingleSelection()
        self.file_list_selection.set_model(self.file_list_store)
        self.file_list_view = Gtk.ListView()
        self.file_list_view.set_model(self.file_list_selection)
        
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_list_setup)
        factory.connect('bind', self.on_list_bind)
        self.file_list_view.set_factory(factory)
        
        self.file_list_selection.connect('notify::selected', self.on_file_selected)
        
        scrolled_files = Gtk.ScrolledWindow()
        scrolled_files.set_child(self.file_list_view)
        scrolled_files.set_vexpand(True)
        scrolled_files.set_margin_start(10)
        scrolled_files.set_margin_end(10)
        sidebar.append(scrolled_files)
        
        # Directory stats
        self._create_directory_stats_section(sidebar)
        
        return sidebar
    
    def _create_directory_stats_section(self, sidebar):
        """Create directory statistics section with better formatting"""
        # Title
        stats_title = Gtk.Label()
        stats_title.set_markup("<b>Directory Statistics</b>")
        stats_title.set_halign(Gtk.Align.START)
        stats_title.set_margin_start(10)
        stats_title.set_margin_top(10)
        sidebar.append(stats_title)
        
        # Create frame for better visual separation
        stats_frame = Gtk.Frame()
        stats_frame.set_margin_start(10)
        stats_frame.set_margin_end(10)
        stats_frame.set_margin_top(5)
        stats_frame.set_margin_bottom(5)
        
        # Create grid for organized display
        self.dir_stats_grid = Gtk.Grid()
        self.dir_stats_grid.set_column_spacing(10)
        self.dir_stats_grid.set_row_spacing(5)
        self.dir_stats_grid.set_margin_start(10)
        self.dir_stats_grid.set_margin_end(10)
        self.dir_stats_grid.set_margin_top(10)
        self.dir_stats_grid.set_margin_bottom(10)
        
        # Add "No directory loaded" initially
        no_dir_label = Gtk.Label()
        no_dir_label.set_text("No directory loaded")
        no_dir_label.set_halign(Gtk.Align.CENTER)
        no_dir_label.add_css_class("dim-label")
        self.dir_stats_grid.attach(no_dir_label, 0, 0, 2, 1)
        
        stats_frame.set_child(self.dir_stats_grid)
        sidebar.append(stats_frame)
    
    def _create_canvas_area(self) -> Gtk.Box:
        """Create canvas area with navigation"""
        middle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        middle_box.set_hexpand(True)
        middle_box.set_vexpand(True)
        
        # Navigation toolbar
        nav_toolbar = self._create_navigation_toolbar()
        middle_box.append(nav_toolbar)
        
        # Canvas
        self.canvas = ImageCanvas(self.project_manager.class_config)
        self.canvas.on_box_selected = self.on_box_selected
        self.canvas.on_boxes_changed = self.on_boxes_changed
        self.canvas.is_text_editing_active = lambda: self._text_editing_active
        self.canvas.on_image_rotated = self._on_image_rotated
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.canvas)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        middle_box.append(scrolled)
        
        return middle_box
    
    def _create_navigation_toolbar(self) -> Gtk.Box:
        """Create navigation toolbar"""
        nav_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        nav_toolbar.set_spacing(10)
        nav_toolbar.set_margin_start(10)
        nav_toolbar.set_margin_end(10)
        nav_toolbar.set_margin_top(10)
        nav_toolbar.set_margin_bottom(10)
        nav_toolbar.set_hexpand(True)
        nav_toolbar.set_homogeneous(False)
        
        # Navigation buttons
        self.prev_button = Gtk.Button(label="◀ Previous")
        self.prev_button.connect('clicked', self.on_prev_clicked)
        self.prev_button.set_sensitive(False)
        nav_toolbar.append(self.prev_button)
        
        self.image_info_label = Gtk.Label()
        self.image_info_label.set_text("No images loaded")
        self.image_info_label.set_hexpand(True)
        self.image_info_label.set_halign(Gtk.Align.CENTER)
        nav_toolbar.append(self.image_info_label)
        
        self.next_button = Gtk.Button(label="Next ▶")
        self.next_button.connect('clicked', self.on_next_clicked)
        self.next_button.set_sensitive(False)
        nav_toolbar.append(self.next_button)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        nav_toolbar.append(separator)
        
        # Image rotation controls
        self._add_rotation_controls(nav_toolbar)
        
        # Zoom controls
        zoom_out_btn = Gtk.Button(label="−")
        zoom_out_btn.set_tooltip_text("Zoom Out (- key or scroll down)")
        zoom_out_btn.connect('clicked', self.on_zoom_out_clicked)
        nav_toolbar.append(zoom_out_btn)
        
        self.zoom_label = Gtk.Label()
        self.zoom_label.set_text("100%")
        self.zoom_label.set_tooltip_text("Current zoom level (0 key to reset)")
        nav_toolbar.append(self.zoom_label)
        
        zoom_in_btn = Gtk.Button(label="+")
        zoom_in_btn.set_tooltip_text("Zoom In (+ key or scroll up)")
        zoom_in_btn.connect('clicked', self.on_zoom_in_clicked)
        nav_toolbar.append(zoom_in_btn)
        
        reset_zoom_btn = Gtk.Button(label="⌂")
        reset_zoom_btn.set_tooltip_text("Fit to Window (0 key)")
        reset_zoom_btn.connect('clicked', self.on_reset_zoom_clicked)
        nav_toolbar.append(reset_zoom_btn)
        
        return nav_toolbar
    
    def _add_rotation_controls(self, nav_toolbar):
        """Add image rotation controls to navigation toolbar"""
        # Rotate counter-clockwise button
        rotate_left_btn = Gtk.Button(label="↺")
        rotate_left_btn.set_tooltip_text("Rotate 90° Counter-clockwise (Ctrl+Shift+R)")
        rotate_left_btn.connect('clicked', self._on_rotate_left_clicked)
        nav_toolbar.append(rotate_left_btn)
        
        # Rotate clockwise button  
        rotate_right_btn = Gtk.Button(label="↻")
        rotate_right_btn.set_tooltip_text("Rotate 90° Clockwise (Ctrl+R)")
        rotate_right_btn.connect('clicked', self._on_rotate_right_clicked)
        nav_toolbar.append(rotate_right_btn)
        
        # Reset rotation button
        reset_rotation_btn = Gtk.Button(label="⟲")
        reset_rotation_btn.set_tooltip_text("Reset Rotation (F5)")
        reset_rotation_btn.connect('clicked', self._on_reset_rotation_clicked)
        nav_toolbar.append(reset_rotation_btn)
        
        # Save rotated image button
        save_rotation_btn = Gtk.Button(label="💾")
        save_rotation_btn.set_tooltip_text("Save Rotated Image")
        save_rotation_btn.connect('clicked', self._on_save_rotation_clicked)
        save_rotation_btn.set_sensitive(False)
        nav_toolbar.append(save_rotation_btn)
        
        # Store button references
        self.rotate_left_btn = rotate_left_btn
        self.rotate_right_btn = rotate_right_btn
        self.reset_rotation_btn = reset_rotation_btn
        self.save_rotation_btn = save_rotation_btn
        
        # Rotation status label
        self.rotation_status_label = Gtk.Label()
        self.rotation_status_label.set_text("0°")
        self.rotation_status_label.set_margin_start(5)
        nav_toolbar.append(self.rotation_status_label)
    
    def _create_editor_sidebar(self) -> Gtk.Box:
        """Create label editor sidebar"""
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.set_size_request(150, -1)
        sidebar.set_hexpand(False)
        sidebar.set_vexpand(True)
        
        # Title
        title = Gtk.Label()
        title.set_markup("<b>Label Editor</b>")
        title.set_margin_top(10)
        title.set_margin_bottom(10)
        sidebar.append(title)
        
        # File info
        self.file_info = Gtk.Label()
        self.file_info.set_markup("<i>No file loaded</i>")
        self.file_info.set_wrap(True)
        self.file_info.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.file_info.set_valign(Gtk.Align.START)
        self.file_info.set_max_width_chars(20)
        self.file_info.set_margin_start(10)
        self.file_info.set_margin_end(10)
        self.file_info.set_use_markup(True)
        sidebar.append(self.file_info)
        
        # Separator
        separator = Gtk.Separator()
        separator.set_margin_top(10)
        separator.set_margin_bottom(10)
        sidebar.append(separator)
        
        # Raw DAT display
        self._add_dat_display(sidebar)
        
        # OCR counts table
        self._add_ocr_counts_table(sidebar)
        
        # Another separator
        separator2 = Gtk.Separator()
        separator2.set_margin_top(10)
        separator2.set_margin_bottom(10)
        sidebar.append(separator2)
        
        # Selected label editor
        self._add_label_editor(sidebar)
        
        return sidebar
    
    def _add_dat_display(self, sidebar):
        """Add DAT file display area"""
        labels_title = Gtk.Label()
        labels_title.set_markup("<b>Raw DAT File</b>")
        labels_title.set_halign(Gtk.Align.START)
        labels_title.set_margin_start(10)
        labels_title.set_margin_top(10)
        sidebar.append(labels_title)
        
        self.all_labels_text = Gtk.TextView()
        self.all_labels_text.set_editable(False)
        self.all_labels_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.all_labels_text.set_margin_start(10)
        self.all_labels_text.set_margin_end(10)
        self.all_labels_text.add_css_class("monospace")
        
        scrolled_labels = Gtk.ScrolledWindow()
        scrolled_labels.set_child(self.all_labels_text)
        scrolled_labels.set_size_request(-1, 200)
        sidebar.append(scrolled_labels)
    
    def _add_ocr_counts_table(self, sidebar):
        """Add OCR character counts table"""
        # OCR Character Count Display - using label like original
        self.ocr_count_label = Gtk.Label()
        self.ocr_count_label.set_markup(
            "<b>OCR Character Counts</b>\n<small>No labels</small>")
        self.ocr_count_label.set_halign(Gtk.Align.START)
        self.ocr_count_label.set_margin_start(10)
        self.ocr_count_label.set_margin_end(10)
        self.ocr_count_label.set_margin_top(10)
        self.ocr_count_label.set_use_markup(True)
        self.ocr_count_label.add_css_class("monospace")
        sidebar.append(self.ocr_count_label)
    
    def _add_label_editor(self, sidebar):
        """Add label editor controls"""
        # Selected label info
        selected_title = Gtk.Label()
        selected_title.set_markup("<b>Selected Label</b>")
        selected_title.set_halign(Gtk.Align.START)
        selected_title.set_margin_start(10)
        sidebar.append(selected_title)
        
        self.selected_info = Gtk.Label()
        self.selected_info.set_markup("<i>No box selected</i>")
        self.selected_info.set_margin_start(10)
        self.selected_info.set_margin_end(10)
        self.selected_info.set_halign(Gtk.Align.START)
        self.selected_info.set_valign(Gtk.Align.START)
        self.selected_info.set_wrap(True)
        self.selected_info.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.selected_info.set_max_width_chars(20)
        self.selected_info.set_use_markup(True)
        sidebar.append(self.selected_info)
        
        # OCR text editor
        ocr_label = Gtk.Label()
        ocr_label.set_markup("<b>OCR Text:</b>")
        ocr_label.set_halign(Gtk.Align.START)
        ocr_label.set_margin_start(10)
        ocr_label.set_margin_top(10)
        sidebar.append(ocr_label)
        
        self.ocr_text = Gtk.TextView()
        self.ocr_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.ocr_text.set_margin_start(10)
        self.ocr_text.set_margin_end(10)
        
        scrolled_text = Gtk.ScrolledWindow()
        scrolled_text.set_child(self.ocr_text)
        scrolled_text.set_size_request(-1, 100)
        sidebar.append(scrolled_text)
        
        # Text change handler
        buffer = self.ocr_text.get_buffer()
        buffer.connect('changed', self.on_ocr_text_changed)
        
        # Focus handlers
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect('enter', self.on_text_focus_in)
        focus_controller.connect('leave', self.on_text_focus_out)
        self.ocr_text.add_controller(focus_controller)
        
        # Class selector
        class_label = Gtk.Label()
        class_label.set_markup("<b>Class:</b>")
        class_label.set_halign(Gtk.Align.START)
        class_label.set_margin_start(10)
        class_label.set_margin_top(10)
        sidebar.append(class_label)
        
        self.class_combo = Gtk.DropDown()
        class_model = Gtk.StringList()
        for cls in self.project_manager.class_config["classes"]:
            class_model.append(cls["name"])
        self.class_combo.set_model(class_model)
        self.class_combo.set_margin_start(10)
        self.class_combo.set_margin_end(10)
        self.class_combo.connect('notify::selected', self.on_class_changed)
        sidebar.append(self.class_combo)
        
        # Action buttons
        self._add_action_buttons(sidebar)
    
    def _refresh_class_dropdown(self):
        """Refresh the class dropdown with current profile classes"""
        if not hasattr(self, 'class_combo'):
            return
        
        # Get current selection before clearing
        current_selection = self.class_combo.get_selected()
        
        # Create new model with updated classes
        class_model = Gtk.StringList()
        for cls in self.project_manager.class_config["classes"]:
            class_model.append(cls["name"])
        
        # Update the dropdown model
        self.class_combo.set_model(class_model)
        
        # Try to restore previous selection or select first item
        if current_selection != Gtk.INVALID_LIST_POSITION and current_selection < len(self.project_manager.class_config["classes"]):
            self.class_combo.set_selected(current_selection)
        elif len(self.project_manager.class_config["classes"]) > 0:
            self.class_combo.set_selected(0)
    
    def _refresh_profile_ui(self):
        """Comprehensive UI refresh for profile changes"""
        # Refresh class dropdown
        self._refresh_class_dropdown()
        
        # Clear selected label state
        if hasattr(self, 'selected_info'):
            self.selected_info.set_markup("<i>No box selected</i>")
        
        # Clear OCR text editor
        if hasattr(self, 'ocr_text'):
            buffer = self.ocr_text.get_buffer()
            buffer.set_text("")
        
        # Reset canvas selection if exists
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.selected_box = None
            self.canvas.queue_draw()
        
        # Update file info to reflect potential new directory
        if hasattr(self, 'file_info'):
            if self.project_manager.current_image_path:
                filename = Path(self.project_manager.current_image_path).name
                self.file_info.set_markup(f"<b>{filename}</b>")
            else:
                self.file_info.set_markup("<i>No file loaded</i>")
    
    def _add_action_buttons(self, sidebar):
        """Add action buttons"""
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        button_box.set_spacing(5)
        button_box.set_margin_start(10)
        button_box.set_margin_end(10)
        button_box.set_margin_top(20)
        sidebar.append(button_box)
        
        # Delete button
        delete_button = Gtk.Button(label="Delete Selected")
        delete_button.connect('clicked', self.on_delete_clicked)
        button_box.append(delete_button)
        
        # OCR button
        ocr_button = Gtk.Button(label="🔍 Run OCR")
        ocr_button.set_tooltip_text("Extract text from selected label area using selected OCR engine")
        ocr_button.connect('clicked', self.on_ocr_clicked)
        button_box.append(ocr_button)
        self.ocr_button = ocr_button
        
        # OCR model selection dropdown
        ocr_model_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ocr_model_label = Gtk.Label(label="OCR Model:")
        ocr_model_box.append(ocr_model_label)
        
        self.ocr_model_combo = Gtk.ComboBoxText()
        self.ocr_model_combo.append("tesseract", "Tesseract")
        self.ocr_model_combo.append("easyocr", "EasyOCR")
        self.ocr_model_combo.append("paddleocr", "PaddleOCR")
        self.ocr_model_combo.append("vietocr", "VietOCR (Vietnamese)")
        self.ocr_model_combo.set_active_id("tesseract")  # Default to Tesseract
        self.ocr_model_combo.set_tooltip_text("Select OCR engine to use")
        ocr_model_box.append(self.ocr_model_combo)
        
        button_box.append(ocr_model_box)
        
        # Confirmation checkbox
        self.confirm_checkbox = Gtk.CheckButton(label="✅ Confirmed")
        self.confirm_checkbox.set_tooltip_text("Toggle confirmation status (when confirming: go to next image)")
        self.confirm_checkbox.connect('toggled', self.on_confirm_toggled)
        self.confirm_checkbox.set_margin_top(10)
        button_box.append(self.confirm_checkbox)
        
        self.set_editing_enabled(False)
    
    def _setup_callbacks(self):
        """Setup callbacks between components"""
        # Project manager callbacks
        self.project_manager.on_directory_loaded = self._on_directory_loaded
        self.project_manager.on_image_changed = self._on_image_changed
        self.project_manager.on_status_update = self.update_status
        self.project_manager.on_error = self.show_error
        
        # Label manager callbacks
        self.label_manager.on_box_selected = self.on_box_selected
        self.label_manager.on_boxes_changed = self.on_boxes_changed
        self.label_manager.on_status_update = self.update_status
        self.label_manager.on_error = self.show_error
        
        # Confirmation manager callbacks - removed to prevent navigation interference
        # self.confirmation_manager.on_confirmation_changed = self._on_confirmation_changed
    
    def _setup_css(self):
        """Setup CSS styling"""
        css_provider = Gtk.CssProvider()
        css = """
        .monospace {
            font-family: 'DejaVu Sans Mono', 'Consolas', 'Monaco', monospace;
            font-size: 11px;
        }
        
        .file-normal { color: inherit; }
        .file-saved { color: #22c55e; font-weight: bold; }
        .file-valid { color: #10b981; }
        .file-no-dat { color: #f59e0b; }
        .file-missing-classes { color: #ef4444; font-weight: bold; }
        .file-invalid-regex { color: #dc2626; }
        .file-error { color: #991b1b; font-style: italic; }
        .file-confirmed { color: #22c55e; font-weight: bold; text-decoration: underline; }
        
        /* OCR counts table styling */
        .dim-label { color: #888888; font-style: italic; }
        
        /* Force software rendering to avoid GL context issues */
        #software-rendered-canvas {
            background-color: inherit;
        }
        """
        css_provider.load_from_string(css)
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    # Callback implementations
    def _on_directory_loaded(self, file_count: int):
        """Handle directory loaded"""
        # Update confirmation manager with new directory
        if self.project_manager.current_directory:
            self.confirmation_manager.set_directory(str(self.project_manager.current_directory))
            # Sync confirmation database with current directory files
            self.confirmation_manager.sync_confirmation_db_with_directory(str(self.project_manager.current_directory))
            # Initialize deletion history database
            self.label_manager.init_deletion_history_db(str(self.project_manager.current_directory))
            # Sync deletion history with current directory files
            self.label_manager.sync_deletion_history_with_directory(str(self.project_manager.current_directory))
        
        self.update_file_list()
        self.update_directory_stats()
        if file_count > 0:
            self.load_current_image()
            self.update_navigation_buttons()
            # Ensure canvas gets focus for immediate interaction
            if hasattr(self, 'canvas'):
                self.canvas.grab_focus()
    
    def _on_image_changed(self, image_path: str, dat_path):
        """Handle image changed"""
        self.load_current_image()
    
    # Removed _on_confirmation_changed to prevent navigation interference
    # File list colors will update naturally during navigation
    
    def _load_directory_async(self, directory_path: str):
        """Load directory asynchronously"""
        self.project_manager.load_directory(directory_path)
        return False  # Don't repeat
    
    # UI update methods
    def update_status(self, message: str):
        """Update status bar"""
        if hasattr(self, 'status_bar'):
            self.status_bar.set_text(message)
    
    def update_title(self):
        """Update window title"""
        title = "MRZ Label Editor"
        if self.project_manager.current_directory:
            title += f" - {self.project_manager.current_directory.name}"
            if self.project_manager.current_image_path:
                total = len(self.project_manager.image_files)
                current = self.project_manager.current_index + 1
                title += f" ({current}/{total})"
        elif self.project_manager.current_image_path:
            title += f" - {Path(self.project_manager.current_image_path).name}"
        if self.unsaved_changes:
            title += " *"
        self.set_title(title)
    
    def update_navigation_buttons(self):
        """Update navigation button states"""
        nav_state = self.project_manager.get_navigation_state()
        self.prev_button.set_sensitive(nav_state['can_go_previous'])
        self.next_button.set_sensitive(nav_state['can_go_next'])
        
        if hasattr(self, 'zoom_label') and hasattr(self.canvas, 'zoom_level'):
            zoom_percent = int(self.canvas.zoom_level * 100)
            self.zoom_label.set_text(f"{zoom_percent}%")
    
    def update_file_list(self):
        """Rebuild file list display (use only when directory changes)"""
        if hasattr(self, 'file_list_store'):
            self.file_list_store.splice(0, self.file_list_store.get_n_items())
            # Store file info as strings but we'll access full info in binding
            self.file_list_data = self._get_enriched_file_list()
            # Reset filtered list when directory changes
            self._filtered_file_list = None
            self._populate_file_list_store()
    
    def _get_enriched_file_list(self):
        """Get file list enriched with confirmation status"""
        file_list = self.project_manager.get_file_list()
        
        # Add confirmation status to each file
        for file_info in file_list:
            file_path = file_info['path']
            file_info['confirmed'] = self.confirmation_manager.get_confirmation(file_path)
        
        return file_list
    
    def _populate_file_list_store(self):
        """Populate file list store with current or filtered data"""
        if hasattr(self, 'file_list_store'):
            # Use filtered list if available, otherwise use all files
            display_files = self._filtered_file_list if self._filtered_file_list is not None else self.file_list_data
            
            for file_info in display_files:
                self.file_list_store.append(file_info['name'])
    
    def update_file_list_colors(self):
        """Update file list colors by swapping selection model"""
        if hasattr(self, 'file_list_store') and hasattr(self, 'file_list_selection'):
            print(f"update_file_list_colors called - updating {len(self.file_list_data) if hasattr(self, 'file_list_data') else 0} items")
            
            # Update the file list data to get latest validation status
            self.file_list_data = self._get_enriched_file_list()
            
            # For now, just update the data without forcing a visual refresh
            # The colors will update when the user navigates or the list naturally refreshes
            print("Updated file_list_data with new confirmation status")
            
            # TODO: Find a way to update colors without scroll reset
            # For now, skip the visual update to prevent scroll reset
    
    def update_directory_stats(self):
        """Update directory statistics display"""
        if not hasattr(self, 'dir_stats_grid'):
            return
        
        # Clear existing content
        child = self.dir_stats_grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.dir_stats_grid.remove(child)
            child = next_child
        
        stats = self.project_manager.get_directory_stats()
        if stats['loaded']:
            summary = stats['validation_summary']
            confirmation_stats = self.confirmation_manager.get_confirmation_stats()
            
            row = 0
            
            # Directory name
            dir_label = Gtk.Label()
            dir_label.set_markup(f"<b>{Path(stats['directory']).name}</b>")
            dir_label.set_halign(Gtk.Align.START)
            self.dir_stats_grid.attach(dir_label, 0, row, 2, 1)
            row += 1
            
            # Total files
            total_label = Gtk.Label()
            total_label.set_text("Total files:")
            total_label.set_halign(Gtk.Align.START)
            self.dir_stats_grid.attach(total_label, 0, row, 1, 1)
            
            total_count = Gtk.Label()
            total_count.set_markup(f"<b>{stats['total_files']}</b>")
            total_count.set_halign(Gtk.Align.END)
            self.dir_stats_grid.attach(total_count, 1, row, 1, 1)
            row += 1
            
            # Valid files
            valid_label = Gtk.Label()
            valid_label.set_text("Valid:")
            valid_label.set_halign(Gtk.Align.START)
            self.dir_stats_grid.attach(valid_label, 0, row, 1, 1)
            
            valid_count = Gtk.Label()
            valid_count.set_markup(f"<span color='#10b981'><b>{summary['valid']}</b></span>")
            valid_count.set_halign(Gtk.Align.END)
            self.dir_stats_grid.attach(valid_count, 1, row, 1, 1)
            row += 1
            
            # No DAT files
            no_dat_label = Gtk.Label()
            no_dat_label.set_text("No DAT:")
            no_dat_label.set_halign(Gtk.Align.START)
            self.dir_stats_grid.attach(no_dat_label, 0, row, 1, 1)
            
            no_dat_count = Gtk.Label()
            no_dat_count.set_markup(f"<span color='#f59e0b'><b>{summary['no_dat']}</b></span>")
            no_dat_count.set_halign(Gtk.Align.END)
            self.dir_stats_grid.attach(no_dat_count, 1, row, 1, 1)
            row += 1
            
            # Missing classes
            if summary.get('missing_classes', 0) > 0:
                missing_label = Gtk.Label()
                missing_label.set_text("Missing classes:")
                missing_label.set_halign(Gtk.Align.START)
                self.dir_stats_grid.attach(missing_label, 0, row, 1, 1)
                
                missing_count = Gtk.Label()
                missing_count.set_markup(f"<span color='#ef4444'><b>{summary['missing_classes']}</b></span>")
                missing_count.set_halign(Gtk.Align.END)
                self.dir_stats_grid.attach(missing_count, 1, row, 1, 1)
                row += 1
            
            # Regex errors
            if summary.get('regex_errors', 0) > 0:
                regex_label = Gtk.Label()
                regex_label.set_text("Invalid format:")
                regex_label.set_halign(Gtk.Align.START)
                self.dir_stats_grid.attach(regex_label, 0, row, 1, 1)
                
                regex_count = Gtk.Label()
                regex_count.set_markup(f"<span color='#dc2626'><b>{summary['regex_errors']}</b></span>")
                regex_count.set_halign(Gtk.Align.END)
                self.dir_stats_grid.attach(regex_count, 1, row, 1, 1)
                row += 1
            
            # Separator
            separator = Gtk.Separator()
            separator.set_margin_top(5)
            separator.set_margin_bottom(5)
            self.dir_stats_grid.attach(separator, 0, row, 2, 1)
            row += 1
            
            # Confirmed files
            confirmed_label = Gtk.Label()
            confirmed_label.set_text("Confirmed:")
            confirmed_label.set_halign(Gtk.Align.START)
            self.dir_stats_grid.attach(confirmed_label, 0, row, 1, 1)
            
            confirmed_count = Gtk.Label()
            confirmed_count.set_markup(f"<span color='#22c55e'><b>{confirmation_stats['confirmed']}/{confirmation_stats['total']}</b></span>")
            confirmed_count.set_halign(Gtk.Align.END)
            self.dir_stats_grid.attach(confirmed_count, 1, row, 1, 1)
            
        else:
            # No directory loaded
            no_dir_label = Gtk.Label()
            no_dir_label.set_text("No directory loaded")
            no_dir_label.set_halign(Gtk.Align.CENTER)
            no_dir_label.add_css_class("dim-label")
            self.dir_stats_grid.attach(no_dir_label, 0, 0, 2, 1)
    
    def update_all_labels_display(self):
        """Update all labels display"""
        if hasattr(self, 'all_labels_text') and hasattr(self, 'canvas'):
            buffer = self.all_labels_text.get_buffer()
            content = self.label_manager.get_dat_file_content()
            buffer.set_text(content, -1)
            
            # Update OCR counts table
            self.update_ocr_counts_table()
    
    def _find_best_available_class(self, target_class_id=None):
        """Find the best available class for OCR text display
        
        Args:
            target_class_id: Preferred class ID (from previous selection), or None
            
        Returns:
            BoundingBox: Best available box, or None if no boxes exist
        """
        if not hasattr(self, 'canvas') or not self.canvas.boxes:
            return None
        
        # If target class exists, prefer it
        if target_class_id is not None:
            for box in self.canvas.boxes:
                if box.class_id == target_class_id:
                    return box
        
        # Otherwise, find the class with lowest ID (highest priority)
        # Sort boxes by class_id to get consistent priority ordering
        sorted_boxes = sorted(self.canvas.boxes, key=lambda b: b.class_id)
        return sorted_boxes[0] if sorted_boxes else None

    def update_ocr_counts_table(self):
        """Update OCR character counts table"""
        if not hasattr(self, 'ocr_count_label'):
            return
        
        if not hasattr(self, 'canvas') or not self.canvas.boxes:
            # Update letter count to 0
            self.ocr_count_label.set_markup(
                "<b>OCR Character Counts</b>\n<small>No labels</small>")
            return
        
        # Calculate character counts by type
        total_letters = 0
        total_numbers = 0
        total_special = 0
        
        # Create table header
        table_text = "<b>OCR Character Counts</b>\n"
        table_text += "<tt>Line | <span color='white'>Letters</span> | <span color='#66ccff'>Numbers</span> | <span color='#ffff99'>Special</span> | Total</tt>\n"
        table_text += "<tt>-----|---------|---------|---------|------</tt>\n"
        
        for box in sorted(self.canvas.boxes, key=lambda b: b.class_id):
            # Count characters by type
            letter_count = sum(1 for char in box.ocr_text if char.isalpha())
            number_count = sum(1 for char in box.ocr_text if char.isdigit())
            special_count = sum(1 for char in box.ocr_text if not char.isalnum() and not char.isspace())
            # Total non-space characters
            total_chars = len(box.ocr_text.replace(' ', ''))
            
            total_letters += letter_count
            total_numbers += number_count
            total_special += special_count
            
            # Format table row with color coding
            table_text += f"<tt>{box.name:<4} | <span color='white'>{letter_count:^7}</span> | <span color='#66ccff'>{number_count:^7}</span> | <span color='#ffff99'>{special_count:^7}</span> | {total_chars:^5}</tt>\n"
        
        # Add totals row
        total_all = total_letters + total_numbers + total_special
        table_text += "<tt>-----|---------|---------|---------|------</tt>\n"
        table_text += f"<tt>{'ALL':<4} | <span color='white'>{total_letters:^7}</span> | <span color='#66ccff'>{total_numbers:^7}</span> | <span color='#ffff99'>{total_special:^7}</span> | {total_all:^5}</tt>"
        
        # Update the character count display
        self.ocr_count_label.set_markup(table_text)
    
    def load_current_image(self):
        """Load current image and DAT file"""
        image_info = self.project_manager.get_current_image_info()
        if not image_info:
            return
        
        # Clear OCR text box when loading new image to prevent persistence
        if hasattr(self, 'ocr_text'):
            self.ocr_text.get_buffer().set_text("", -1)
        
        # Load image in canvas
        self.canvas.load_image(image_info['path'])
        
        # Load labels
        if image_info['dat_exists']:
            self.label_manager.load_from_file(str(image_info['dat_path']))
            self.canvas.set_boxes(self.label_manager.boxes)
        else:
            self.label_manager.set_boxes([])
            self.canvas.set_boxes([])
        
        # Auto-select best available class for OCR text display
        best_box = self._find_best_available_class(self._last_selected_class_id)
        if best_box:
            # Select the best available box
            if self.canvas.selected_box:
                self.canvas.selected_box.selected = False
            best_box.selected = True
            self.canvas.selected_box = best_box
            
            # Update UI to show the selected box
            if hasattr(self, 'on_box_selected') and callable(self.on_box_selected):
                self.on_box_selected(best_box)
            
            # Enable editing controls
            self.set_editing_enabled(True)
        else:
            # No boxes available, clear selection
            self.canvas.selected_box = None
            if hasattr(self, 'selected_info'):
                self.selected_info.set_markup("<i>No box selected</i>")
            
            # Disable editing controls since no box is selected
            self.set_editing_enabled(False)
        
        # Update UI
        self.image_info_label.set_text(f"{image_info['index'] + 1}/{image_info['total']}: {image_info['filename']}")
        self.file_info.set_markup(f"<b>Image:</b> {image_info['filename']}\n<b>DAT:</b> {Path(image_info['dat_path']).name}")
        
        # Update confirmation status
        is_confirmed = self.confirmation_manager.get_confirmation(image_info['path'])
        self.confirm_checkbox.disconnect_by_func(self.on_confirm_toggled)
        self.confirm_checkbox.set_active(is_confirmed)
        self.confirm_checkbox.connect('toggled', self.on_confirm_toggled)
        
        self.unsaved_changes = False
        self.update_title()
        self.update_all_labels_display()
        
        # Update file list selection and colors
        self._updating_selection = True
        self.file_list_selection.set_selected(image_info['index'])
        # Ensure the selected item is visible in the scroll range
        if hasattr(self, 'file_list_view'):
            self.file_list_view.scroll_to(image_info['index'], Gtk.ListScrollFlags.SELECT)
        # Update file list colors to reflect current validation status
        self.update_file_list_colors()
        # Update directory statistics
        self.update_directory_stats()
        self._updating_selection = False
    
    def set_editing_enabled(self, enabled: bool):
        """Enable/disable editing controls"""
        if hasattr(self, 'ocr_text'):
            self.ocr_text.set_sensitive(enabled)
        if hasattr(self, 'class_combo'):
            self.class_combo.set_sensitive(enabled)
    
    def toggle_confirmation(self):
        """Toggle confirmation status"""
        if self.project_manager.current_image_path:
            old_status = self.confirmation_manager.get_confirmation(self.project_manager.current_image_path)
            new_status = self.confirmation_manager.toggle_confirmation(
                self.project_manager.current_image_path)
            
            # Update checkbox
            self.confirm_checkbox.disconnect_by_func(self.on_confirm_toggled)
            self.confirm_checkbox.set_active(new_status)
            self.confirm_checkbox.connect('toggled', self.on_confirm_toggled)
            
            # Only update file list colors if confirmation actually changed
            if old_status != new_status:
                print(f"Confirmation changed from {old_status} to {new_status} - updating colors")
                self.update_file_list_colors()
            else:
                print("Confirmation didn't change - skipping color update")
            
            # Only advance to next image when confirming (not when unconfirming)
            if new_status and self.project_manager.get_navigation_state()['can_go_next']:
                # Go to next image
                self.on_next_clicked(None)
            # When unconfirming (new_status is False), stay on current image
    
    def auto_save_current(self):
        """Auto-save current file"""
        if (self.project_manager.current_image_path and 
            self.unsaved_changes and 
            hasattr(self, 'canvas')):
            
            # Check if image has been rotated
            if self.canvas.has_unsaved_rotation():
                # For auto-save, only save labels with rotated coordinates
                # Don't auto-save the rotated image to avoid unintended changes
                self.update_status("Auto-save: Labels saved with rotated coordinates (image rotation not auto-saved)")
            
            self.label_manager.boxes = self.canvas.boxes
            dat_path = Path(self.project_manager.current_image_path).with_suffix('.dat')
            self.label_manager.save_to_file(str(dat_path))
            self.unsaved_changes = False
            self.update_title()
    
    def save_dat_file(self, file_path: str):
        """Save DAT file"""
        if hasattr(self, 'canvas'):
            self.label_manager.boxes = self.canvas.boxes
            if self.label_manager.save_to_file(file_path):
                self.unsaved_changes = False
                self.update_title()
                # Update file list colors to reflect new validation status
                self.update_file_list_colors()
                # Update directory statistics
                self.update_directory_stats()
    
    def load_image(self, image_path: str):
        """Load a single image"""
        # This is for opening individual images, not part of directory navigation
        self.canvas.load_image(image_path)
        self.project_manager.current_image_path = image_path
        dat_path = Path(image_path).with_suffix('.dat')
        
        if dat_path.exists():
            self.label_manager.load_from_file(str(dat_path))
            self.canvas.set_boxes(self.label_manager.boxes)
        else:
            self.label_manager.set_boxes([])
            self.canvas.set_boxes([])
        
        self.file_info.set_text(f"Image: {Path(image_path).name}\\nDAT: {dat_path.name}")
        self.update_all_labels_display()
        self.unsaved_changes = False
        self.update_title()
    
    def _delayed_auto_save(self):
        """Delayed auto-save implementation"""
        try:
            if (self.unsaved_changes and 
                self.project_manager.current_image_path and 
                hasattr(self, 'canvas')):
                self.label_manager.boxes = self.canvas.boxes
                dat_path = Path(self.project_manager.current_image_path).with_suffix('.dat')
                self.label_manager.save_to_file(str(dat_path))
                self.unsaved_changes = False
                self.update_title()
        except Exception as e:
            self.show_error(f"Auto-save error: {e}")
        
        self._editing_in_progress = False
        self._auto_save_timeout = None
        return False  # Don't repeat
    
    def _on_filter_clicked(self, button):
        """Handle filter button click"""
        if not hasattr(self, 'file_list_data') or not self.file_list_data:
            return
        
        # Create and show filter modal
        filter_modal = FilterModal(
            parent_window=self,
            file_list_data=self.file_list_data,
            on_filter_applied=self._on_filter_applied
        )
        filter_modal.present()
    
    def _on_filter_applied(self, filtered_files):
        """Handle filter results applied"""
        # Store filtered results
        self._filtered_file_list = filtered_files
        
        # Rebuild file list display
        if hasattr(self, 'file_list_store'):
            self.file_list_store.splice(0, self.file_list_store.get_n_items())
            self._populate_file_list_store()
        
        # Update the displayed file list data for binding
        # We need to update the binding to use filtered data
        self._update_file_list_binding()
    
    def _update_file_list_binding(self):
        """Update file list binding to use current display files"""
        # This method updates the internal mapping for the file list binding
        # The binding methods will now use the filtered data when available
        pass
    
    # Image rotation event handlers
    def _on_rotate_left_clicked(self, button):
        """Handle rotate counter-clockwise button click"""
        if hasattr(self, 'canvas'):
            self.canvas.rotate_image_counterclockwise()
    
    def _on_rotate_right_clicked(self, button):
        """Handle rotate clockwise button click"""
        if hasattr(self, 'canvas'):
            self.canvas.rotate_image_clockwise()
    
    def _on_reset_rotation_clicked(self, button):
        """Handle reset rotation button click"""
        if hasattr(self, 'canvas'):
            # Reload original boxes from file
            self._reload_original_boxes()
            self.canvas.reset_image_rotation()
    
    def _on_save_rotation_clicked(self, button):
        """Handle save rotation button click"""
        if not hasattr(self, 'canvas') or not self.canvas.has_unsaved_rotation():
            return
        
        # Show save options dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Save Rotated Image"
        )
        dialog.set_property("secondary-text", 
            "How would you like to save the rotated image?\n\n"
            "• Overwrite: Replace the original image file\n"
            "• Save Copy: Save as a new file with '_rotated' suffix"
        )
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save Copy", Gtk.ResponseType.NO)  
        dialog.add_button("Overwrite", Gtk.ResponseType.YES)
        dialog.set_default_response(Gtk.ResponseType.NO)
        
        # GTK4 compatible dialog handling
        def on_dialog_response(dialog, response_id):
            dialog.destroy()
            if response_id == Gtk.ResponseType.YES:
                # Overwrite original - save both image and current labels
                self._save_rotated_image_and_current_labels()
            elif response_id == Gtk.ResponseType.NO:
                # Save copy - just save image copy
                saved_path = self.canvas.save_rotated_image(overwrite=False)
                if saved_path:
                    self.update_status(f"Rotated image saved as: {Path(saved_path).name}")
                else:
                    self.show_error("Failed to save rotated image copy")
        
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
                    self._update_rotation_controls(0, False)
                else:
                    self.show_error("Failed to retrieve current label coordinates")
            else:
                self.show_error("Failed to save rotated image")
        except Exception as e:
            self.show_error(f"Error saving rotated content: {e}")
    
    def _reload_original_boxes(self):
        """Reload original bounding boxes from file"""
        if not self.project_manager.current_dat_path:
            return
        
        try:
            if self.project_manager.current_dat_path.exists():
                original_boxes = self.label_manager.load_from_file(
                    str(self.project_manager.current_dat_path)
                )
                self.canvas.boxes = original_boxes
            else:
                self.canvas.boxes = []
        except Exception as e:
            self.show_error(f"Error reloading original boxes: {e}")
    
    def _update_rotation_controls(self, rotation_angle: int, has_unsaved: bool):
        """Update rotation controls based on current state"""
        if hasattr(self, 'rotation_status_label'):
            self.rotation_status_label.set_text(f"{rotation_angle}°")
        
        if hasattr(self, 'save_rotation_btn'):
            self.save_rotation_btn.set_sensitive(has_unsaved)
    
    def _on_image_rotated(self, *args):
        """Handle image rotation callback from canvas"""
        if len(args) == 2:
            # Called with rotation_angle and has_unsaved
            rotation_angle, has_unsaved = args
            self._update_rotation_controls(rotation_angle, has_unsaved)
        elif len(args) == 1 and args[0] == 'reset':
            # Reset callback - reload original image and boxes
            self._reload_original_boxes()
            self._update_rotation_controls(0, False)