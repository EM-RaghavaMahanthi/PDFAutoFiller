import json
from ..extractors.docling_extract import DoclingExtractor
from src.extractors.fitz_extract import FitzExtractor
from src.extractors.fitz_extract_lines import FitzExtractorLine


class PDFExtractor:
    """Orchestrates different extraction methods."""

    def __init__(self, method="docling"):
        self.method = method
        self.extractor = self._initialize_extractor()

    def _initialize_extractor(self):
        """Initialize extractor based on the selected method."""
        if self.method == "docling":
            return DoclingExtractor()
        
        elif self.method == "fitz":
            
            return FitzExtractor()
        
        elif self.method == "fitzl":
            return FitzExtractorLine()
        
        else:
            raise ValueError(f"Unknown extraction method: {self.method}")

    def extract_fields(self, pdf_path, output_json="data/temp/extracted.json"):
        """Extract fields from the given PDF."""
        return self.extractor.extract(pdf_path, output_json)


