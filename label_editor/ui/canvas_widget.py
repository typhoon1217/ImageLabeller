#!/usr/bin/env python3

from typing import List, Tuple, Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf
from ..core.data_types import BoundingBox


class ImageCanvas(Gtk.DrawingArea):
    def __init__(self, class_config=None):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_can_focus(True)
        
        # Force cairo rendering for stability
        try:
            # Disable GL rendering on this widget
            self.set_name("software-rendered-canvas")
        except:
            pass

        self.class_config = class_config

        self.pixbuf = None
        self.boxes = []
        self.selected_box = None
        self.scale_factor = 1.0
        self.base_scale_factor = 1.0  # For fit-to-window
        self.zoom_level = 1.0  # User zoom multiplier
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.panning = False

        self.dragging = False
        self.resizing = False
        self.resize_handle = None
        self.creating_box = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.box_start_x = 0
        self.box_start_y = 0
        self.box_start_width = 0
        self.box_start_height = 0

        self.set_draw_func(self.on_draw)

        self.click_controller = Gtk.GestureClick()
        self.click_controller.connect('pressed', self.on_click_pressed)
        self.click_controller.connect('released', self.on_click_released)
        self.add_controller(self.click_controller)

        self.motion_controller = Gtk.EventControllerMotion()
        self.motion_controller.connect('motion', self.on_motion)
        self.add_controller(self.motion_controller)

        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.connect('key-pressed', self.on_key_pressed)
        self.add_controller(self.key_controller)

        self.scroll_controller = Gtk.EventControllerScroll()
        self.scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL)
        self.scroll_controller.connect('scroll', self.on_scroll)
        self.add_controller(self.scroll_controller)

        self.on_box_selected = None
        self.on_boxes_changed = None
        self.is_text_editing_active = None  # Callback to check if text editing is active

    def get_class_by_id(self, class_id):
        for cls in self.class_config["classes"]:
            if cls["id"] == class_id:
                return cls
        return None

    def get_class_color(self, class_id):
        cls = self.get_class_by_id(class_id)
        return cls["color"] if cls else [0.5, 0.5, 0.5]  # Default gray

    def get_class_name(self, class_id):
        cls = self.get_class_by_id(class_id)
        return cls["name"] if cls else f"class_{class_id}"

    def load_image(self, file_path: str):
        try:
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
            self.fit_image()
            self.queue_draw()
        except Exception as e:
            print(f"Load error: {e}")

    def fit_image(self):
        if not self.pixbuf:
            return

        canvas_width = self.get_width()
        canvas_height = self.get_height()

        if canvas_width <= 0 or canvas_height <= 0:
            return

        img_width = self.pixbuf.get_width()
        img_height = self.pixbuf.get_height()

        scale_x = canvas_width / img_width
        scale_y = canvas_height / img_height
        self.base_scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up

        self.scale_factor = self.base_scale_factor * self.zoom_level

        scaled_width = img_width * self.scale_factor
        scaled_height = img_height * self.scale_factor
        self.offset_x = (canvas_width - scaled_width) / 2
        self.offset_y = (canvas_height - scaled_height) / 2

    def zoom_in(self):
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)  # Max 5x zoom
        self.fit_image()
        self.queue_draw()

    def zoom_out(self):
        self.zoom_level = max(self.zoom_level / 1.25, 0.1)  # Min 0.1x zoom
        self.fit_image()
        self.queue_draw()

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.fit_image()
        self.queue_draw()

    def image_to_canvas(self, x: int, y: int) -> Tuple[int, int]:
        canvas_x = x * self.scale_factor + self.offset_x
        canvas_y = y * self.scale_factor + self.offset_y
        return int(canvas_x), int(canvas_y)

    def canvas_to_image(self, x: int, y: int) -> Tuple[int, int]:
        img_x = (x - self.offset_x) / self.scale_factor
        img_y = (y - self.offset_y) / self.scale_factor
        return int(img_x), int(img_y)

    def set_boxes(self, boxes: List[BoundingBox]):
        self.boxes = boxes
        for box in self.boxes:
            box.name = self.get_class_name(box.class_id)
        self.selected_box = None
        self.queue_draw()

    def on_draw(self, area, cr, width, height, user_data=None):
        try:
            cr.set_source_rgb(0.2, 0.2, 0.2)
            cr.paint()

            if not self.pixbuf:
                return

            scaled_width = self.pixbuf.get_width() * self.scale_factor
            scaled_height = self.pixbuf.get_height() * self.scale_factor

            cr.save()
            cr.translate(self.offset_x, self.offset_y)
            cr.scale(self.scale_factor, self.scale_factor)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
            cr.restore()
        except Exception as e:
            print(f"Draw error (image): {e}")
            cr.restore()
            return

        try:
            for box in self.boxes:
                canvas_x, canvas_y = self.image_to_canvas(box.x, box.y)
                canvas_width = box.width * self.scale_factor
                canvas_height = box.height * self.scale_factor

                if box.selected:
                    cr.set_source_rgba(1.0, 0.0, 0.0, 0.3)  # Red for selected
                    cr.set_line_width(3.0)
                else:
                    color = self.get_class_color(box.class_id)
                    cr.set_source_rgba(color[0], color[1], color[2], 0.3)
                    cr.set_line_width(2.0)

                cr.rectangle(canvas_x, canvas_y, canvas_width, canvas_height)
                cr.stroke()

                show_labels = True
                if self.is_text_editing_active and callable(self.is_text_editing_active):
                    show_labels = not self.is_text_editing_active()

                if show_labels:
                    cr.set_source_rgb(1.0, 1.0, 1.0)
                    cr.select_font_face("Sans", 0, 0)
                    cr.set_font_size(11)

                ocr_display = box.ocr_text[:30] + "..." if len(box.ocr_text) > 30 else box.ocr_text
                label_text = f"{box.name}: {ocr_display}"

                text_extents = cr.text_extents(label_text)
                text_width = text_extents.width + 4
                text_height = text_extents.height + 4

                label_x = canvas_x
                label_y = canvas_y - text_height - 2

                if label_y < 0:
                    label_y = canvas_y + canvas_height + text_height + 2

                cr.set_source_rgba(0.0, 0.0, 0.0, 0.3)
                cr.rectangle(label_x, label_y, text_width, text_height)
                cr.fill()

                cr.set_source_rgb(1.0, 1.0, 1.0)  # White text
                cr.move_to(label_x + 2, label_y + text_height - 2)
                cr.show_text(label_text)

                if box.selected:
                    handle_size = 6
                    cr.set_source_rgb(1.0, 1.0, 0.0)  # Yellow handles

                    handles = [
                        (canvas_x, canvas_y),  # nw
                        (canvas_x + canvas_width, canvas_y),  # ne
                        (canvas_x, canvas_y + canvas_height),  # sw
                        (canvas_x + canvas_width, canvas_y + canvas_height),  # se
                        (canvas_x + canvas_width/2, canvas_y),  # n
                        (canvas_x + canvas_width/2, canvas_y + canvas_height),  # s
                        (canvas_x, canvas_y + canvas_height/2),  # w
                        (canvas_x + canvas_width, canvas_y + canvas_height/2),  # e
                    ]

                    for hx, hy in handles:
                        cr.rectangle(hx - handle_size/2, hy -
                                     handle_size/2, handle_size, handle_size)
                        cr.fill()
        except Exception as e:
            print(f"Draw error (boxes): {e}")

    def on_click_pressed(self, gesture, n_press, x, y):
        self.grab_focus()

        if not self.pixbuf:
            return

        if gesture.get_current_button() == 2:  # Middle mouse button
            self.panning = True
            self.pan_start_x = x
            self.pan_start_y = y
            return

        img_x, img_y = self.canvas_to_image(x, y)

        if self.selected_box:
            canvas_x, canvas_y = self.image_to_canvas(
                self.selected_box.x, self.selected_box.y)
            canvas_width = self.selected_box.width * self.scale_factor
            canvas_height = self.selected_box.height * self.scale_factor

            temp_box = BoundingBox(
                canvas_x, canvas_y, canvas_width, canvas_height, 0)
            handle = temp_box.get_resize_handle(x, y, 8)

            if handle:
                self.resizing = True
                self.resize_handle = handle
                self.drag_start_x = x
                self.drag_start_y = y
                self.box_start_x = self.selected_box.x
                self.box_start_y = self.selected_box.y
                self.box_start_width = self.selected_box.width
                self.box_start_height = self.selected_box.height
                return

        clicked_box = None
        for box in self.boxes:
            if box.contains_point(img_x, img_y):
                clicked_box = box
                break

        if clicked_box:
            if self.selected_box:
                self.selected_box.selected = False
            clicked_box.selected = True
            self.selected_box = clicked_box

            self.dragging = True
            self.drag_start_x = x
            self.drag_start_y = y
            self.box_start_x = clicked_box.x
            self.box_start_y = clicked_box.y

            if self.on_box_selected:
                self.on_box_selected(clicked_box)
        else:
            self.creating_box = True
            self.drag_start_x = x
            self.drag_start_y = y

            if self.selected_box:
                self.selected_box.selected = False
                self.selected_box = None
                if self.on_box_selected:
                    self.on_box_selected(None)

        self.queue_draw()

    def on_click_released(self, gesture, n_press, x, y):
        self.panning = False

        if self.creating_box:
            start_img_x, start_img_y = self.canvas_to_image(
                self.drag_start_x, self.drag_start_y)
            end_img_x, end_img_y = self.canvas_to_image(x, y)

            if abs(end_img_x - start_img_x) > 10 and abs(end_img_y - start_img_y) > 10:
                box_x = min(start_img_x, end_img_x)
                box_y = min(start_img_y, end_img_y)
                box_width = abs(end_img_x - start_img_x)
                box_height = abs(end_img_y - start_img_y)

                available_classes = [cls["id"]
                                     for cls in self.class_config["classes"]]
                used_classes = [b.class_id for b in self.boxes]

                class_id = available_classes[0]  # Default to first class
                for cls_id in available_classes:
                    if cls_id not in used_classes:
                        class_id = cls_id
                        break

                class_name = self.get_class_name(class_id)
                new_box = BoundingBox(
                    box_x, box_y, box_width, box_height, class_id, "", class_name)
                new_box.selected = True

                if self.selected_box:
                    self.selected_box.selected = False

                self.boxes.append(new_box)
                self.selected_box = new_box

                if self.on_box_selected:
                    self.on_box_selected(new_box)
                if self.on_boxes_changed:
                    self.on_boxes_changed()

        self.creating_box = False
        self.dragging = False
        self.resizing = False
        self.resize_handle = None
        self.queue_draw()

    def on_motion(self, controller, x, y):
        if self.panning:
            dx = x - self.pan_start_x
            dy = y - self.pan_start_y
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start_x = x
            self.pan_start_y = y
            self.queue_draw()
            return

        if self.dragging and self.selected_box:
            dx = (x - self.drag_start_x) / self.scale_factor
            dy = (y - self.drag_start_y) / self.scale_factor

            self.selected_box.x = max(0, self.box_start_x + dx)
            self.selected_box.y = max(0, self.box_start_y + dy)

            if self.on_boxes_changed:
                self.on_boxes_changed()
            self.queue_draw()

        elif self.resizing and self.selected_box:
            dx = (x - self.drag_start_x) / self.scale_factor
            dy = (y - self.drag_start_y) / self.scale_factor

            if self.resize_handle == "nw":
                self.selected_box.x = self.box_start_x + dx
                self.selected_box.y = self.box_start_y + dy
                self.selected_box.width = self.box_start_width - dx
                self.selected_box.height = self.box_start_height - dy
            elif self.resize_handle == "ne":
                self.selected_box.y = self.box_start_y + dy
                self.selected_box.width = self.box_start_width + dx
                self.selected_box.height = self.box_start_height - dy
            elif self.resize_handle == "sw":
                self.selected_box.x = self.box_start_x + dx
                self.selected_box.width = self.box_start_width - dx
                self.selected_box.height = self.box_start_height + dy
            elif self.resize_handle == "se":
                self.selected_box.width = self.box_start_width + dx
                self.selected_box.height = self.box_start_height + dy
            elif self.resize_handle == "n":
                self.selected_box.y = self.box_start_y + dy
                self.selected_box.height = self.box_start_height - dy
            elif self.resize_handle == "s":
                self.selected_box.height = self.box_start_height + dy
            elif self.resize_handle == "w":
                self.selected_box.x = self.box_start_x + dx
                self.selected_box.width = self.box_start_width - dx
            elif self.resize_handle == "e":
                self.selected_box.width = self.box_start_width + dx

            if self.selected_box.width < 10:
                self.selected_box.width = 10
            if self.selected_box.height < 10:
                self.selected_box.height = 10

            if self.on_boxes_changed:
                self.on_boxes_changed()
            self.queue_draw()

        elif self.creating_box:
            self.queue_draw()

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl_pressed = (state & Gdk.ModifierType.CONTROL_MASK) != 0

        if keyval == Gdk.KEY_Delete and self.selected_box:
            self.boxes.remove(self.selected_box)
            self.selected_box = None
            if self.on_box_selected:
                self.on_box_selected(None)
            if self.on_boxes_changed:
                self.on_boxes_changed()
            self.queue_draw()
            return True
        elif keyval == Gdk.KEY_plus or keyval == Gdk.KEY_equal:
            self.zoom_in()
            return True
        elif keyval == Gdk.KEY_minus:
            self.zoom_out()
            return True
        elif keyval == Gdk.KEY_0:
            self.reset_zoom()
            return True
        elif keyval == Gdk.KEY_Tab:
            if self.boxes:
                current_idx = -1
                if self.selected_box:
                    try:
                        current_idx = self.boxes.index(self.selected_box)
                    except ValueError:
                        pass

                next_idx = (current_idx + 1) % len(self.boxes)
                if self.selected_box:
                    self.selected_box.selected = False

                self.selected_box = self.boxes[next_idx]
                self.selected_box.selected = True

                if self.on_box_selected:
                    self.on_box_selected(self.selected_box)
                self.queue_draw()
            return True
        elif keyval == Gdk.KEY_Escape:
            if self.selected_box:
                self.selected_box.selected = False
                self.selected_box = None
                if self.on_box_selected:
                    self.on_box_selected(None)
                self.queue_draw()
            return True
        else:
            if self.selected_box:
                for cls in self.class_config["classes"]:
                    if keyval == getattr(Gdk, f'KEY_{cls["key"]}', None):
                        self.selected_box.class_id = cls["id"]
                        self.selected_box.name = cls["name"]
                        if self.on_boxes_changed:
                            self.on_boxes_changed()
                        self.queue_draw()
                        return True

        return False

    def on_scroll(self, controller, dx, dy):
        if dy < 0:  # Scroll up - zoom in
            self.zoom_in()
        elif dy > 0:  # Scroll down - zoom out
            self.zoom_out()
        return True