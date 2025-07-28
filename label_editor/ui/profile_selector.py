#!/usr/bin/env python3
"""
Profile selector dialog for the settings manager
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from typing import Optional, Callable


class ProfileSelectorDialog(Gtk.Dialog):
    """Dialog for selecting and managing settings profiles"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(title="Settings Profile Manager", transient_for=parent)
        self.settings_manager = settings_manager
        self.selected_profile = None
        
        # Set dialog properties
        self.set_default_size(600, 400)
        self.set_modal(True)
        
        # Add buttons
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Load Profile", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        
        # Create content
        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_area.append(main_box)
        
        # Current profile label
        current_profile = self.settings_manager.active_profile or "Base Settings"
        self.current_label = Gtk.Label(label=f"Current Profile: {current_profile}")
        self.current_label.set_halign(Gtk.Align.START)
        self.current_label.add_css_class("heading")
        main_box.append(self.current_label)
        
        # Profile list
        list_frame = Gtk.Frame()
        main_box.append(list_frame)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        list_frame.set_child(scrolled)
        
        # Create list model and view
        self.list_store = Gtk.ListStore(str, str, str)  # name, description, status
        self.tree_view = Gtk.TreeView(model=self.list_store)
        self.tree_view.set_headers_visible(True)
        scrolled.set_child(self.tree_view)
        
        # Add columns
        renderer_text = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Profile Name", renderer_text, text=0)
        column_name.set_expand(True)
        self.tree_view.append_column(column_name)
        
        renderer_desc = Gtk.CellRendererText()
        column_desc = Gtk.TreeViewColumn("Description", renderer_desc, text=1)
        column_desc.set_expand(True)
        self.tree_view.append_column(column_desc)
        
        renderer_status = Gtk.CellRendererText()
        column_status = Gtk.TreeViewColumn("Status", renderer_status, text=2)
        self.tree_view.append_column(column_status)
        
        # Selection handling
        selection = self.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        selection.connect("changed", self.on_selection_changed)
        
        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        main_box.append(button_box)
        
        # Add profile management buttons
        self.new_button = Gtk.Button(label="New Profile")
        self.new_button.connect("clicked", self.on_new_profile)
        button_box.append(self.new_button)
        
        self.duplicate_button = Gtk.Button(label="Duplicate")
        self.duplicate_button.connect("clicked", self.on_duplicate_profile)
        self.duplicate_button.set_sensitive(False)
        button_box.append(self.duplicate_button)
        
        self.delete_button = Gtk.Button(label="Delete")
        self.delete_button.connect("clicked", self.on_delete_profile)
        self.delete_button.set_sensitive(False)
        button_box.append(self.delete_button)
        
        self.import_button = Gtk.Button(label="Import")
        self.import_button.connect("clicked", self.on_import_profile)
        button_box.append(self.import_button)
        
        self.export_button = Gtk.Button(label="Export")
        self.export_button.connect("clicked", self.on_export_profile)
        self.export_button.set_sensitive(False)
        button_box.append(self.export_button)
        
        # Load profiles
        self.refresh_profile_list()
    
    def refresh_profile_list(self):
        """Refresh the list of available profiles"""
        self.list_store.clear()
        
        # Add base settings option
        status = "Active" if self.settings_manager.active_profile is None else ""
        self.list_store.append(["Base Settings", "Default application settings", status])
        
        # Add all profiles
        profiles = self.settings_manager.list_profiles()
        for profile_name in profiles:
            description = self.get_profile_description(profile_name)
            status = "Active" if profile_name == self.settings_manager.active_profile else ""
            self.list_store.append([profile_name, description, status])
    
    def get_profile_description(self, profile_name: str) -> str:
        """Get a description for a profile based on its contents"""
        descriptions = {
            "passport": "Passport MRZ scanning configuration",
            "document_ocr": "General document OCR with layout detection",
            "invoice_processing": "Invoice field extraction and validation",
            "minimal": "Minimal UI with basic features",
            "default": "Custom user configuration"
        }
        return descriptions.get(profile_name, "Custom profile")
    
    def on_selection_changed(self, selection):
        """Handle selection changes"""
        model, iter = selection.get_selected()
        if iter:
            profile_name = model.get_value(iter, 0)
            self.selected_profile = profile_name if profile_name != "Base Settings" else None
            
            # Update button states
            is_custom = profile_name not in ["Base Settings"]
            self.duplicate_button.set_sensitive(True)
            self.delete_button.set_sensitive(is_custom)
            self.export_button.set_sensitive(is_custom)
    
    def on_new_profile(self, button):
        """Create a new profile"""
        dialog = Gtk.Dialog(title="New Profile", transient_for=self)
        dialog.set_default_size(400, 150)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Create", Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        
        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)
        content.append(grid)
        
        label = Gtk.Label(label="Profile Name:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, 0, 1, 1)
        
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        grid.attach(entry, 1, 0, 1, 1)
        
        label2 = Gtk.Label(label="Base on:")
        label2.set_halign(Gtk.Align.END)
        grid.attach(label2, 0, 1, 1, 1)
        
        combo = Gtk.ComboBoxText()
        combo.append_text("Empty (Base Settings)")
        if self.selected_profile:
            combo.append_text(f"Current ({self.selected_profile})")
        for profile in self.settings_manager.list_profiles():
            combo.append_text(profile)
        combo.set_active(0)
        grid.attach(combo, 1, 1, 1, 1)
        
        dialog.show()
        
        if dialog.run() == Gtk.ResponseType.OK:
            profile_name = entry.get_text().strip()
            if profile_name:
                base_on = combo.get_active_text()
                if base_on == "Empty (Base Settings)":
                    base_on = None
                elif base_on and base_on.startswith("Current"):
                    base_on = self.selected_profile
                
                if self.settings_manager.create_profile(profile_name, base_on):
                    self.refresh_profile_list()
                else:
                    self.show_error("Failed to create profile")
        
        dialog.destroy()
    
    def on_duplicate_profile(self, button):
        """Duplicate selected profile"""
        if not self.selected_profile:
            return
        
        dialog = Gtk.Dialog(title="Duplicate Profile", transient_for=self)
        dialog.set_default_size(400, 100)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Duplicate", Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.append(box)
        
        label = Gtk.Label(label="New Name:")
        box.append(label)
        
        entry = Gtk.Entry()
        entry.set_text(f"{self.selected_profile}_copy")
        entry.set_hexpand(True)
        box.append(entry)
        
        dialog.show()
        
        if dialog.run() == Gtk.ResponseType.OK:
            new_name = entry.get_text().strip()
            if new_name:
                if self.settings_manager.create_profile(new_name, self.selected_profile):
                    self.refresh_profile_list()
                else:
                    self.show_error("Failed to duplicate profile")
        
        dialog.destroy()
    
    def on_delete_profile(self, button):
        """Delete selected profile"""
        if not self.selected_profile:
            return
        
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete profile '{self.selected_profile}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            if self.settings_manager.delete_profile(self.selected_profile):
                self.refresh_profile_list()
            else:
                self.show_error("Failed to delete profile")
    
    def on_import_profile(self, button):
        """Import profile from file"""
        dialog = Gtk.FileChooserDialog(
            title="Import Profile",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Import", Gtk.ResponseType.OK)
        
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files")
        filter_json.add_mime_type("application/json")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        
        if dialog.run() == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            if file_path:
                if self.settings_manager.import_profile(file_path):
                    self.refresh_profile_list()
                else:
                    self.show_error("Failed to import profile")
        
        dialog.destroy()
    
    def on_export_profile(self, button):
        """Export profile to file"""
        if not self.selected_profile:
            return
        
        dialog = Gtk.FileChooserDialog(
            title="Export Profile",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Export", Gtk.ResponseType.OK)
        
        dialog.set_current_name(f"{self.selected_profile}_profile.json")
        
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files")
        filter_json.add_mime_type("application/json")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        
        if dialog.run() == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            if file_path:
                if self.settings_manager.export_profile(self.selected_profile, file_path):
                    self.show_info("Profile exported successfully")
                else:
                    self.show_error("Failed to export profile")
        
        dialog.destroy()
    
    def show_error(self, message: str):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()
    
    def show_info(self, message: str):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()


def show_profile_selector(parent_window, settings_manager) -> Optional[str]:
    """
    Show profile selector dialog and return selected profile name
    
    Returns:
        Profile name if one was selected and loaded, None otherwise
    """
    dialog = ProfileSelectorDialog(parent_window, settings_manager)
    dialog.present()
    
    # GTK4 pattern - use response signal
    result = None
    
    def on_response(dialog, response_id):
        nonlocal result
        selected_profile = dialog.selected_profile
        
        if response_id == Gtk.ResponseType.OK and selected_profile is not None:
            # Load the selected profile
            if selected_profile == "Base Settings":
                settings_manager.reset_to_base()
                result = "Base Settings"
            elif settings_manager.load_profile(selected_profile):
                result = selected_profile
        
        dialog.destroy()
    
    dialog.connect("response", on_response)
    
    # Run the main loop until dialog is closed
    while dialog.get_visible():
        dialog.get_display().sync()
        
    return result
