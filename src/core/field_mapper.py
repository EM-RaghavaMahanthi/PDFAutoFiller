# src/core/field_mapper.py
import json
from src.mappers.base_mapper import BaseFieldMapper
from src.mappers.sentence_transform_mapper import SentenceTransformMapper

class FieldMapper:
    def __init__(self, method="sentence_transformer"):
        self.method = method
        self.mapper: BaseFieldMapper = self._get_mapper()

    def _get_mapper(self) -> BaseFieldMapper:
        if self.method == "sentence_transformer":
            return SentenceTransformMapper()
        else:
            raise ValueError(f"Unsupported mapping method: {self.method}")

    def map_fields(self, semantics_json: str, input_json: str, output_json: str):
        """High-level method to run field mapping."""
        self.mapper.load_semantics(semantics_json)
        self.mapper.load_input(input_json)
        self.mapper.embed_keys(input_json)
        self.mapper.run_mapping()
        self.mapper.save(output_json)
