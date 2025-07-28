#!/usr/bin/env python3
"""
GTK4-compatible Profile selector dialog for the settings manager
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from typing import Optional, Callable


class ProfileSelectorDialog(Gtk.Dialog):
    """Dialog for selecting and managing settings profiles - GTK4 compatible"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(title="Settings Profile Manager", transient_for=parent, modal=True)
        self.settings_manager = settings_manager
        self.selected_profile = None
        
        # Set dialog properties
        self.set_default_size(600, 400)
        
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
            "default": "Custom user configuration",
            "vietnamese_nid_front": "Vietnamese National ID - Front Side",
            "vietnamese_nid_back": "Vietnamese National ID - Back Side (MRZ)"
        }
        return descriptions.get(profile_name, "Custom profile")
    
    def on_selection_changed(self, selection):
        """Handle selection changes"""
        model, iter = selection.get_selected()
        if iter:
            profile_name = model.get_value(iter, 0)
            self.selected_profile = profile_name if profile_name != "Base Settings" else None


def show_profile_selector(parent_window, settings_manager) -> Optional[str]:
    """
    Show profile selector dialog and return selected profile name
    
    Returns:
        Profile name if one was selected and loaded, None otherwise
    """
    dialog = ProfileSelectorDialog(parent_window, settings_manager)
    
    # GTK4 async pattern with callback
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
        
        dialog.close()
    
    dialog.connect("response", on_response)
    dialog.present()
    
    # Simple modal wait pattern for GTK4
    context = dialog.get_display().get_default_seat().get_display().get_default()
    while dialog.get_visible():
        context.iteration(False)
        
    return result
