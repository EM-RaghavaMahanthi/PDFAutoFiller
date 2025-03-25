import os
from src.core.pdf_extractor import PDFExtractor
from src.semantic_extractors.base import BaseSemanticExtractor
from src.semantic_extractors.prefix_suffix_cluster import PrefixSuffixClusterExtractor
from src.llm.llm_selector import LLMSelector
from src.core.field_mapper import FieldMapper
from src.utils.logger import logger
from src.utils.timing import timing_decorator

class PDFProcessingPipeline:
    """Pipeline for extracting fields, generating semantic context, and mapping them."""

    def __init__(self, pdf_path, json_path, output_json, semantics_json="data/temp/semantics.json",
                 mapped_json="data/temp/mapped_fields.json", method="docling", semantic_method="prefix_suffix",
                 model_name="models/gemini-1.5-pro", provider="gemini", api_key_env="GOOGLE_API_KEY"):

        self.pdf_path = pdf_path
        self.json_path = json_path
        self.output_json = output_json
        self.semantics_json = semantics_json
        self.mapped_json = mapped_json
        self.method = method
        self.semantic_method = semantic_method
        self.extracted_data = None
        self.semantic_extractor: BaseSemanticExtractor = None

        # Set up LLM
        api_key = os.environ.get(api_key_env)
        self.llm = LLMSelector(provider=provider, model=model_name, api_key=api_key)

        # Set up extractor
        self.extractor = PDFExtractor(method)

        # Ensure necessary directories exist
        os.makedirs(os.path.dirname(self.output_json), exist_ok=True)
        os.makedirs(os.path.dirname(self.semantics_json), exist_ok=True)
        os.makedirs(os.path.dirname(self.mapped_json), exist_ok=True)

    def _get_semantic_extractor(self) -> BaseSemanticExtractor:
        if self.semantic_method == "prefix_suffix":
            return PrefixSuffixClusterExtractor(extracted_data=self.extracted_data, llm=self.llm)
        else:
            raise ValueError(f"Unsupported semantic method: {self.semantic_method}")

    @timing_decorator
    def run_extraction(self):
        logger.info(f"Running extraction using method: {self.method}")
        self.extracted_data = self.extractor.extract_fields(self.pdf_path, self.output_json)
        logger.info(f"Extraction saved to: {self.output_json}")
        return self.extracted_data

    @timing_decorator
    def run_semantic_extraction(self):
        if self.extracted_data is None:
            self.run_extraction()

        logger.info("Running semantic context extraction.")
        self.semantic_extractor = self._get_semantic_extractor()
        self.semantic_extractor.extract_all_semantics()
        self.semantic_extractor.save_semantics(self.semantics_json)
        logger.info(f"Semantics saved to: {self.semantics_json}")

    @timing_decorator
    def run_mapping(self):
        logger.info("Running field mapping.")
        mapper = FieldMapper(method="sentence_transformer")
        mapper.map_fields(self.semantics_json, self.json_path, self.mapped_json)
        logger.info(f"Mapped fields saved to: {self.mapped_json}")

    @timing_decorator
    def run_all(self):
        logger.info("Running full pipeline (extraction + semantic + mapping)")
        self.run_extraction()
        # self.run_semantic_extraction()
        # self.run_mapping()
        logger.info("Full pipeline execution completed.")

    
