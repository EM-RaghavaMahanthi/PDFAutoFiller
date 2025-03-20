import os
from src.core.pdf_extractor import PDFExtractor
from src.utils.timing import timing_decorator
from src.utils.logger import logger  

class PDFProcessingPipeline:
    """Pipeline for extracting fields, mapping them, and preparing for filling."""

    def __init__(self, pdf_path, json_path, output_json, mapped_json="data/temp/mapped_fields.json", method="docling"):
        self.pdf_path = pdf_path
        self.json_path = json_path
        self.output_json = output_json
        self.mapped_json = mapped_json
        self.method = method

        self.extractor = PDFExtractor(method)
        #self.mapper = FieldMapper()

        os.makedirs(os.path.dirname(self.output_json), exist_ok=True)

    @timing_decorator
    def run_extraction(self):
        """Step 1: Extract fields from PDF and save to JSON."""
        logger.info(f"Starting extraction for {self.pdf_path} using {self.method}.")
        extracted_fields = self.extractor.extract_fields(self.pdf_path, self.output_json)
        logger.info(f"Extraction completed. Data saved at: {self.output_json}")
        return extracted_fields

    @timing_decorator
    def run_mapping(self):
        """Step 2: Map extracted fields to user data."""
        logger.info(f"Starting field mapping using input data: {self.json_path}.")
        extracted_fields = self.run_extraction()
        return extracted_fields
        # mapped_fields = self.mapper.map_fields(extracted_fields, self.json_path, self.mapped_json)
        # logger.info(f"Mapping completed. Data saved at: {self.mapped_json}")
        # return mapped_fields
