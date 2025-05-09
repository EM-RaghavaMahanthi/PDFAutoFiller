# src/mappers/base.py
from abc import ABC, abstractmethod

class BaseMapper(ABC):
    @abstractmethod
    def process_and_save(self, pdf_path: str, input_json_path: str, output_dir: str = "data/temp") -> str:
        """
        Process the input PDF and JSON, produce a field mapping, and save the results.

        Args:
            pdf_path (str): Path to the input PDF.
            input_json_path (str): Path to the input JSON containing values.
            output_dir (str): Directory to save the mapping outputs.

        Returns:
            str: Path to the saved mapping file.
        """
        pass
