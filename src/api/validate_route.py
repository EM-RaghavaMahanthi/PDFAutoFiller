# src/routes/validate.py
from fastapi import APIRouter
from src.models.request_models import ValidateRequest
from src.validations import get_validator_by_name
from src.utils.logger import logger
from src.utils.storage import download_to_tempfile, cleanup_temp_file
from src.utils.render_jinja_config import render_jinja_config
import os
import yaml

router = APIRouter()

@router.post("/validate")
def validate_mapping(request: ValidateRequest):
    config_path = request.config_path

    if not os.path.exists(config_path):
        return {"message": f"Config file not found at {config_path}"}

    pipeline_config = render_jinja_config(config_path, {})

    # --- Method Section ---
    validator_block = pipeline_config.get("validator", {})
    method_section = validator_block.get("method", {})
    current_method = method_section.get("current_method", "type_validator")
    method_config = next((m for m in method_section.get("methods", []) if m.get("name") == current_method), {})
    method_config["name"] = current_method

    # --- Storage Section ---
    storage_section = validator_block.get("storage", {})
    current_storage = storage_section.get("current_storage", "local")
    storage_config = next((s for s in storage_section.get("storages", []) if s.get("name") == current_storage), {})
    storage_config["name"] = current_storage

    logger.info(f"Validator method: {current_method}")
    logger.info(f"Storage type: {current_storage}")

    # --- Download files ---
    temp_validation_path = download_to_tempfile(storage_config, key_name="validation_path", suffix=".json")
    temp_mapping_path = download_to_tempfile(storage_config, key_name="mapping_path", suffix=".json")
    output_path = storage_config.get("output_path", "data/output/validation_stats.csv")

    try:
        method_config["storage"] = storage_config
        validator = get_validator_by_name(current_method, method_config)
        df = validator.validate(temp_validation_path, temp_mapping_path, storage_config)
    finally:
        cleanup_temp_file(temp_validation_path, delete=False)
        cleanup_temp_file(temp_mapping_path, delete=False)

    return {
        "message": "Validation Completed",
        "output_path": output_path,
        "num_types": len(df),
        "preview": df.head().to_dict(orient="records")
    }
