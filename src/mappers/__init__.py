from .semantic_mapper import SemanticMapper
from .base import BaseMapper

def get_mapper_by_name(name: str, method_config: dict, chunking_config):
    if name == "semantic":
        return SemanticMapper(method_config, chunking_config)
    else:
        raise ValueError(f"Unknown mapper type: {name}")
