import os
import json
import shutil
import fitz  # PyMuPDF

class FitzFiller:
    def __init__(self, rounding=1):
        self.rounding = rounding

    def load_data(self, extracted_path, mapping_path):
        """Load extracted data and final mappings."""
        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(mapping_path, "r", encoding="utf-8") as f:
            final_mappings = json.load(f)
        return extracted_data, final_mappings

    def create_output_path(self, pdf_path, output_dir="data/output"):
        """Create dynamic output path."""
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = os.path.basename(pdf_path)
        output_pdf_path = os.path.join(output_dir, f"filled_{pdf_name}")
        return output_pdf_path

    def build_fid_bbox_map(self, extracted_data):
        """Create map of fid → (bbox, type) from extracted data."""
        fid_bbox_map = {}
        for page in extracted_data["pages"]:
            for field in page["form_fields"]:
                fid = str(field["fid"])
                bbox = field["bbox"]
                field_type = field["type"]
                fid_bbox_map[fid] = (bbox, field_type, page["page_number"] - 1)
        return fid_bbox_map

    def fill_pdf(self, pdf_path, extracted_path, mapping_path):
        """Main function to fill PDF and return stats."""
        extracted_data, final_mappings = self.load_data(extracted_path, mapping_path)
        fid_bbox_map = self.build_fid_bbox_map(extracted_data)

        output_pdf_path = self.create_output_path(pdf_path)
        shutil.copy(pdf_path, output_pdf_path)

        doc = fitz.open(output_pdf_path)
        filled_count = 0
        total_count = 0

        for page_key, mappings in final_mappings.items():
            for fid, (key, value, confidence) in mappings.items():
                if value is None or value == "":
                    continue

                bbox_info = fid_bbox_map.get(fid)
                if not bbox_info:
                    continue

                bbox, field_type, page_num = bbox_info

                # Only fill text & table cell fields
                if field_type not in ["text_input"]:
                    continue

                rect = fitz.Rect(bbox["left"], bbox["top"], bbox["right"], bbox["bottom"])
                page = doc[page_num]

                try:
                    page.insert_textbox(rect, str(value), fontsize=9, color=(1, 0, 0))  # Red color
                    filled_count += 1
                except Exception as e:
                    print(f"[Warning] Could not fill fid {fid}: {e}")

                total_count += 1

        doc.saveIncr()

        percent = round((filled_count / total_count) * 100, 2) if total_count else 0

        print(f"\nTotal Fields Processed: {total_count}")
        print(f"Fields Filled: {filled_count}")
        print(f"Fill Percentage: {percent}%")
        print(f"Filled PDF saved at: {output_pdf_path}")

        return {
            "output_pdf": output_pdf_path,
            "filled_count": filled_count,
            "total_count": total_count,
            "percentage": percent
        }
