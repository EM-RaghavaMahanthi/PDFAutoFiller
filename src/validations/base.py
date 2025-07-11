from abc import ABC, abstractmethod

class BaseValidator(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def validate(self, validation_path: str, mapping_path: str, output_path: str):
        """
        Validate mappings using a reference file and write results to output CSV.

        Parameters:
        - validation_path: path to the ground truth (JSON or PDF)
        - mapping_path: path to the mapped result (JSON or PDF)
        - output_path: CSV file where stats will be saved
        """
        pass
