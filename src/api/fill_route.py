# src/routes/fill_pdf.py
from fastapi import APIRouter
from src.models.request_models import FillRequest
from src.utils.logger import logger
from src.utils.storage import download_to_tempfile, cleanup_temp_file
from src.fillers import get_filler_by_name
import yaml
import os

router = APIRouter()

@router.post("/fill")
def fill_pdf(request: FillRequest):
    config_path = request.config_path

    if not os.path.exists(config_path):
        return {"message": f"Config file not found at {config_path}"}

    with open(config_path, "r") as f:
        pipeline_config = yaml.safe_load(f)

    # --- Method Section ---
    filler_block = pipeline_config.get("filler", {})
    method_section = filler_block.get("method", {})
    current_method = method_section.get("current_method", "fitz")
    method_config = next((m for m in method_section.get("methods", []) if m.get("name") == current_method), {})
    method_config["name"] = current_method

    # --- Storage Section ---
    storage_section = filler_block.get("storage", {})
    current_storage = storage_section.get("current_storage", "local")
    storage_config = next((s for s in storage_section.get("storages", []) if s.get("name") == current_storage), {})
    storage_config["name"] = current_storage

    logger.info(f"Filler method: {current_method}")
    logger.info(f"Storage type: {current_storage}")

    # --- Download files to temp ---
    temp_pdf_path = download_to_tempfile(storage_config, key_name="pdf_path", suffix=".pdf")
    temp_extracted_path = download_to_tempfile(storage_config, key_name="extracted_path", suffix=".json")
    temp_mapping_path = download_to_tempfile(storage_config, key_name="mapping_path", suffix=".json")

    try:
        method_config["storage"] = storage_config  # Pass storage for output handling
        filler = get_filler_by_name(current_method, method_config)
        result = filler.fill_pdf(temp_pdf_path, temp_extracted_path, temp_mapping_path, storage_config)
    finally:
        cleanup_temp_file(temp_pdf_path, delete=False)
        cleanup_temp_file(temp_extracted_path, delete=False)
        cleanup_temp_file(temp_mapping_path, delete=False)

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