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
        menu.append("Save", "win.save")
        menu.append("Save As", "win.save-as")
        menu.append("Keyboard Shortcuts", "win.show-help")
        menu.append("Quit", "win.quit")
        menu_button.set_menu_model(menu)
        
        self._create_actions()
    
    def _create_actions(self):
        """Create menu actions"""
        actions = [
            ("open-directory", self.on_open_directory),
            ("open-image", self.on_open_image),
            ("save", self.on_save),
            ("save-as", self.on_save_as),
            ("quit", self.on_quit),
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
        
        # Title
        title = Gtk.Label()
        title.set_markup("<b>Image Files</b>")
        title.set_margin_top(10)
        title.set_margin_bottom(10)
        sidebar.append(title)
        
        # File list
        self.file_list_store = Gtk.StringList()
        self.file_list_selection = Gtk.SingleSelection(model=self.file_list_store)
        self.file_list_view = Gtk.ListView(model=self.file_list_selection, factory=None)
        
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
        self.dir_stats = Gtk.Label()
        self.dir_stats.set_text("No directory loaded")
        self.dir_stats.set_wrap(True)
        self.dir_stats.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.dir_stats.set_valign(Gtk.Align.START)
        self.dir_stats.set_max_width_chars(35)
        self.dir_stats.set_margin_start(10)
        self.dir_stats.set_margin_end(10)
        self.dir_stats.set_margin_top(10)
        sidebar.append(self.dir_stats)
        
        return sidebar
    
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
    
    def _create_editor_sidebar(self) -> Gtk.Box:
        """Create label editor sidebar"""
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.set_size_request(300, -1)
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
        self.file_info.set_text("No file loaded")
        self.file_info.set_wrap(True)
        self.file_info.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.file_info.set_valign(Gtk.Align.START)
        self.file_info.set_max_width_chars(40)
        self.file_info.set_margin_start(10)
        self.file_info.set_margin_end(10)
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
        # Title
        ocr_title = Gtk.Label()
        ocr_title.set_markup("<b>OCR Character Counts</b>")
        ocr_title.set_halign(Gtk.Align.START)
        ocr_title.set_margin_start(10)
        ocr_title.set_margin_top(10)
        sidebar.append(ocr_title)
        
        # Create scrolled window for the table
        scrolled_counts = Gtk.ScrolledWindow()
        scrolled_counts.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_counts.set_size_request(-1, 100)
        scrolled_counts.set_margin_start(10)
        scrolled_counts.set_margin_end(10)
        scrolled_counts.set_margin_top(5)
        
        # Create grid for table layout
        self.ocr_counts_grid = Gtk.Grid()
        self.ocr_counts_grid.set_column_spacing(10)
        self.ocr_counts_grid.set_row_spacing(2)
        self.ocr_counts_grid.set_margin_start(5)
        self.ocr_counts_grid.set_margin_end(5)
        self.ocr_counts_grid.set_margin_top(5)
        self.ocr_counts_grid.set_margin_bottom(5)
        
        # Add headers
        class_header = Gtk.Label()
        class_header.set_markup("<b>Class</b>")
        class_header.set_halign(Gtk.Align.START)
        self.ocr_counts_grid.attach(class_header, 0, 0, 1, 1)
        
        count_header = Gtk.Label()
        count_header.set_markup("<b>Count</b>")
        count_header.set_halign(Gtk.Align.END)
        self.ocr_counts_grid.attach(count_header, 1, 0, 1, 1)
        
        # Add separator row
        separator_line = Gtk.Separator()
        separator_line.set_margin_top(2)
        separator_line.set_margin_bottom(2)
        self.ocr_counts_grid.attach(separator_line, 0, 1, 2, 1)
        
        # Add "No labels" row initially
        no_labels = Gtk.Label()
        no_labels.set_text("No labels")
        no_labels.set_halign(Gtk.Align.START)
        no_labels.add_css_class("dim-label")
        self.ocr_counts_grid.attach(no_labels, 0, 2, 2, 1)
        
        scrolled_counts.set_child(self.ocr_counts_grid)
        sidebar.append(scrolled_counts)
    
    def _add_label_editor(self, sidebar):
        """Add label editor controls"""
        # Selected label info
        selected_title = Gtk.Label()
        selected_title.set_markup("<b>Selected Label</b>")
        selected_title.set_halign(Gtk.Align.START)
        selected_title.set_margin_start(10)
        sidebar.append(selected_title)
        
        self.selected_info = Gtk.Label()
        self.selected_info.set_text("No box selected")
        self.selected_info.set_margin_start(10)
        self.selected_info.set_margin_end(10)
        self.selected_info.set_halign(Gtk.Align.START)
        self.selected_info.set_valign(Gtk.Align.START)
        self.selected_info.set_wrap(True)
        self.selected_info.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.selected_info.set_max_width_chars(40)
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
        ocr_button.set_tooltip_text("Extract text from selected label area using Tesseract OCR optimized for MRZ")
        ocr_button.connect('clicked', self.on_ocr_clicked)
        button_box.append(ocr_button)
        self.ocr_button = ocr_button
        
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
        """Update file list display"""
        if hasattr(self, 'file_list_store'):
            self.file_list_store.splice(0, self.file_list_store.get_n_items())
            # Store file info as strings but we'll access full info in binding
            self.file_list_data = self.project_manager.get_file_list()
            for file_info in self.file_list_data:
                self.file_list_store.append(file_info['name'])
    
    def update_directory_stats(self):
        """Update directory statistics display"""
        stats = self.project_manager.get_directory_stats()
        if stats['loaded']:
            summary = stats['validation_summary']
            confirmation_stats = self.confirmation_manager.get_confirmation_stats()
            
            stats_text = f"Directory: {Path(stats['directory']).name}\\n"
            stats_text += f"Total files: {stats['total_files']}\\n"
            stats_text += f"Valid: {summary['valid']}, No DAT: {summary['no_dat']}\\n"
            stats_text += f"Confirmed: {confirmation_stats['confirmed']}/{confirmation_stats['total']}"
            self.dir_stats.set_text(stats_text)
        else:
            self.dir_stats.set_text("No directory loaded")
    
    def update_all_labels_display(self):
        """Update all labels display"""
        if hasattr(self, 'all_labels_text') and hasattr(self, 'canvas'):
            buffer = self.all_labels_text.get_buffer()
            content = self.label_manager.get_dat_file_content()
            buffer.set_text(content)
            
            # Update OCR counts table
            self.update_ocr_counts_table()
    
    def update_ocr_counts_table(self):
        """Update OCR character counts table"""
        if not hasattr(self, 'ocr_counts_grid'):
            return
        
        # Clear existing data rows (keep header and separator)
        # Remove all children from row 2 onwards
        child = self.ocr_counts_grid.get_child_at(0, 2)
        while child:
            self.ocr_counts_grid.remove(child)
            child = self.ocr_counts_grid.get_child_at(0, 2)
        
        # Get OCR character counts
        counts = self.label_manager.get_ocr_character_counts()
        
        if counts:
            # Add data rows
            row = 2
            for class_name, count in counts.items():
                # Class name column
                class_label = Gtk.Label()
                class_label.set_text(class_name)
                class_label.set_halign(Gtk.Align.START)
                self.ocr_counts_grid.attach(class_label, 0, row, 1, 1)
                
                # Count column
                count_label = Gtk.Label()
                count_label.set_text(str(count))
                count_label.set_halign(Gtk.Align.END)
                count_label.add_css_class("monospace")
                self.ocr_counts_grid.attach(count_label, 1, row, 1, 1)
                
                row += 1
        else:
            # Add "No labels" row
            no_labels = Gtk.Label()
            no_labels.set_text("No labels")
            no_labels.set_halign(Gtk.Align.START)
            no_labels.add_css_class("dim-label")
            self.ocr_counts_grid.attach(no_labels, 0, 2, 2, 1)
    
    def load_current_image(self):
        """Load current image and DAT file"""
        image_info = self.project_manager.get_current_image_info()
        if not image_info:
            return
        
        # Load image in canvas
        self.canvas.load_image(image_info['path'])
        
        # Load labels
        if image_info['dat_exists']:
            self.label_manager.load_from_file(str(image_info['dat_path']))
            self.canvas.set_boxes(self.label_manager.boxes)
        else:
            self.label_manager.set_boxes([])
            self.canvas.set_boxes([])
        
        # Update UI
        self.image_info_label.set_text(f"{image_info['index'] + 1}/{image_info['total']}: {image_info['filename']}")
        self.file_info.set_text(f"Image: {image_info['filename']}\\nDAT: {Path(image_info['dat_path']).name}")
        
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
        self.update_file_list()  # Update colors without navigation interference
        self.file_list_selection.set_selected(image_info['index'])
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
            new_status = self.confirmation_manager.toggle_confirmation(
                self.project_manager.current_image_path)
            
            # Update checkbox
            self.confirm_checkbox.disconnect_by_func(self.on_confirm_toggled)
            self.confirm_checkbox.set_active(new_status)
            self.confirm_checkbox.connect('toggled', self.on_confirm_toggled)
            
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