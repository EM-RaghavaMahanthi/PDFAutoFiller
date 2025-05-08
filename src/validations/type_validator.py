import json
import pandas as pd
from collections import defaultdict

class TypeValidator:
    def __init__(self, validation_path: str, mapping_path: str):
        self.validation_path = validation_path
        self.mapping_path = mapping_path
        self.validation_dict = self._load_json(validation_path)
        self.mappings = self._load_json(mapping_path)

    def _load_json(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def compute_stats(self):
        stats = defaultdict(lambda: {
            "total": 0,
            "filled": 0,
            "correctly_filled": 0
        })

        for fid, (field_name, value, field_type) in self.validation_dict.items():
            stats[field_type]["total"] += 1
            field_name = field_name.strip()
            value = value.strip()

            if fid in self.mappings:
                mapped_key = self.mappings[fid][0]
                
                if field_name:
                    stats[field_type]["filled"] += 1

                if not mapped_key or not mapped_key.strip():
                    continue

                if field_name == mapped_key.strip():
                    stats[field_type]["correctly_filled"] += 1
                else:
                    print(fid, ":\t", field_name, "\t-->\t", mapped_key)

        combined = {
            "total": 0,
            "filled": 0,
            "correctly_filled": 0
        }

        for field_type, s in stats.items():
            total = s["total"]
            filled = s["filled"]
            correct = s["correctly_filled"]

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

    def save_to_csv(self, output_path: str):
        type_stats, combined_stats = self.compute_stats()

        df = pd.DataFrame.from_dict(type_stats, orient="index").reset_index()
        df = df.rename(columns={"index": "type"})

        combined_row = {"type": "all", **combined_stats}
        df = pd.concat([df, pd.DataFrame([combined_row])], ignore_index=True)

        df.to_csv(output_path, index=False)
        print(f"Stats saved to {output_path}")
        return df
