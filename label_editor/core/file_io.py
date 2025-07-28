#!/usr/bin/env python3

from typing import List
from .data_types import BoundingBox


class DATParser:
    @staticmethod
    def parse_dat_file(file_path: str) -> List[BoundingBox]:
        boxes = []
        try:
            with open(file_path, 'r', encoding='ascii') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(' ', 1)
                    if len(parts) < 2:
                        parts = line.split('\t', 1)

                    if len(parts) >= 2:
                        class_id = int(parts[0])
                        coords_text = parts[1]

                        ocr_text = ""
                        if '#' in coords_text:
                            coord_part, ocr_text = coords_text.split('#', 1)
                        else:
                            coord_part = coords_text

                        coords = coord_part.strip().split()
                        if len(coords) >= 4:
                            try:
                                x = int(float(coords[0]))
                                y = int(float(coords[1]))
                                width = int(float(coords[2]))
                                height = int(float(coords[3]))
                                boxes.append(BoundingBox(
                                    x, y, width, height, class_id, ocr_text))
                            except (ValueError, IndexError) as e:
                                print(f"Skipping invalid coordinate line: {coord_part.strip()}")
                                continue
        except Exception as e:
            print(f"Parse error: {e}")

        return boxes

    @staticmethod
    def save_dat_file(file_path: str, boxes: List[BoundingBox]):
        try:
            with open(file_path, 'wb') as f:
                lines = []
                for box in sorted(boxes, key=lambda b: b.class_id):
                    ocr_text = box.ocr_text
                    ocr_text = ocr_text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\ufb02', "fl").replace('\ufb01', "fi")
                    ocr_text = ocr_text.encode(
                        'ascii', 'ignore').decode('ascii')

                    line = f"{box.class_id} {box.x} {box.y} {box.width} {box.height} #{ocr_text}"
                    lines.append(line)
                content = '\r\n'.join(lines)
                f.write(content.encode('ascii'))
        except Exception as e:
            print(f"Save error: {e}")
