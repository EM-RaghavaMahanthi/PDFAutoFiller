# src/semantic_extractors/base.py
import json
from abc import ABC, abstractmethod

class BaseSemanticExtractor(ABC):
    def __init__(self, extracted_data: dict):
        self.extracted_data = extracted_data
        self.forms_dict = self._generate_form_and_text_mappings()["forms_dict"]
        self.lines_info = self._generate_form_and_text_mappings()["lines_info"]
        self.output_semantics = {}  # fid -> semantic meaning

    def _generate_form_and_text_mappings(self):
        forms_dict = {
            "checkbox": {},
            "blank_input": {},
            "table_cell": {}
        }
        lines_info = {}

        for page in self.extracted_data["pages"]:
            page_number = page["page_number"]
            table_cell_info = page.get("table_cell_info", {})

            for text_item in page["text_elements"]:
                gid = text_item["gid"]
                lines_info[gid] = text_item["text"]

            for form_field in page["form_fields"]:
                fid = form_field["fid"]
                gid = form_field["gid"]
                field_name = form_field.get("field_name", "Unknown Field")
                bbox = form_field["bbox"]

                if form_field["type"] == "checkbox":
                    forms_dict["checkbox"][fid] = (gid, field_name, bbox)
                elif str(fid) in table_cell_info:
                    forms_dict["table_cell"][fid] = (gid, field_name, bbox)
                else:
                    forms_dict["blank_input"][fid] = (gid, field_name, bbox)

        return {"forms_dict": forms_dict, "lines_info": lines_info}

    def parse_semantic_json_response(self, response_text):
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                self.output_semantics.update(parsed)
        except Exception as e:
            print("Failed to parse JSON response:", e)

    def save_semantics(self, output_path="data/temp/semantic_output.json"):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.output_semantics, f, indent=2, ensure_ascii=False)
        print(f"Saved semantic mappings to {output_path}")

    def reset_semantics(self):
        self.output_semantics = {}

    @abstractmethod
    def extract_all_semantics(self, llm):
        pass
