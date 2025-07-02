import os
import fitz
import json
import pandas as pd
from collections import defaultdict
from src.utils.logger import logger
from src.utils.storage import save_file
from src.validations.base import BaseValidator


def get_field_type_new(widget):
    base = widget.field_type_string.upper()
    if base == "CHOICE":
        return "COMBOBOX" if (widget.field_flags & 0x80) else "LISTBOX"
    if base == "BUTTON":
        if widget.field_flags & 0x100:
            return "RADIOBUTTON"
        return "CHECKBOX"
    return base


def fitz_pdf_to_field_map(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    field_map = {}

    for page_num, page in enumerate(doc, start=1):
        for widget in page.widgets():
            rect = widget.rect
            bbox = (int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
            field_name = widget.field_name or ""
            field_value = widget.field_value or ""
            field_type = get_field_type_new(widget)
            key = (page_num, bbox)
            field_map[key] = (field_name.strip(), field_type, str(field_value).strip())

    return field_map


class EmbedValidator(BaseValidator):
    def __init__(self, config: dict):
        super().__init__(config)


    def _compute_stats(self, ground_truth_map, filled_map):
        stats = defaultdict(lambda: {
            "total_fields": 0,
            "total_filled": 0,
            "total_mapped": 0,
            "total_unmapped": 0,
            "correctly_filled": 0
        })

        for key, (gt_field_name, field_type, _) in ground_truth_map.items():
            if "unknown" in gt_field_name.strip().lower():
                continue

            stats[field_type]["total_fields"] += 1

            filled_field_name = filled_map.get(key, ("", "", ""))[0].strip()
            if not filled_field_name:
                continue

            print(filled_field_name, gt_field_name, field_type)

            stats[field_type]["total_filled"] += 1

            mapped_key = filled_field_name.split(".")[-1].strip()

            if "unmapped" in mapped_key.lower():
                stats[field_type]["total_unmapped"] += 1
            else:
                stats[field_type]["total_mapped"] += 1
                if mapped_key == gt_field_name.strip():
                    stats[field_type]["correctly_filled"] += 1

        # Compute derived metrics per field type
        combined = {
            "total_fields": 0,
            "total_filled": 0,
            "total_mapped": 0,
            "total_unmapped": 0,
            "correctly_filled": 0
        }

        for field_type, s in stats.items():
            total = s["total_fields"]
            filled = s["total_filled"]
            mapped = s["total_mapped"]
            correct = s["correctly_filled"]

            s["coverage"] = round((filled / total) * 100, 2) if total else 0
            s["accuracy"] = round((correct / filled) * 100, 2) if filled else 0
            s["mapping_precision"] = round((correct / mapped) * 100, 2) if mapped else 0

            for k in combined:
                combined[k] += s[k]

        # Compute overall metrics
        combined["coverage"] = round((combined["total_filled"] / combined["total_fields"]) * 100, 2) if combined["total_fields"] else 0
        combined["accuracy"] = round((combined["correctly_filled"] / combined["total_filled"]) * 100, 2) if combined["total_filled"] else 0
        combined["mapping_precision"] = round((combined["correctly_filled"] / combined["total_mapped"]) * 100, 2) if combined["total_mapped"] else 0

        return stats, combined



    def validate(self, validation_path: str, mapping_path: str, storage_config: dict):
        logger.info("Running EmbedValidator...")

        ground_truth_map = fitz_pdf_to_field_map(validation_path)
        filled_map = fitz_pdf_to_field_map(mapping_path)

        type_stats, combined_stats = self._compute_stats(ground_truth_map, filled_map)

        df = pd.DataFrame.from_dict(type_stats, orient="index").reset_index()
        df = df.rename(columns={"index": "type"})

        combined_row = {"type": "all", **combined_stats}
        df = pd.concat([df, pd.DataFrame([combined_row])], ignore_index=True)

        # Save to temp location first
        output_file = storage_config.get("output_file", "embed_validation_stats.csv")
        local_path = os.path.join("/tmp", os.path.basename(output_file))
        df.to_csv(local_path, index=False)

        final_path = save_file(local_path, storage_config, key_name="output_file")
        logger.info(f"Embed validation stats saved to: {final_path}")

        return df
