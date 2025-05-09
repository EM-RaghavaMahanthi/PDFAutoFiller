# src/extractors/__init__.py
from .fitz_extract_lines import FitzExtractorLine
from .docling_extract import DoclingExtractor
from .base import BaseExtractor

def get_extractor_by_name(name: str, config: dict) -> BaseExtractor:
    name = name.lower()

    if name == "fitz":
        return FitzExtractorLine(config)
    elif name == "docling":
        return DoclingExtractor(config)
    else:
        raise ValueError(f"Unknown extractor method: {name}")