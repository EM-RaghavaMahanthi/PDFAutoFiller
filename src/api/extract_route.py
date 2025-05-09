# src/routes/extract.py
from fastapi import APIRouter
from src.models.request_models import ExtractRequest
from src.extractors import get_extractor_by_name
from src.utils.logger import logger
from src.utils.storage import download_to_tempfile, cleanup_temp_file
import os
import yaml

router = APIRouter()

@router.post("/extract")
def extract_pdf(request: ExtractRequest):
    config_path = request.config_path

    if not os.path.exists(config_path):
        return {"message": f"Config file not found at {config_path}"}

    with open(config_path, "r") as f:
        pipeline_config = yaml.safe_load(f)

    extractor_config = pipeline_config.get("extractor", {})

    # ----- Method selection -----
    method_block = extractor_config.get("method", {})
    current_method = method_block.get("current_method", "fitz")
    method_config = next(
        (m for m in method_block.get("methods", []) if m["name"] == current_method),
        {}
    )

    # ----- Storage selection -----
    storage_block = extractor_config.get("storage", {})
    current_storage = storage_block.get("current_storage", "local")
    storage_config = next(
        (s for s in storage_block.get("storages", []) if s["name"] == current_storage),
        {}
    )
    storage_config["name"] = current_storage

    logger.info(f"Extractor method: {current_method}")
    logger.info(f"Storage method: {current_storage}")

    pdf_path = download_to_tempfile(storage_config, key_name="input_path", suffix=".pdf")

    try:
        extractor = get_extractor_by_name(current_method, method_config)
        extracted_data = extractor.extract(pdf_path, storage_config)
    finally:
        cleanup_temp_file(pdf_path, delete=False)

    # ----- Construct full output path -----
    storage_type = storage_config.get("name", "local")
    if storage_type == "local":
        extracted_data_path = os.path.abspath(storage_config.get("output_path", ""))
    elif storage_type == "s3":
        extracted_data_path = f"s3://{storage_config.get('bucket')}/{storage_config.get('output_prefix')}extracted.json"
    else:
        extracted_data_path = storage_config.get("output_path", "")

    return {
        "message": "Extraction completed",
        "storage_type": storage_type,
        "extracted_data_path": extracted_data_path
    }
