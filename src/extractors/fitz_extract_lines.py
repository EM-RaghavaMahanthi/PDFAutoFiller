# src/extractors/fitz_extract_lines.py
import fitz
import re
from src.models.bounding_box import BoundingBox
from src.utils.logger import logger
from src.extractors.base import BaseExtractor
from src.utils.storage import save_json
from src.utils.timing import timing_decorator


class FitzExtractorLine(BaseExtractor):
    """Extracts text, form fields, and tables from PDFs with sorted Global/Page IDs."""

    def __init__(self, config: dict):
        self.WIDGET_LINE_DISTANCE_THRESHOLD = config.get("WIDGET_LINE_DISTANCE_THRESHOLD", 10)
        self.rounding = config.get("rounding", 1)
        self.global_id = 1
        self.global_fid = 1
        self.fid_to_gid_map = {}

    @timing_decorator
    def extract(self,pdf_path, storage_config: dict) -> dict:

        doc = fitz.open(pdf_path)
        logger.info(f"Starting extraction from PDF: {pdf_path}")
        extracted_data = {"pages": []}
        global_tid = 0

        for page_num, page in enumerate(doc, start=1):
            page_data = {
                "page_number": page_num,
                "text_elements": [],
                "form_fields": [],
                "tables": [],
                "table_cell_info": {}
            }

            elements = []
            words = page.get_text("words")
            widgets = {w.rect: w for w in page.widgets()}
            lines = {}
            line_map = {}

            page_gids = []
            page_fids = []

            for word in words:
                x0, y0, x1, y1, text, *_ = word
                line_key = (round(y0, self.rounding), round(y1, self.rounding))
                if line_key not in lines:
                    lines[line_key] = []
                if re.match(r"[._\u2026-]{2,}", text):
                    lines[line_key].append(("", (x0, y0, x1, y1), word[-1]))
                else:
                    lines[line_key].append((text, (x0, y0, x1, y1), word[-1]))

            sorted_line_keys = sorted(lines.keys(), key=lambda k: k[0])
            for line_key in sorted_line_keys:
                line_map[line_key] = self.global_id
                self.global_id += 1

            tables = page.find_tables()
            table_data = []
            for table in tables:
                table_info = {
                    "tid": global_tid, 
                    "bbox": list(table.bbox),
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                }
                table_data.append(table_info)
                global_tid += 1

            page_data["tables"] = table_data

            for rect, widget in widgets.items():
                fid = self.global_fid
                bbox = BoundingBox(l=rect.x0, t=rect.y0, r=rect.x1, b=rect.y1, rounding=self.rounding)
                field_type = widget.field_type
                field_flag = widget.field_flags
                field_value = widget.field_value
                field_type_str = {
                    5: "button",
                    7: "text",
                    2: "choice",
                    4: "signature"
                }.get(field_type, "unknown")

                assigned_table = None
                for table in table_data:
                    t_bbox = table["bbox"]
                    if bbox.l >= t_bbox[0] and bbox.r <= t_bbox[2] and bbox.t >= t_bbox[1] and bbox.b <= t_bbox[3]:
                        assigned_table = table["tid"]
                        break

                closest_line = None
                min_distance = float("inf")
                assigned_gid = None

                for (y0, y1), words in lines.items():
                    if words:
                        _, (_, line_y0, _, line_y1), _ = words[0]
                        distance = abs(rect.y1 - line_y1)
                        if distance < min_distance:
                            min_distance = distance
                            closest_line = (y0, y1)

                if closest_line and min_distance <= self.WIDGET_LINE_DISTANCE_THRESHOLD:
                    field_tag = (
                        "TABLE_CELL_FIELD" if assigned_table else
                        "CHOICE_FIELD" if field_type_str == "choice" else
                        "BUTTON_FIELD" if field_type_str == "button" else
                        "BLANK_FIELD"
                    )
                    lines[closest_line].append((f"[{field_tag}:{fid}]", (rect.x0, rect.y0, rect.x1, rect.y1), 9999))
                    assigned_gid = line_map[closest_line]
                else:
                    new_line_key = (round(rect.y0, self.rounding), round(rect.y1, self.rounding))
                    if new_line_key not in line_map:
                        line_map[new_line_key] = self.global_id
                        self.global_id += 1
                        lines[new_line_key] = []
                    field_tag = (
                        "TABLE_CELL_FIELD" if assigned_table else
                        "CHOICE_FIELD" if field_type_str == "choice" else
                        "BUTTON_FIELD" if field_type_str == "button" else
                        "BLANK_FIELD"
                    )
                    lines[new_line_key].append((f"[{field_tag}:{fid}]", (rect.x0, rect.y0, rect.x1, rect.y1), 0))
                    assigned_gid = line_map[new_line_key]

                self.fid_to_gid_map[fid] = assigned_gid

                form_field = {
                    "type_inferred": field_tag,
                    "field_type": field_type_str,
                    "field_flag": field_flag,
                    "bbox": bbox.to_dict(),
                    "fid": fid,
                    "page": page_num,
                    "field_name": widget.field_name if widget.field_name else None,
                    "field_value": field_value,
                    "gid": assigned_gid
                }
                elements.append(form_field)

                if assigned_table:
                    page_data["table_cell_info"][fid] = {"tid": assigned_table}

                page_fids.append(fid)
                page_gids.append(assigned_gid)
                self.global_fid += 1

            processed_lines = []
            page_pid = 1
            for (y0, y1) in sorted_line_keys:
                words = lines[(y0, y1)]
                sorted_words = sorted(words, key=lambda w: w[1][0])
                if not sorted_words:
                    continue

                full_text = " ".join([w[0] for w in sorted_words])
                bbox = BoundingBox(
                    l=min(w[1][0] for w in sorted_words),
                    t=y0,
                    r=max(w[1][2] for w in sorted_words),
                    b=y1,
                    rounding=self.rounding
                )

                processed_lines.append({
                    "text": full_text,
                    "bbox": bbox.to_dict(),
                    "gid": line_map[(y0, y1)],
                    "pid": page_pid,
                    "tid": global_tid,
                    "page": page_num
                })
                page_pid += 1

            start_fid, end_fid = (min(page_fids), max(page_fids)) if page_fids else (-1, -1)
            start_gid, end_gid = (min(page_gids), max(page_gids)) if page_gids else (-1, -1)

            page_metadata = {
                "start_fid": start_fid,
                "end_fid": end_fid,
                "total_fids": len(page_fids),
                "start_gid": start_gid,
                "end_gid": end_gid
            }

            elements.sort(key=lambda el: (el["bbox"]["bottom"], el["bbox"]["right"]))

            page_data["text_elements"] = processed_lines
            page_data["form_fields"] = elements
            page_data["metadata"] = page_metadata
            extracted_data["pages"].append(page_data)

        save_json(extracted_data, storage_config)
        logger.info("Extraction completed.")
        return extracted_data
