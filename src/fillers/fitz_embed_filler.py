import os
import json
import shutil
import fitz
from src.utils.storage import save_file
from src.utils.logger import logger

class FitzEmbedFiller:
    def __init__(self, config: dict):
        self.fontsize = config.get("fontsize", 6)
        self.config = config

    def fill_text_field(self, page, rect, value, fid):
        try:
            page.insert_textbox(rect, str(value), fontsize=self.fontsize, color=(1, 0, 0))
            return True
        except Exception as e:
            logger.warning(f"Could not fill text field fid {fid}: {e}")
            return False

    def fill_button_or_choice_field(self, widget, value, key, field_type):
        try:
            state = str(value).strip().lower()
            if state in ["yes", "on", "true", "1"]:
                if field_type == 5:  
                    widget.field_value = "On"
                elif field_type == 2:  
                    widget.field_value = 1
                widget.update()
                return True
            return False
        except Exception as e:
            print(f"Could not update widget for key={key}: {e}")
            return False

    def fill_pdf(self, pdf_path, input_json_path, extracted_path, mapping_path, storage_config: dict):
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        output_pdf_path = os.path.join("/tmp", os.path.basename(storage_config.get("output_file", "filled_output.pdf")))
        shutil.copy(pdf_path, output_pdf_path)
        doc = fitz.open(output_pdf_path)

        doc = fitz.open(pdf_path)

        total_widgets = 0
        filled_count = 0

        for page_num, page in enumerate(doc, start=1):
            for widget in page.widgets():
                total_widgets += 1
                key = widget.field_name
                print(key)
                if not key:
                    continue
                key = key.split(".")[-1]

                if key=="unmapped":
                    continue

                if key not in input_data:
                    continue

                value = input_data[key]
                if not value:
                    continue

                try:
                    rect = widget.rect
                    field_type_str = {
                        5: "button",
                        7: "text",
                        2: "choice",
                        4: "signature"
                    }.get(widget.field_type, "unknown")

                    if field_type_str == "text":
                        print(key,value )
                        if self.fill_text_field(page, rect, value, key):
                            filled_count += 1
                    elif field_type_str in ["button", "choice"]:
                        if self.fill_button_or_choice_field(widget, value, key, widget.field_type):
                            filled_count += 1
                except Exception as e:
                    print(f"Failed to fill key={key} on page {page_num}: {e}")

        save_file(output_pdf_path, storage_config, key_name="output_file")
        print(f"Filled PDF saved to: {output_pdf_path}")
        print(f"Filled {filled_count} out of {total_widgets} widgets.")
        return {
            "output_pdf": output_pdf_path
        }
