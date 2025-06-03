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
        stats = defaultdict(lambda: {"total": 0, "filled": 0, "correctly_filled": 0})

        for key, (gt_field_name, field_type, _) in ground_truth_map.items():
            if "unknown" in gt_field_name.strip().lower():
                continue

            stats[field_type]["total"] += 1
            

            filled_field_name = filled_map.get(key, ("", "", ""))[0].strip()
            mapped_key = filled_field_name.split(".")[-1].strip()

            if mapped_key.lower() != "unmapped":
                stats[field_type]["filled"] += 1

                if mapped_key == gt_field_name.strip():
                    stats[field_type]["correctly_filled"] += 1

        # Aggregate totals
        combined = {"total": 0, "filled": 0, "correctly_filled": 0}
        for field_type, s in stats.items():
            total, filled, correct = s["total"], s["filled"], s["correctly_filled"]
            s["fill_rate"] = round((filled / total) * 100, 2) if total else 0
            s["correct_fill_rate"] = round((correct / total) * 100, 2) if total else 0
            s["accuracy"] = round((correct / filled) * 100, 2) if filled else 0

            combined["total"] += total
            combined["filled"] += filled
            combined["correctly_filled"] += correct

        combined["fill_rate"] = round((combined["filled"] / combined["total"]) * 100, 2) if combined["total"] else 0
        combined["correct_fill_rate"] = round((combined["correctly_filled"] / combined["total"]) * 100, 2) if combined["total"] else 0
        combined["accuracy"] = round((combined["correctly_filled"] / combined["filled"]) * 100, 2) if combined["filled"] else 0

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
