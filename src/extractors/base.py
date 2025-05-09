from abc import ABC, abstractmethod

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, storage_config: dict) -> dict:
        """
        Extract structured data from a PDF and save based on storage config.

        Args:
            storage_config (dict): Contains input_path, output_path, and storage strategy.
                Example:
                {
                    "name": "local",
                    "input_path": "data/input/form.pdf",
                    "output_path": "data/temp/extracted.json"
                }

        Returns:
            dict: Extracted structured data
        """
        pass