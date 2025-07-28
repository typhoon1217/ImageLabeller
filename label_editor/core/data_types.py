#!/usr/bin/env python3

from typing import Optional


class BoundingBox:
    def __init__(self, x: int, y: int, width: int, height: int, class_id: int, ocr_text: str = "", class_name: str = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.class_id = class_id
        self.ocr_text = ocr_text
        self.selected = False
        self.name = class_name if class_name is not None else f"class_{class_id}"

    def contains_point(self, x: int, y: int) -> bool:
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)

    def get_resize_handle(self, x: int, y: int, handle_size: int = 8) -> Optional[str]:
        if (abs(x - self.x) <= handle_size and abs(y - self.y) <= handle_size):
            return "nw"
        elif (abs(x - (self.x + self.width)) <= handle_size and abs(y - self.y) <= handle_size):
            return "ne"
        elif (abs(x - self.x) <= handle_size and abs(y - (self.y + self.height)) <= handle_size):
            return "sw"
        elif (abs(x - (self.x + self.width)) <= handle_size and abs(y - (self.y + self.height)) <= handle_size):
            return "se"
        elif (abs(x - self.x) <= handle_size and self.y <= y <= self.y + self.height):
            return "w"
        elif (abs(x - (self.x + self.width)) <= handle_size and self.y <= y <= self.y + self.height):
            return "e"
        elif (abs(y - self.y) <= handle_size and self.x <= x <= self.x + self.width):
            return "n"
        elif (abs(y - (self.y + self.height)) <= handle_size and self.x <= x <= self.x + self.width):
            return "s"
        return None
