import json
import os
import pandas as pd
from collections import defaultdict
from src.validations.base import BaseValidator
from src.utils.storage import save_file
from src.utils.logger import logger

class TypeValidator(BaseValidator):
    def __init__(self, config: dict):
        super().__init__(config)

    def _load_json(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def _compute_stats(self, validation_dict, mappings):
        stats = defaultdict(lambda: {"total": 0, "filled": 0, "correctly_filled": 0})

        for fid, (field_name, value, field_type) in validation_dict.items():
            stats[field_type]["total"] += 1
            field_name = field_name.strip()
            value = value.strip()

            if fid in mappings:
                mapped_key = mappings[fid][0]
                if field_name:
                    stats[field_type]["filled"] += 1
                if not mapped_key or not mapped_key.strip():
                    continue
                if field_name == mapped_key.strip():
                    stats[field_type]["correctly_filled"] += 1

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
        logger.info("Running TypeValidator...")

        validation_dict = self._load_json(validation_path)
        mappings = self._load_json(mapping_path)

        type_stats, combined_stats = self._compute_stats(validation_dict, mappings)

        df = pd.DataFrame.from_dict(type_stats, orient="index").reset_index()
        df = df.rename(columns={"index": "type"})

        combined_row = {"type": "all", **combined_stats}
        df = pd.concat([df, pd.DataFrame([combined_row])], ignore_index=True)

        # Save locally first
        output_file = storage_config.get("output_file", "validation_stats.csv")
        local_path = os.path.join("/tmp", os.path.basename(output_file))
        df.to_csv(local_path, index=False)

        final_path = save_file(local_path, storage_config, key_name="output_file")
        logger.info(f"Validation stats saved to: {final_path}")

        return df
