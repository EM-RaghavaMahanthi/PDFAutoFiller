from .semantic_mapper import SemanticMapper
from .embed_mapper import EmbedMapper
from .feedback_semantic_mapper import FeedbackSemanticMapper

from .base import BaseMapper

def get_mapper_by_name(name: str, method_config: dict, chunking_config):
    if name == "semantic":
        return SemanticMapper(method_config, chunking_config)
    elif name == "feedback_semantic":
        return FeedbackSemanticMapper(method_config, chunking_config)
    elif name == "embed":
        return EmbedMapper(method_config, chunking_config)
    else:
        raise ValueError(f"Unknown mapper type: {name}")
