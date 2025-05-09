# src/mappers/sentence_transform_mapper.py
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from mappers.base import BaseFieldMapper

class SentenceTransformMapper(BaseFieldMapper):
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        super().__init__()
        self.model = SentenceTransformer(model_name)
        self.key_embeddings = None
        self.input_json_path = None

    def load_input(self, input_path):
        self.input_json_path = input_path

        with open(input_path, "r") as f:
            input_data = json.load(f)

        def flatten_json(y, prefix="", drop_prefix=True):
            flat = {}
            if isinstance(y, dict):
                for k, v in y.items():
                    flat.update(flatten_json(v, f"{prefix}{k}.", drop_prefix))
            elif isinstance(y, list):
                for idx, item in enumerate(y):
                    flat.update(flatten_json(item, f"{prefix}{idx}.", drop_prefix))
            else:
                key = prefix.rstrip('.')
                if drop_prefix:
                    key = key.split('.')[-1]
                flat[key] = y
            return flat

        for record in input_data["records"]:
            flat = flatten_json(record)
            self.flattened_keys.extend(flat.keys())
            self.flattened_values.update(flat)

    def embed_keys(self, input_json_path):
        base = os.path.splitext(input_json_path)[0]
        self.key_embeddings = self.model.encode(self.flattened_keys, convert_to_numpy=True)

        np.save(f"{base}_embedded_keys.npy", self.key_embeddings)
        with open(f"{base}_embedded_keys.json", "w") as f:
            json.dump(self.flattened_keys, f, indent=2)
        with open(f"{base}_embedded_values.json", "w") as f:
            json.dump(self.flattened_values, f, indent=2)

    def match_semantic_context(self, semantic_context, top_k=1):
        query_embedding = self.model.encode([semantic_context])
        similarities = cosine_similarity(query_embedding, self.key_embeddings)[0]
        top_indices = similarities.argsort()[::-1][:top_k]

        results = []
        for idx in top_indices:
            matched_key = self.flattened_keys[idx]
            matched_value = self.flattened_values.get(matched_key, "N/A")
            score = similarities[idx]
            results.append({
                "matched_key": matched_key,
                "matched_value": matched_value,
                "score": round(float(score), 4)
            })
        return results

    def run_mapping(self):
        self.mapped_results = []
        for fid, semantic in self.semantics.items():
            match = self.match_semantic_context(semantic, top_k=1)[0]
            match["fid"] = fid
            match["semantic"] = semantic
            self.mapped_results.append(match)

    def save(self, output_path):
        with open(output_path, "w") as f:
            json.dump(self.mapped_results, f, indent=2)
