import os
import json
import shutil
import fitz  # PyMuPDF
from src.utils.logger import logger

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
        """Create map of fid → (bbox, type, page_num) from extracted data."""
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
        logger.info(f"Starting PDF Filling for: {pdf_path}")

        extracted_data, final_mappings = self.load_data(extracted_path, mapping_path)
        fid_bbox_map = self.build_fid_bbox_map(extracted_data)

        total_form_fields = sum(len(p["form_fields"]) for p in extracted_data["pages"])
        logger.info(f"Total Form Fields in PDF: {total_form_fields}")

        output_pdf_path = self.create_output_path(pdf_path)
        shutil.copy(pdf_path, output_pdf_path)
        doc = fitz.open(output_pdf_path)

        total_fields = 0
        fillable_fields = 0
        filled_fields = 0

        for page_key, mappings in final_mappings.items():
            for fid, (key, value, confidence) in mappings.items():
                if key is None:
                    continue  # No semantic mapping, ignore

                total_fields += 1

                if value is None or value == "":
                    continue  # Missing value

                bbox_info = fid_bbox_map.get(fid)
                if not bbox_info:
                    logger.warning(f"No bbox found for fid {fid}")
                    continue

                bbox, field_type, page_num = bbox_info

                # Only fill text fields (skip checkbox)
                if field_type not in ["text_input"]:
                    continue

                rect = fitz.Rect(bbox["left"], bbox["top"], bbox["right"], bbox["bottom"])
                page = doc[page_num]

                try:
                    page.insert_textbox(rect, str(value), fontsize=9, color=(1, 0, 0))
                    filled_fields += 1
                    fillable_fields += 1
                except Exception as e:
                    logger.warning(f"Could not fill fid {fid}: {e}")

        doc.saveIncr()

        missing_value_count = total_fields - fillable_fields

        fill_percent = round((filled_fields / total_fields) * 100, 2) if total_fields else 0
        missing_percent = round((missing_value_count / total_fields) * 100, 2) if total_fields else 0
        overall_fill_percent = round((filled_fields / total_form_fields) * 100, 2) if total_form_fields else 0
        overall_fillable_percent = round((fillable_fields / total_form_fields) * 100, 2) if total_form_fields else 0

        logger.info(f"Total Mapped Fields: {total_fields}")
        logger.info(f"Fields Successfully Filled: {filled_fields}")
        logger.info(f"Fill Percentage (w.r.t mapped fields): {fill_percent}%")
        logger.info(f"Fields with Missing Values: {missing_value_count} ({missing_percent}%)")
        logger.info(f"Overall Fill Percentage (w.r.t total form fields): {overall_fill_percent}%")
        logger.info(f"Overall Fillable Fields Percentage: {overall_fillable_percent}%")
        logger.info(f"Filled PDF saved at: {output_pdf_path}")

        return {
            "output_pdf": output_pdf_path,
            "total_fields": total_fields,
            "fillable_fields": fillable_fields,
            "filled_fields": filled_fields,
            "percentage_filled": fill_percent,
            "missing_value_count": missing_value_count,
            "percentage_missing_value": missing_percent,
            "total_form_fields": total_form_fields,
            "overall_fill_percentage": overall_fill_percent,
            "overall_fillable_percentage": overall_fillable_percent
        }
