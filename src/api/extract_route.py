from fastapi import APIRouter
from src.models.request_models import ExtractRequest
from src.extractors.fitz_extract_lines import FitzExtractorLine
import os
import yaml
from src.utils.logger import logger

router = APIRouter()

# Load config
with open("pipeline_config.yaml", "r") as f:
    pipeline_config = yaml.safe_load(f)

extractor_config = pipeline_config.get("extractor", {})
WIDGET_LINE_DISTANCE_THRESHOLD = extractor_config.get("WIDGET_LINE_DISTANCE_THRESHOLD", 10)

logger.info(f"WIDGET_LINE_DISTANCE_THRESHOLD : {WIDGET_LINE_DISTANCE_THRESHOLD}")

@router.post("/extract")
def extract_pdf(request: ExtractRequest):
    pdf_path = request.pdf_path

    if not os.path.exists(pdf_path):
        return {"message": f"PDF file not found at {pdf_path}"}

    file_name = os.path.basename(pdf_path).replace(".pdf", "")
    output_json = f"data/temp/extracted_{file_name}.json"

    extractor = FitzExtractorLine(WIDGET_LINE_DISTANCE_THRESHOLD)
    extracted_data = extractor.extract(pdf_path, output_json=output_json)

    return {
        "message": "Extraction completed",
        "extracted_data_path": output_json
    }
