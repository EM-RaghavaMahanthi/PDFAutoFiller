# src/mappers/base_mapper.py
from abc import ABC, abstractmethod
import json

class BaseFieldMapper(ABC):
    def __init__(self):
        self.semantics = {}
        self.flattened_keys = []
        self.flattened_values = {}
        self.mapped_results = []

    def load_semantics(self, semantics_path):
        with open(semantics_path, "r") as f:
            self.semantics = json.load(f)

    @abstractmethod
    def load_input(self, input_path): pass

    @abstractmethod
    def embed_keys(self, input_json_path): pass

    @abstractmethod
    def run_mapping(self): pass

    @abstractmethod
    def save(self, output_path): pass
