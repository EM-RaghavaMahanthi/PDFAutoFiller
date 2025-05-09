# src/extractors/docling_extractor.py
import re
from docling.document_converter import DocumentConverter
from src.models.bounding_box import BoundingBox
from src.extractors.base import BaseExtractor
from src.utils.storage import save_json
from src.utils.timing import timing_decorator


class DoclingExtractor(BaseExtractor):
    """Extracts text and form fields from PDFs using Docling, handling multi-blanks correctly."""

    def __init__(self, config: dict):
        self.config = config
        self.converter = DocumentConverter()
        self.global_id = 1

    @timing_decorator
    def extract(self, pdf_path, storage_config: dict) -> dict:

        
        result = self.converter.convert(pdf_path)
        

        extracted_data = {"pages": []}

        for page_no, page in enumerate(result.pages):
            page_data = {
                "page_number": page_no + 1,
                "text_elements": [],
                "form_fields": []
            }

            page_pid = 1

            for cell in page.cells:
                bbox = BoundingBox(
                    l=cell.bbox.l, t=cell.bbox.t, r=cell.bbox.r, b=cell.bbox.b,
                    page_number=page_no + 1, field_id=f"text_{cell.id}"
                )

                text_parts, blank_parts = self.split_text_and_blanks(cell.text, bbox)

                for text, b, i in text_parts:
                    page_data["text_elements"].append({"text": text, "bbox": b.to_dict(), "gid": self.global_id+i, "pid": page_pid+i})

                for b, i in blank_parts:
                    page_data["form_fields"].append({"type": "text_input", "bbox": b.to_dict(), "gid": self.global_id+i, "pid": page_pid+i})

                page_pid += len(text_parts) + len(blank_parts)
                self.global_id += len(text_parts) + len(blank_parts)

            for form_field in page.predictions.layout.clusters:
                if form_field.label in ["checkbox", "text_input"]:
                    bbox = BoundingBox(
                        l=form_field.bbox.l, t=form_field.bbox.t, r=form_field.bbox.r, b=form_field.bbox.b,
                        page_number=page_no + 1, field_id=f"field_{form_field.id}"
                    )
                    page_data["form_fields"].append({"type": form_field.label, "bbox": bbox.to_dict(), "gid": self.global_id, "pid": page_pid})
                    page_pid += 1
                    self.global_id += 1

            extracted_data["pages"].append(page_data)

        save_json(extracted_data, storage_config)
        return extracted_data

    def split_text_and_blanks(self, text, bbox):
        matches = list(re.finditer(r"[._\u2026-]{2,}", text))
        text_parts = []
        blank_parts = []

        total_length = len(text)
        char_width = bbox.width / total_length
        current_x = bbox.l
        prev_end = 0
        id = 0

        for match in matches:
            start, end = match.span()

            if start > prev_end:
                text_bbox = BoundingBox(
                    l=current_x, t=bbox.t, width=(start - prev_end) * char_width, height=bbox.height,
                    page_number=bbox.page_number, field_id=f"{bbox.field_id}_text{id}"
                )
                text_parts.append((text[prev_end:start].strip(), text_bbox, id))
                current_x += (start - prev_end) * char_width
                id += 1

            blank_bbox = BoundingBox(
                l=current_x, t=bbox.t, width=(end - start) * char_width, height=bbox.height,
                page_number=bbox.page_number, field_id=f"{bbox.field_id}_blank{id}"
            )
            blank_parts.append((blank_bbox, id))
            current_x += (end - start) * char_width
            id += 1
            prev_end = end

        if prev_end < total_length:
            text_bbox = BoundingBox(
                l=current_x, t=bbox.t, width=(total_length - prev_end) * char_width, height=bbox.height,
                page_number=bbox.page_number, field_id=f"{bbox.field_id}_text_end{id}"
            )
            text_parts.append((text[prev_end:].strip(), text_bbox, id))

        return text_parts, blank_parts
