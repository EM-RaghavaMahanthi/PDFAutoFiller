
from src.models.bounding_box import BoundingBox

class BaseExtractor:
    def extract(self, pdf_path):
        """
        Base extraction function.
        :param pdf_path: Path to input PDF
        :return: List of ExtractedField objects
        """
        raise NotImplementedError("Subclasses must implement extract method.")


