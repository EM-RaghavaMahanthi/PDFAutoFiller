from fastapi import APIRouter
from src.models.request_models import FillRequest
from src.fillers.fitz_filler import FitzFiller
import yaml
from src.utils.logger import logger

router = APIRouter()

# Load filler config from pipeline_config.yaml
with open("pipeline_config.yaml", "r") as f:
    pipeline_config = yaml.safe_load(f)

filler_config = pipeline_config.get("filler", {})
FONTSIZE = filler_config.get("fontsize", 6)

logger.info(f"FONTSIZE used in Filler: {FONTSIZE}")

@router.post("/fill")
def fill_pdf(request: FillRequest):
    pdf_path = request.pdf_path

    file_name = pdf_path.split("/")[-1].replace(".pdf", "")
    extracted_path = f"data/temp/extracted_{file_name}.json"
    mapping_path = f"data/temp/mappings_{file_name}.json"

    filler = FitzFiller(fontsize=FONTSIZE)

    result = filler.fill_pdf(pdf_path, extracted_path, mapping_path)

    return {
        "message": "PDF Filling Completed",
        "output_pdf": result["output_pdf"],
        "total_form_fields": result["total_form_fields"],
        "total_mapped_fields": result["total_fields"],
        "filled_fields": result["filled_fields"],
        "missing_value_count": result["missing_value_count"],
        "mapped_percentage": result["mapped_percentage"],
        "fill_percentage_mapped": result["percentage_filled"],
        "fill_percentage_overall": result["overall_fill_percentage"]
    }
