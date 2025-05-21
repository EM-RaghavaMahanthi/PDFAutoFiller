import json
import faiss
import numpy as np
from src.llm.embed_selector import EmbedModelSelector
from src.utils.logger import logger
from src.utils.storage import save_json, save_numpy_array
import os
from src.utils.timing import timing_decorator

class EmbedMapper:
    def __init__(self, config: dict, chunking_section: dict):
        self.config = config
        embedding_config = config.get("embedder", {})
        self.embed_model = EmbedModelSelector(embedding_config)
        

    def build_final_fid_context_map(self, extracted_data, prefix_window=10, suffix_window=10):
        fid_to_field_name = {}
        for page in extracted_data["pages"]:
            for field in page["form_fields"]:
                fid_to_field_name[str(field["fid"])] = field.get("field_name", "")

        fid_prefix_suffix = self.extract_fid_prefix_suffix_context(extracted_data, prefix_window, suffix_window)

        final_context_map = {}
        for fid, ctx in fid_prefix_suffix.items():
            field_name = fid_to_field_name.get(fid, "")
            final_context = f"{field_name} ||| {ctx['prefix']} ||| {ctx['suffix']}"
            final_context_map[int(fid)] = final_context.strip()

        return final_context_map

    def extract_fid_prefix_suffix_context(self, extracted_data, prefix_window=10, suffix_window=10):
        import re
        gid_to_text = {}
        gid_to_fids = {}
        fid_context = {}

        for page in extracted_data["pages"]:
            for line in page["text_elements"]:
                gid = line["gid"]
                text = line["text"]
                gid_to_text[gid] = text

                matches = re.findall(r"\[(?:FIELD|BLANK_FIELD|TABLE_CELL_FIELD|CHECKBOX_FIELD):(\d+)\]", text)
                for fid in matches:
                    gid_to_fids.setdefault(gid, []).append(fid)

        all_gids = sorted(gid_to_text.keys())

        for gid in all_gids:
            line = gid_to_text[gid]
            if gid not in gid_to_fids:
                continue

            for fid in gid_to_fids[gid]:
                pattern = r"\[(?:FIELD|BLANK_FIELD|TABLE_CELL_FIELD|CHECKBOX_FIELD):" + fid + r"\]"
                match = re.search(pattern, line)
                if not match:
                    continue

                before = line[:match.end()]
                after = line[match.end():]

                prefix_lines = [gid_to_text[all_gids[i]] for i in range(max(0, all_gids.index(gid) - prefix_window), all_gids.index(gid))]
                prefix_lines.append(before)
                prefix = "\n".join(prefix_lines)

                suffix_lines = [after] + [gid_to_text[all_gids[i]] for i in range(all_gids.index(gid) + 1, min(len(all_gids), all_gids.index(gid) + 1 + suffix_window))]
                suffix = "\n".join(suffix_lines)

                fid_context[fid] = {
                    "prefix": prefix.strip(),
                    "suffix": suffix.strip()
                }

        return fid_context

    def create_faiss_index(self, texts):
        embeddings = self.embed_model.encode(texts)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        return index, embeddings

    @timing_decorator
    def process_and_save(self, extracted_path, input_json_path, storage_config: dict, output_dir="data/temp/"):
        mapping_path = storage_config.get("output_path")
        file_stub = os.path.splitext(os.path.basename(mapping_path))[0]
        logger.info(f"Starting Field Mapping for extracted file: {extracted_path}")

        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        fid_context_map = self.build_final_fid_context_map(extracted_data)
        fids = list(fid_context_map.keys())
        context_texts = [fid_context_map[fid] for fid in fids]

        fid_index, fid_embeddings = self.create_faiss_index(context_texts)

        keys = list(input_data.keys())
        input_index, input_embeddings = self.create_faiss_index(keys)

        D, I = input_index.search(fid_embeddings, 1)  # Top-1 match

        results = {}
        for idx, fid in enumerate(fids):
            match_idx = I[idx][0]
            score = float(D[idx][0])
            matched_key = keys[match_idx] if score > 0 else None
            matched_value = input_data.get(matched_key) if matched_key else None
            results[str(fid)] = [matched_key, matched_value, round(score, 3)]

        save_json(results, storage_config)

        emb_config = storage_config.get("embeddings", {})
        save_numpy_array(fid_embeddings, emb_config.get("fid_embedding_path"), storage_config)
        save_numpy_array(input_embeddings, emb_config.get("input_embedding_path"), storage_config)

        logger.info(f"Saved cleaned (deduplicated) field mappings to: {mapping_path}")
        return mapping_path
