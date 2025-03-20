import fitz  # PyMuPDF
import json
from src.models.bounding_box import BoundingBox

class FitzExtractor:
    """Extracts text, form fields, and tables from PDFs with sorted Global/Page IDs."""

    def __init__(self):
        self.global_id = 1   # Global ID counter for all elements
        self.global_fid = 1  # Global Form Field ID counter (for form fields only)

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

            elements = []  # Store all elements (text + forms) before sorting

            # **Step 1: Extract Text Elements**
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text, _, _ = block
                if not text.strip():
                    continue

                bbox = BoundingBox(l=x0, t=y0, r=x1, b=y1)
                elements.append({
                    "text": text.strip(),
                    "bbox": bbox.to_dict(),
                    "type": "text",
                    "field_name": None
                })

            # **Step 2: Extract Tables**
            tables = page.find_tables()
            table_data = []

            for tid, table in enumerate(tables):
                table_info = {
                    "tid": tid + 1,
                    "bbox": list(table.bbox),  # Bounding box of the table
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                }
                table_data.append(table_info)

            page_data["tables"] = table_data  # Save table metadata

            # **Step 3: Extract Form Fields & Associate with Tables**
            for widget in page.widgets():
                if widget.field_name:
                    bbox = BoundingBox(l=widget.rect.x0, t=widget.rect.y0,
                                       r=widget.rect.x1, b=widget.rect.y1)

                    field_type = "checkbox" if "checkbox" in widget.field_name.lower() else "text_input"

                    # Check if form field belongs to any table
                    form_tid, row_idx, col_idx = None, None, None

                    for table in table_data:
                        t_bbox = table["bbox"]
                        if bbox.l >= t_bbox[0] and bbox.r <= t_bbox[2] and bbox.t >= t_bbox[1] and bbox.b <= t_bbox[3]:
                            form_tid = table["tid"]  # Assign table ID
                            break  # Found table, no need to check further

                    # Store only `fid` in form fields, other table-related details go to `table_cell_info`
                    form_field = {
                        "type": field_type,
                        "bbox": bbox.to_dict(),
                        "fid": self.global_fid,  # Form field ID
                        "field_name": widget.field_name if widget.field_name else None
                    }
                    elements.append(form_field)

                    if form_tid:
                        page_data["table_cell_info"][self.global_fid] = {"tid": form_tid}

                    self.global_fid += 1  # Increment form field ID

            # **Step 4: Sort Elements in Reading Order**
            elements.sort(key=lambda e: (e["bbox"]["bottom"], e["bbox"]["left"]))

            # **Step 5: Assign Global & Page IDs**
            page_pid = 1  # Reset page-level ID for each page

            for element in elements:
                element["gid"] = self.global_id  # Assign unique global ID
                element["pid"] = page_pid  # Assign unique page ID
                self.global_id += 1
                page_pid += 1

                # **Save elements in respective categories**
                if element["type"] == "text":
                    page_data["text_elements"].append(element)
                else:
                    page_data["form_fields"].append(element)

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

