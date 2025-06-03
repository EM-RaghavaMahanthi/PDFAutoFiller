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

    def _get_field_type(self, widget):
        base = widget.field_type_string.upper()
        if base == "CHOICE":
            return "COMBOBOX" if (widget.field_flags & 0x80) else "LISTBOX"
        if base == "BUTTON":
            return "RADIOBUTTON" if (widget.field_flags & 0x100) else "CHECKBOX"
        return base 

    def fill_text_field(self, page, rect, value, fid):
        try:
            page.insert_textbox(rect, str(value), fontsize=self.fontsize, color=(1, 0, 0))
            return True
        except Exception as e:
            logger.warning(f"Could not fill text field fid {fid}: {e}")
            return False

    def fill_checkbox(self, widget, value):
        try:
            if str(value).strip().lower() in ["yes", "on", "true", "1"]:
                widget.field_value = "On"
            else:
                widget.field_value = "Off"
            widget.update()
            return True
        except Exception as e:
            logger.warning(f"Could not fill checkbox: {e}")
            return False

    def fill_radiobutton(self, widget):
        try:
            widget.field_value = "Off"
            widget.update()
            return True
        except Exception as e:
            logger.warning(f"Could not fill radiobutton: {e}")
            return False

    def fill_choice_field(self, widget, value, field_type):
        try:
            if field_type == "LISTBOX" or field_type == "COMBOBOX":
                if value in widget.choice_values:
                    widget.field_value = value
                    widget.update()
                    return True
                else:
                    logger.warning(f"Value '{value}' not in choices for field {widget.field_name}")
            return False
        except Exception as e:
            logger.warning(f"Could not fill choice field: {e}")
            return False

    def fill_pdf(self, pdf_path, embed_pdf_path, input_json_path, extracted_path, mapping_path, storage_config: dict):
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        output_pdf_path = os.path.join("/tmp", os.path.basename(storage_config.get("output_file", "filled_output.pdf")))
        shutil.copy(embed_pdf_path, output_pdf_path)
        doc = fitz.open(embed_pdf_path)

        total_widgets = 0
        filled_count = 0

        for page_num, page in enumerate(doc, start=1):
            for widget in page.widgets():
                total_widgets += 1

                raw_key = widget.field_name
                if not raw_key:
                    continue

                key = raw_key.split(".")[-1]  
                if key.lower().startswith("unmapped"):
                    continue

                if key not in input_data:
                    continue

                value = input_data[key]
                if not value:
                    continue

                rect = widget.rect
                field_type = self._get_field_type(widget)

                if field_type == "TEXT":
                    if self.fill_text_field(page, rect, value, key):
                        filled_count += 1

                elif field_type == "CHECKBOX":
                    if self.fill_checkbox(widget, value):
                        filled_count += 1

                elif field_type == "RADIOBUTTON":
                    if self.fill_radiobutton(widget):
                        filled_count += 1

                elif field_type in ["LISTBOX", "COMBOBOX"]:
                    if self.fill_choice_field(widget, value, field_type):
                        filled_count += 1

                else:
                    logger.warning(f"Unsupported widget type '{field_type}' for key: {key}")


        doc.save(output_pdf_path)
        save_file(output_pdf_path, storage_config, key_name="output_file")
        logger.info(f"[✓] Filled {filled_count} out of {total_widgets} widgets. Saved: {output_pdf_path}")
        return {
            "output_pdf": output_pdf_path
        }
