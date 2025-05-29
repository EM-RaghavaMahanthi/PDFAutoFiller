import fitz
import re
from src.models.bounding_box import BoundingBox
from src.utils.logger import logger
from src.extractors.base import BaseExtractor
from src.utils.storage import save_json
from src.utils.timing import timing_decorator


class FitzExtractorLine(BaseExtractor):
    def __init__(self, config: dict):
        self.WIDGET_LINE_DISTANCE_THRESHOLD = config.get("WIDGET_LINE_DISTANCE_THRESHOLD", 10)
        self.rounding = config.get("rounding", 1)
        self.global_id = 1
        self.global_fid = 1
        self.fid_to_gid_map = {}

    def _get_field_type_new(self, widget):
        base = widget.field_type_string.upper()
        if base == "CHOICE":
            return "COMBOBOX" if (widget.field_flags & 0x80) else "LISTBOX"
        if base == "BUTTON":
            if widget.field_flags & 0x100:
                return "RADIOBUTTON"
            return "CHECKBOX"
        return base

    def _extract_words_by_line(self, words):
        lines = {}
        for word in words:
            x0, y0, x1, y1, text, *_ = word
            line_key = (round(y0, self.rounding), round(y1, self.rounding))
            if line_key not in lines:
                lines[line_key] = []
            if re.match(r"[._\u2026-]{2,}", text):
                lines[line_key].append(("", (x0, y0, x1, y1), word[-1]))
            else:
                lines[line_key].append((text, (x0, y0, x1, y1), word[-1]))
        return lines

    def _assign_gids_to_lines(self, lines):
        line_map = {}
        for line_key in sorted(lines.keys(), key=lambda k: k[0]):
            line_map[line_key] = self.global_id
            self.global_id += 1
        return line_map

    def _extract_tables(self, page, global_tid):
        tables = []
        for table in page.find_tables():
            tables.append({
                "tid": global_tid,
                "bbox": list(table.bbox),
                "row_count": table.row_count,
                "col_count": table.col_count
            })
            global_tid += 1
        return tables, global_tid

    def _assign_fid_and_gid_to_field(self, rect, widget, lines, line_map, table_data, page_num):
        fid = self.global_fid
        bbox = BoundingBox(l=rect.x0, t=rect.y0, r=rect.x1, b=rect.y1, rounding=self.rounding)

        field_type_str = self._get_field_type_new(widget)

        assigned_table = next((t["tid"] for t in table_data if bbox.l >= t["bbox"][0] and
                               bbox.r <= t["bbox"][2] and bbox.t >= t["bbox"][1] and
                               bbox.b <= t["bbox"][3]), None)

        min_distance = float("inf")
        closest_line = None
        for (y0, y1), words in lines.items():
            if words:
                _, (_, _, _, line_y1), _ = words[0]
                distance = abs(rect.y1 - line_y1)
                if distance < min_distance:
                    min_distance = distance
                    closest_line = (y0, y1)

        if closest_line and min_distance <= self.WIDGET_LINE_DISTANCE_THRESHOLD:
            line_key = closest_line
        else:
            line_key = (round(rect.y0, self.rounding), round(rect.y1, self.rounding))
            if line_key not in lines:
                lines[line_key] = []
                line_map[line_key] = self.global_id
                self.global_id += 1

        field_tag = f"{field_type_str}_FIELD"

        if assigned_table:
            field_tag = "TABLE_CELL_FIELD"

        AVG_CHAR_WIDTH = 7
        field_text = f"[{field_tag}:{fid}]"
        synthetic_width = len(field_text) * AVG_CHAR_WIDTH
        x0 = rect.x0
        x1 = x0 + synthetic_width
        lines[line_key].append((field_text, (x0, rect.y0, x1, rect.y1), 9999))
        
        #lines[line_key].append((f"[{field_tag}:{fid}]", (rect.x0, rect.y0, rect.x1, rect.y1), 9999))

        gid = line_map[line_key]
        self.fid_to_gid_map[fid] = gid

        form_field = {
            "type_inferred": field_tag,
            "field_type": field_type_str,
            "field_type_new" : self._get_field_type_new(widget),
            "field_flag": widget.field_flags,
            "bbox": bbox.to_dict(),
            "fid": fid,
            "page": page_num,
            "field_name": widget.field_name or None,
            "field_value": widget.field_value,
            "gid": gid
        }

        self.global_fid += 1
        return fid, gid, form_field, assigned_table

    def _process_lines(self, lines, line_map, page_num, global_tid):
        processed = []
        AVG_CHAR_WIDTH = 7  
        LEFT_MARGIN_X = 70
        for page_pid, line_key in enumerate(sorted(lines.keys()), start=1):
            words = sorted(lines[line_key], key=lambda w: w[1][0])
            if not words:
                continue

            full_text = ""
            previous_x1 = None

            for i, (word, (x0, y0, x1, y1), _) in enumerate(words):
          
                if i == 0:
                    gap = max(0, x0 - LEFT_MARGIN_X)
                    space_count = int(gap / AVG_CHAR_WIDTH)
                    full_text += " " * space_count
                else:
                    gap = max(0, x0 - previous_x1)
                    space_count = int(gap / AVG_CHAR_WIDTH)
                    full_text += " " * max(1, space_count)

                full_text += word
                previous_x1 = x1

            bbox = BoundingBox(
                l=min(w[1][0] for w in words),
                t=line_key[0],
                r=max(w[1][2] for w in words),
                b=line_key[1],
                rounding=self.rounding
            )

            processed.append({
                "text": full_text,
                "bbox": bbox.to_dict(),
                "gid": line_map[line_key],
                "pid": page_pid,
                "tid": global_tid,
                "page": page_num
            })

        return processed


    def _compute_page_metadata(self, page_fids, page_gids):
        return {
            "start_fid": min(page_fids) if page_fids else -1,
            "end_fid": max(page_fids) if page_fids else -1,
            "total_fids": len(page_fids),
            "start_gid": min(page_gids) if page_gids else -1,
            "end_gid": max(page_gids) if page_gids else -1
        }

    @timing_decorator
    def extract(self, pdf_path, storage_config: dict) -> dict:
        doc = fitz.open(pdf_path)
        logger.info(f"Starting extraction from PDF: {pdf_path}")
        extracted_data = {"pages": []}
        global_tid = 1

        for page_num, page in enumerate(doc, start=1):
            words = page.get_text("words")
            widgets = {w.rect: w for w in page.widgets()}
            lines = self._extract_words_by_line(words)
            line_map = self._assign_gids_to_lines(lines)

            table_data, global_tid = self._extract_tables(page, global_tid)
            form_fields, page_fids, page_gids, table_cell_info = [], [], [], {}

            for rect, widget in widgets.items():
                fid, gid, form_field, table_id = self._assign_fid_and_gid_to_field(
                    rect, widget, lines, line_map, table_data, page_num
                )
                form_fields.append(form_field)
                page_fids.append(fid)
                page_gids.append(gid)
                if table_id is not None:
                    table_cell_info[fid] = {"tid": table_id}

            text_elements = self._process_lines(lines, line_map, page_num, global_tid)
            page_metadata = self._compute_page_metadata(page_fids, page_gids)

            form_fields.sort(key=lambda el: (el["bbox"]["bottom"], el["bbox"]["right"]))
            extracted_data["pages"].append({
                "page_number": page_num,
                "text_elements": text_elements,
                "form_fields": form_fields,
                "tables": table_data,
                "table_cell_info": table_cell_info,
                "metadata": page_metadata
            })

        save_json(extracted_data, storage_config)
        logger.info("Extraction completed.")
        return extracted_data
