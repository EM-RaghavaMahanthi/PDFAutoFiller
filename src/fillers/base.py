# src/fillers/base.py

from abc import ABC, abstractmethod

class BaseFiller(ABC):
    """
    Abstract base class for all PDF filler implementations.
    """
    
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fill_pdf(self, pdf_path: str, extracted_path: str, mapping_path: str, storage_config: dict) -> dict:
        """
        Fill the PDF using extracted data and final field mappings.

        Parameters:
        - pdf_path: Path to the original PDF file
        - extracted_path: Path to the extracted structure JSON
        - mapping_path: Path to the mapping JSON with fid → key → value
        - storage_config: Dict containing output path details

        Returns:
        - Dictionary with filling statistics and final output file path
        """
        pass
