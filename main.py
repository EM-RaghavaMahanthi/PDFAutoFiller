import os
from src.core.pipeline import PDFProcessingPipeline
from src.utils.logger import logger  

# Define input paths
pdf_path = "data/input/sample1.pdf"
json_path = "data/input/sample1.json"
output_json = "data/temp/sample1_fitz_extracted_lines.json"
mapped_json = "data/temp/sample1_mapped.json"

# Convert paths to absolute paths
pdf_path = os.path.abspath(pdf_path)
json_path = os.path.abspath(json_path)
output_json = os.path.abspath(output_json)
mapped_json = os.path.abspath(mapped_json)

# Run pipeline
logger.info("Initializing PDF processing pipeline.")
pipeline = PDFProcessingPipeline(pdf_path, json_path, output_json, mapped_json, method="fitzl")
pipeline.run_mapping()
logger.info("Pipeline execution completed successfully.")
