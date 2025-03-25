import fitz  # PyMuPDF
import json
import re
from src.models.bounding_box import BoundingBox

class FitzExtractorLine:
    """Extracts text, form fields, and tables from PDFs with sorted Global/Page IDs."""

    def __init__(self, rounding=1):
        self.global_id = 1   # Global ID counter for all elements
        self.global_fid = 1  # Global Form Field ID counter (for form fields only)
        self.rounding = rounding  # Rounding precision for bounding boxes
        self.fid_to_gid_map = {}  # Mapping {fid: gid} for metadata

    def extract(self, pdf_path, output_json="data/temp/extracted.json"):
        """Extracts all elements from a PDF, sorts them, and assigns unique IDs."""
        doc = fitz.open(pdf_path)
        extracted_data = {"pages": []}

        for page_num, page in enumerate(doc, start=1):
            page_data = {
                "page_number": page_num,
                "text_elements": [],
                "form_fields": [],
                "tables": [],
                "table_cell_info": {}  # Only store form field mappings to tables
            }

            elements = []  # Store all form fields separately
            words = page.get_text("words")  
            widgets = {w.rect: w for w in page.widgets()}  # Store widgets by bbox
            lines = {}
            line_map = {}


            # **Step 1: Extract Text, Replace Blanks, and Organize by Lines**
            for word in words:
                x0, y0, x1, y1, text, line_num, sub_line_num, word_num = word
                line_key = (round(y0, self.rounding), round(y1, self.rounding))  # Round y-coordinates
                if line_key not in line_map:
                    line_map[line_key] = self.global_id
                    self.global_id += 1
                    lines[line_key] = []


                if line_key not in lines:
                    lines[line_key] = []

                # Replace placeholder blanks (`......` or `____`) with `[FIELD]`
                if re.match(r"[._\u2026-]{2,}", text):
                    lines[line_key].append(("", (x0, y0, x1, y1), word_num))
                else:
                    lines[line_key].append((text, (x0, y0, x1, y1), word_num))

            # **Step 2: Extract Tables and Assign Form Fields to Them**
            tables = page.find_tables()
            table_data = []
            table_fid_map = {}  # {fid: {"tid": table_id, "row": row_idx, "col": col_idx}}

            for tid, table in enumerate(tables):
                table_info = {
                    "tid": tid + 1,
                    "bbox": list(table.bbox),  
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                }
                table_data.append(table_info)

            page_data["tables"] = table_data  # Store table metadata

            # **Step 3: Assign Widgets to Closest Line and Tables**
            for rect, widget in widgets.items():
                fid = self.global_fid
                bbox = BoundingBox(l=rect.x0, t=rect.y0, r=rect.x1, b=rect.y1, rounding=self.rounding)
                field_type = "checkbox" if "checkbox" in widget.field_name.lower() else "text_input"

                # **Check if widget belongs to a table**
                assigned_table = None
                for table in table_data:
                    t_bbox = table["bbox"]
                    if bbox.l >= t_bbox[0] and bbox.r <= t_bbox[2] and bbox.t >= t_bbox[1] and bbox.b <= t_bbox[3]:
                        assigned_table = table["tid"]
                        break  # Found table, no need to check further

                # **Find the Best Line to Insert the Widget Placeholder**
                closest_line = None
                min_distance = float("inf")
                assigned_gid = None  

                for (y0, y1), words in lines.items():
                    if words:
                        _, (_, line_y0, _, line_y1), _ = words[0]  # Get first word bbox
                        distance = abs(rect.y1 - line_y1)

                        if distance < min_distance:
                            min_distance = distance
                            closest_line = (y0, y1)

                if closest_line:
                    if assigned_table:
                        field_tag = "TABLE_CELL_FIELD"
                    elif field_type == "checkbox":
                        field_tag = "CHECKBOX_FIELD"
                    else:
                        field_tag = "BLANK_FIELD"

                    lines[closest_line].append((f"[{field_tag}:{fid}]", (rect.x0, rect.y0, rect.x1, rect.y1), 9999))  
                    assigned_gid = line_map[closest_line] 

                # **Store fid → gid mapping for metadata tracking**
                self.fid_to_gid_map[fid] = assigned_gid  

                form_field = {
                    "type": field_type,
                    "bbox": bbox.to_dict(),
                    "fid": fid,
                    "field_name": widget.field_name if widget.field_name else None,
                    "gid": assigned_gid  
                }
                elements.append(form_field)

                # If form field belongs to a table, map it separately
                if assigned_table:
                    page_data["table_cell_info"][fid] = {"tid": assigned_table}

                self.global_fid += 1  

            # **Step 4: Sort Words & Widgets in Each Line, Assign GIDs**
            processed_lines = []
            page_pid = 1  

            for (y0, y1), words in lines.items():
                sorted_words = sorted(words, key=lambda w: w[1][0])  

                if len(sorted_words) == 0:
                    continue

                full_text = " ".join([w[0] for w in sorted_words])
                bbox = BoundingBox(
                    l=min(w[1][0] for w in sorted_words),  
                    t=y0,  
                    r=max(w[1][2] for w in sorted_words),  
                    b=y1,  
                    rounding=self.rounding
                )

                processed_lines.append({"text": full_text, "bbox": bbox.to_dict(), "gid": line_map[(y0,y1)], "pid": page_pid})

                page_pid += 1

            # **Step 5: Save to Extracted Data**
            page_data["text_elements"] = processed_lines
            page_data["form_fields"] = elements
            extracted_data["pages"].append(page_data)

        # **Step 6: Save Extracted Data**
        self.save_to_json(extracted_data, output_json)
        return extracted_data


    @staticmethod
    def save_to_json(data, output_json):
        """Saves extracted data to a JSON file."""
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Extracted data saved to {output_json}")
