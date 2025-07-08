#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import re
from typing import List, Dict, Callable, Optional
from enum import Enum


class FilterType(Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class FilterCategory(Enum):
    FILENAME = "filename"
    STATUS = "status"
    CONFIRMATION = "confirmation"
    VALIDATION = "validation"
    EXTENSION = "extension"


class FilterRule:
    def __init__(self, category: FilterCategory, filter_type: FilterType, 
                 pattern: str, regex_enabled: bool = False):
        self.category = category
        self.filter_type = filter_type
        self.pattern = pattern
        self.regex_enabled = regex_enabled
        self.compiled_regex = None
        
        if regex_enabled:
            try:
                self.compiled_regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                self.compiled_regex = None
    
    def matches(self, file_info: Dict) -> bool:
        """Check if file matches this filter rule"""
        if self.category == FilterCategory.FILENAME:
            text = file_info.get('name', '')
        elif self.category == FilterCategory.STATUS:
            text = file_info.get('status', '')
        elif self.category == FilterCategory.CONFIRMATION:
            text = 'confirmed' if file_info.get('confirmed', False) else 'unconfirmed'
        elif self.category == FilterCategory.VALIDATION:
            text = file_info.get('validation_status', '')
        elif self.category == FilterCategory.EXTENSION:
            text = file_info.get('name', '').split('.')[-1] if '.' in file_info.get('name', '') else ''
        else:
            return False
        
        if self.regex_enabled and self.compiled_regex:
            return bool(self.compiled_regex.search(text))
        else:
            # Escape special characters for literal matching
            escaped_pattern = re.escape(self.pattern)
            return bool(re.search(escaped_pattern, text, re.IGNORECASE))


class SortOption(Enum):
    FILENAME_ASC = "filename_asc"
    FILENAME_DESC = "filename_desc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"
    CONFIRMATION_ASC = "confirmation_asc"
    CONFIRMATION_DESC = "confirmation_desc"
    VALIDATION_ASC = "validation_asc"
    VALIDATION_DESC = "validation_desc"


class FilterModal(Gtk.Window):
    """Modal window for filtering and sorting image list"""
    
    def __init__(self, parent_window, file_list_data: List[Dict], 
                 on_filter_applied: Callable[[List[Dict]], None]):
        super().__init__()
        self.parent_window = parent_window
        self.file_list_data = file_list_data
        self.on_filter_applied = on_filter_applied
        self.filter_rules: List[FilterRule] = []
        self.current_sort = SortOption.FILENAME_ASC
        
        self._setup_window()
        self._setup_ui()
        self._setup_css()
        
        # Apply initial filtering
        self._apply_filters()
    
    def _setup_window(self):
        """Setup window properties"""
        self.set_title("Filter & Sort Images")
        self.set_transient_for(self.parent_window)
        self.set_modal(True)
        self.set_default_size(900, 600)  # Wider for horizontal layout
        self.set_resizable(True)
        
        # Center on parent
        if self.parent_window:
            parent_size = self.parent_window.get_default_size()
            self.set_default_size(min(900, parent_size[0] - 100), min(600, parent_size[1] - 100))
    
    def _setup_ui(self):
        """Setup UI structure"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        self.set_child(main_box)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<b>Filter &amp; Sort Images</b>")
        title_label.set_halign(Gtk.Align.START)
        main_box.append(title_label)
        
        # Create horizontal paned layout for filters and preview
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_hexpand(True)
        paned.set_position(450)  # Initial position
        main_box.append(paned)
        
        # Left side - filters and controls
        left_scrolled = Gtk.ScrolledWindow()
        left_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_scrolled.set_size_request(400, -1)
        paned.set_start_child(left_scrolled)
        
        left_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        left_content.set_margin_start(10)
        left_content.set_margin_end(10)
        left_content.set_margin_top(10)
        left_content.set_margin_bottom(10)
        left_scrolled.set_child(left_content)
        
        # Sort section
        self._create_sort_section(left_content)
        
        # Filter section
        self._create_filter_section(left_content)
        
        # Right side - preview
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        right_box.set_margin_start(10)
        right_box.set_margin_end(10)
        right_box.set_margin_top(10)
        right_box.set_margin_bottom(10)
        paned.set_end_child(right_box)
        
        # Preview section
        self._create_preview_section(right_box)
        
        # Buttons
        self._create_buttons(main_box)
    
    def _create_sort_section(self, parent):
        """Create sort options section"""
        sort_frame = Gtk.Frame()
        sort_frame.set_label("Sort Options")
        parent.append(sort_frame)
        
        sort_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sort_box.set_margin_start(15)
        sort_box.set_margin_end(15)
        sort_box.set_margin_top(10)
        sort_box.set_margin_bottom(15)
        sort_frame.set_child(sort_box)
        
        # Sort dropdown
        sort_label = Gtk.Label()
        sort_label.set_markup("<b>Sort by:</b>")
        sort_label.set_halign(Gtk.Align.START)
        sort_box.append(sort_label)
        
        self.sort_combo = Gtk.DropDown()
        sort_model = Gtk.StringList()
        sort_options = [
            ("Filename (A-Z)", SortOption.FILENAME_ASC),
            ("Filename (Z-A)", SortOption.FILENAME_DESC),
            ("Status (A-Z)", SortOption.STATUS_ASC),
            ("Status (Z-A)", SortOption.STATUS_DESC),
            ("Confirmation (Confirmed first)", SortOption.CONFIRMATION_DESC),
            ("Confirmation (Unconfirmed first)", SortOption.CONFIRMATION_ASC),
            ("Validation (Valid first)", SortOption.VALIDATION_DESC),
            ("Validation (Invalid first)", SortOption.VALIDATION_ASC)
        ]
        
        self.sort_option_mapping = {}
        for display_name, sort_option in sort_options:
            sort_model.append(display_name)
            self.sort_option_mapping[display_name] = sort_option
        
        self.sort_combo.set_model(sort_model)
        self.sort_combo.set_selected(0)  # Default to filename A-Z
        self.sort_combo.connect('notify::selected', self._on_sort_changed)
        sort_box.append(self.sort_combo)
    
    def _create_filter_section(self, parent):
        """Create filter rules section"""
        filter_frame = Gtk.Frame()
        filter_frame.set_label("Filter Rules")
        parent.append(filter_frame)
        
        filter_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        filter_box.set_margin_start(15)
        filter_box.set_margin_end(15)
        filter_box.set_margin_top(10)
        filter_box.set_margin_bottom(15)
        filter_frame.set_child(filter_box)
        
        # Add filter controls
        self._create_filter_controls(filter_box)
        
        # Filter rules list
        rules_label = Gtk.Label()
        rules_label.set_markup("<b>Active Filter Rules:</b>")
        rules_label.set_halign(Gtk.Align.START)
        filter_box.append(rules_label)
        
        # Scrolled window for filter rules
        rules_scrolled = Gtk.ScrolledWindow()
        rules_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rules_scrolled.set_size_request(-1, 150)
        filter_box.append(rules_scrolled)
        
        self.rules_list_box = Gtk.ListBox()
        self.rules_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.rules_list_box.add_css_class("boxed-list")
        rules_scrolled.set_child(self.rules_list_box)
    
    def _create_filter_controls(self, parent):
        """Create filter input controls"""
        controls_grid = Gtk.Grid()
        controls_grid.set_column_spacing(10)
        controls_grid.set_row_spacing(8)
        parent.append(controls_grid)
        
        # Category dropdown
        category_label = Gtk.Label()
        category_label.set_text("Category:")
        category_label.set_halign(Gtk.Align.START)
        controls_grid.attach(category_label, 0, 0, 1, 1)
        
        self.category_combo = Gtk.DropDown()
        category_model = Gtk.StringList()
        categories = [
            ("Filename", FilterCategory.FILENAME),
            ("Status", FilterCategory.STATUS),
            ("Confirmation", FilterCategory.CONFIRMATION),
            ("Validation", FilterCategory.VALIDATION),
            ("Extension", FilterCategory.EXTENSION)
        ]
        
        self.category_mapping = {}
        for display_name, category in categories:
            category_model.append(display_name)
            self.category_mapping[display_name] = category
        
        self.category_combo.set_model(category_model)
        self.category_combo.set_selected(0)
        controls_grid.attach(self.category_combo, 1, 0, 1, 1)
        
        # Filter type dropdown
        type_label = Gtk.Label()
        type_label.set_text("Type:")
        type_label.set_halign(Gtk.Align.START)
        controls_grid.attach(type_label, 0, 1, 1, 1)
        
        self.type_combo = Gtk.DropDown()
        type_model = Gtk.StringList()
        type_model.append("Include")
        type_model.append("Exclude")
        self.type_combo.set_model(type_model)
        self.type_combo.set_selected(0)
        controls_grid.attach(self.type_combo, 1, 1, 1, 1)
        
        # Pattern entry
        pattern_label = Gtk.Label()
        pattern_label.set_text("Pattern:")
        pattern_label.set_halign(Gtk.Align.START)
        controls_grid.attach(pattern_label, 0, 2, 1, 1)
        
        self.pattern_entry = Gtk.Entry()
        self.pattern_entry.set_placeholder_text("Enter search pattern...")
        self.pattern_entry.set_hexpand(True)
        controls_grid.attach(self.pattern_entry, 1, 2, 1, 1)
        
        # Regex checkbox
        self.regex_checkbox = Gtk.CheckButton()
        self.regex_checkbox.set_label("Use Regular Expression")
        self.regex_checkbox.set_tooltip_text("Enable regex pattern matching")
        controls_grid.attach(self.regex_checkbox, 0, 3, 2, 1)
        
        # Add filter button
        add_button = Gtk.Button(label="Add Filter Rule")
        add_button.set_halign(Gtk.Align.END)
        add_button.connect('clicked', self._on_add_filter_clicked)
        controls_grid.attach(add_button, 1, 4, 1, 1)
        
        # Connect Enter key to add filter
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.pattern_entry.add_controller(key_controller)
    
    def _create_preview_section(self, parent):
        """Create preview section"""
        # Header with title and stats
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_bottom(5)
        parent.append(header_box)
        
        preview_title = Gtk.Label()
        preview_title.set_markup("<b>Preview Results</b>")
        preview_title.set_halign(Gtk.Align.START)
        preview_title.set_hexpand(True)
        header_box.append(preview_title)
        
        # Results count
        self.results_label = Gtk.Label()
        self.results_label.set_markup("<b>0 files</b>")
        self.results_label.set_halign(Gtk.Align.END)
        header_box.append(self.results_label)
        
        # Search info label
        self.search_info_label = Gtk.Label()
        self.search_info_label.set_markup("<i>No filters applied</i>")
        self.search_info_label.set_halign(Gtk.Align.START)
        self.search_info_label.set_margin_bottom(5)
        self.search_info_label.add_css_class("dim-label")
        parent.append(self.search_info_label)
        
        # Preview list with enhanced display
        preview_scrolled = Gtk.ScrolledWindow()
        preview_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        preview_scrolled.set_vexpand(True)
        preview_scrolled.set_hexpand(True)
        parent.append(preview_scrolled)
        
        self.preview_list = Gtk.ListBox()
        self.preview_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.preview_list.add_css_class("boxed-list")
        preview_scrolled.set_child(self.preview_list)
        
        # Add stats summary at bottom
        self.stats_label = Gtk.Label()
        self.stats_label.set_markup("<small>No files to display</small>")
        self.stats_label.set_halign(Gtk.Align.CENTER)
        self.stats_label.set_margin_top(5)
        self.stats_label.add_css_class("dim-label")
        parent.append(self.stats_label)
    
    def _create_buttons(self, parent):
        """Create bottom buttons"""
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(10)
        parent.append(button_box)
        
        # Clear all button
        clear_button = Gtk.Button(label="Clear All")
        clear_button.connect('clicked', self._on_clear_clicked)
        button_box.append(clear_button)
        
        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect('clicked', self._on_cancel_clicked)
        button_box.append(cancel_button)
        
        # Apply button
        apply_button = Gtk.Button(label="Apply")
        apply_button.add_css_class("suggested-action")
        apply_button.connect('clicked', self._on_apply_clicked)
        button_box.append(apply_button)
    
    def _setup_css(self):
        """Setup CSS styling"""
        css_provider = Gtk.CssProvider()
        css = """
        .filter-rule-row {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin: 2px;
        }
        
        .filter-rule-row:hover {
            background-color: #f5f5f5;
        }
        
        .preview-item {
            padding: 2px 4px;
            font-family: monospace;
            font-size: 11px;
        }
        
        .preview-item-confirmed {
            color: #22c55e;
            font-weight: bold;
        }
        
        .preview-item-valid {
            color: #10b981;
        }
        
        .preview-item-error {
            color: #ef4444;
        }
        
        .preview-item-warning {
            color: #f59e0b;
        }
        
        .preview-item-extension {
            color: #6b7280;
            font-size: 9px;
            font-weight: bold;
            padding: 2px 4px;
            border-radius: 2px;
            background-color: #f3f4f6;
        }
        """
        css_provider.load_from_string(css)
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def _on_sort_changed(self, combo, param):
        """Handle sort option change"""
        selected_idx = combo.get_selected()
        if selected_idx != Gtk.INVALID_LIST_POSITION:
            model = combo.get_model()
            display_name = model.get_string(selected_idx)
            self.current_sort = self.sort_option_mapping.get(display_name, SortOption.FILENAME_ASC)
            self._apply_filters()
    
    def _on_add_filter_clicked(self, button):
        """Handle add filter button click"""
        self._add_filter_rule()
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press in pattern entry"""
        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            self._add_filter_rule()
            return True
        return False
    
    def _add_filter_rule(self):
        """Add a new filter rule"""
        pattern = self.pattern_entry.get_text().strip()
        if not pattern:
            return
        
        # Get selected category
        category_idx = self.category_combo.get_selected()
        if category_idx == Gtk.INVALID_LIST_POSITION:
            return
        
        category_model = self.category_combo.get_model()
        category_display = category_model.get_string(category_idx)
        category = self.category_mapping.get(category_display, FilterCategory.FILENAME)
        
        # Get selected type
        type_idx = self.type_combo.get_selected()
        filter_type = FilterType.INCLUDE if type_idx == 0 else FilterType.EXCLUDE
        
        # Get regex setting
        regex_enabled = self.regex_checkbox.get_active()
        
        # Create filter rule
        rule = FilterRule(category, filter_type, pattern, regex_enabled)
        
        # Validate regex if enabled
        if regex_enabled and not rule.compiled_regex:
            self._show_error("Invalid regular expression pattern")
            return
        
        # Add to rules list
        self.filter_rules.append(rule)
        self._update_rules_display()
        
        # Clear entry
        self.pattern_entry.set_text("")
        
        # Apply filters
        self._apply_filters()
    
    def _update_rules_display(self):
        """Update the display of filter rules"""
        # Clear existing rules
        child = self.rules_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.rules_list_box.remove(child)
            child = next_child
        
        # Add current rules
        for i, rule in enumerate(self.filter_rules):
            row = self._create_rule_row(rule, i)
            self.rules_list_box.append(row)
    
    def _create_rule_row(self, rule: FilterRule, index: int) -> Gtk.ListBoxRow:
        """Create a row for a filter rule"""
        row = Gtk.ListBoxRow()
        row.add_css_class("filter-rule-row")
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(5)
        box.set_margin_end(5)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        row.set_child(box)
        
        # Rule description
        type_text = "Include" if rule.filter_type == FilterType.INCLUDE else "Exclude"
        category_text = rule.category.value.title()
        pattern_text = rule.pattern
        regex_text = " (regex)" if rule.regex_enabled else ""
        
        rule_label = Gtk.Label()
        rule_label.set_markup(f"<b>{type_text}</b> {category_text}: <tt>{pattern_text}</tt>{regex_text}")
        rule_label.set_halign(Gtk.Align.START)
        rule_label.set_hexpand(True)
        box.append(rule_label)
        
        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name("edit-delete-symbolic")
        remove_button.set_tooltip_text("Remove this filter rule")
        remove_button.connect('clicked', lambda btn: self._remove_filter_rule(index))
        box.append(remove_button)
        
        return row
    
    def _remove_filter_rule(self, index: int):
        """Remove a filter rule"""
        if 0 <= index < len(self.filter_rules):
            del self.filter_rules[index]
            self._update_rules_display()
            self._apply_filters()
    
    def _apply_filters(self):
        """Apply current filters and update preview"""
        filtered_files = self.file_list_data.copy()
        
        # Apply filter rules
        for rule in self.filter_rules:
            if rule.filter_type == FilterType.INCLUDE:
                filtered_files = [f for f in filtered_files if rule.matches(f)]
            else:  # EXCLUDE
                filtered_files = [f for f in filtered_files if not rule.matches(f)]
        
        # Apply sorting
        filtered_files = self._sort_files(filtered_files)
        
        # Update preview with enhanced info
        self._update_preview(filtered_files)
        self._update_search_info()
        
        # Store current results
        self.filtered_results = filtered_files
    
    def _sort_files(self, files: List[Dict]) -> List[Dict]:
        """Sort files based on current sort option"""
        if self.current_sort == SortOption.FILENAME_ASC:
            return sorted(files, key=lambda f: f.get('name', '').lower())
        elif self.current_sort == SortOption.FILENAME_DESC:
            return sorted(files, key=lambda f: f.get('name', '').lower(), reverse=True)
        elif self.current_sort == SortOption.STATUS_ASC:
            return sorted(files, key=lambda f: f.get('status', '').lower())
        elif self.current_sort == SortOption.STATUS_DESC:
            return sorted(files, key=lambda f: f.get('status', '').lower(), reverse=True)
        elif self.current_sort == SortOption.CONFIRMATION_ASC:
            return sorted(files, key=lambda f: f.get('confirmed', False))
        elif self.current_sort == SortOption.CONFIRMATION_DESC:
            return sorted(files, key=lambda f: f.get('confirmed', False), reverse=True)
        elif self.current_sort == SortOption.VALIDATION_ASC:
            return sorted(files, key=lambda f: f.get('validation_status', '').lower())
        elif self.current_sort == SortOption.VALIDATION_DESC:
            return sorted(files, key=lambda f: f.get('validation_status', '').lower(), reverse=True)
        
        return files
    
    def _update_preview(self, files: List[Dict]):
        """Update preview list"""
        # Clear existing items
        child = self.preview_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.preview_list.remove(child)
            child = next_child
        
        # Update count
        self.results_label.set_markup(f"<b>{len(files)} files</b>")
        
        # Add preview items
        for file_info in files:
            row = self._create_preview_row(file_info)
            self.preview_list.append(row)
        
        # Update stats summary
        self._update_stats_summary(files)
    
    def _update_search_info(self):
        """Update search info label"""
        if not self.filter_rules:
            self.search_info_label.set_markup("<i>No filters applied - showing all files</i>")
        else:
            rule_count = len(self.filter_rules)
            sort_text = self.current_sort.value.replace('_', ' ').title()
            self.search_info_label.set_markup(f"<i>{rule_count} filter rule{'s' if rule_count != 1 else ''} applied, sorted by {sort_text}</i>")
    
    def _update_stats_summary(self, files: List[Dict]):
        """Update stats summary at bottom"""
        if not files:
            self.stats_label.set_markup("<small>No files match the current filters</small>")
            return
        
        # Count by status
        confirmed = sum(1 for f in files if f.get('confirmed', False))
        valid = sum(1 for f in files if f.get('validation_status') == 'valid')
        invalid = sum(1 for f in files if f.get('validation_status') in ['invalid_regex', 'missing_classes'])
        no_dat = sum(1 for f in files if f.get('validation_status') == 'no_dat')
        
        stats_text = f"<small>Confirmed: {confirmed} | Valid: {valid} | Invalid: {invalid} | No DAT: {no_dat}</small>"
        self.stats_label.set_markup(stats_text)
    
    def _create_preview_row(self, file_info: Dict) -> Gtk.ListBoxRow:
        """Create a preview row for a file"""
        row = Gtk.ListBoxRow()
        
        # Create horizontal box for better layout
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_start(8)
        hbox.set_margin_end(8)
        hbox.set_margin_top(4)
        hbox.set_margin_bottom(4)
        
        # File name
        name_label = Gtk.Label()
        name_label.set_text(file_info.get('name', ''))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_label.add_css_class("preview-item")
        hbox.append(name_label)
        
        # Status indicators
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        # Confirmation status
        if file_info.get('confirmed', False):
            confirm_label = Gtk.Label()
            confirm_label.set_text("✓")
            confirm_label.set_tooltip_text("Confirmed")
            confirm_label.add_css_class("preview-item-confirmed")
            status_box.append(confirm_label)
        
        # Validation status
        validation_status = file_info.get('validation_status', '')
        if validation_status == 'valid':
            valid_label = Gtk.Label()
            valid_label.set_text("✓")
            valid_label.set_tooltip_text("Valid")
            valid_label.add_css_class("preview-item-valid")
            status_box.append(valid_label)
        elif validation_status in ['invalid_regex', 'missing_classes']:
            error_label = Gtk.Label()
            error_label.set_text("✗")
            error_label.set_tooltip_text("Invalid")
            error_label.add_css_class("preview-item-error")
            status_box.append(error_label)
        elif validation_status == 'no_dat':
            no_dat_label = Gtk.Label()
            no_dat_label.set_text("⚠")
            no_dat_label.set_tooltip_text("No DAT file")
            no_dat_label.add_css_class("preview-item-warning")
            status_box.append(no_dat_label)
        
        # File extension
        ext_label = Gtk.Label()
        filename = file_info.get('name', '')
        ext = filename.split('.')[-1].upper() if '.' in filename else ''
        ext_label.set_text(ext)
        ext_label.set_tooltip_text(f"File extension: {ext}")
        ext_label.add_css_class("preview-item-extension")
        status_box.append(ext_label)
        
        hbox.append(status_box)
        
        # Add status-based styling to the row
        if file_info.get('confirmed', False):
            name_label.add_css_class("preview-item-confirmed")
        elif file_info.get('validation_status', '') == 'valid':
            name_label.add_css_class("preview-item-valid")
        elif file_info.get('validation_status', '') in ['invalid_regex', 'missing_classes']:
            name_label.add_css_class("preview-item-error")
        
        row.set_child(hbox)
        return row
    
    def _on_clear_clicked(self, button):
        """Handle clear all button click"""
        self.filter_rules.clear()
        self.current_sort = SortOption.FILENAME_ASC
        self.sort_combo.set_selected(0)
        self._update_rules_display()
        self._apply_filters()
    
    def _on_cancel_clicked(self, button):
        """Handle cancel button click"""
        self.close()
    
    def _on_apply_clicked(self, button):
        """Handle apply button click"""
        if hasattr(self, 'filtered_results'):
            self.on_filter_applied(self.filtered_results)
        self.close()
    
    def _show_error(self, message: str):
        """Show error message"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.connect('response', lambda d, r: d.destroy())
        dialog.show()