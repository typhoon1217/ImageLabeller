#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from label_editor.ui.main_window import LabelEditorWindow


class LabelEditorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.labeleditor")

    def do_activate(self):
        window = LabelEditorWindow(self)
        window.present()


def main():
    app = LabelEditorApp()
    app.run()


if __name__ == "__main__":
    main()