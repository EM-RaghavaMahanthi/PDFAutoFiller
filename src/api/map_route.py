# src/routes/map_fields.py
from fastapi import APIRouter
from src.models.request_models import MapFieldsRequest
from src.utils.logger import logger
from src.utils.storage import download_to_tempfile, cleanup_temp_file
from src.mappers import get_mapper_by_name
import yaml
import os

import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
router = APIRouter()

@router.post("/map-fields")
def map_fields(request: MapFieldsRequest):
    config_path = request.config_path

    if not os.path.exists(config_path):
        return {"message": f"Config file not found at {config_path}"}

    with open(config_path, "r") as f:
        pipeline_config = yaml.safe_load(f)

    mapper_block = pipeline_config.get("mapper", {})

    # Get method and config
    method_section = mapper_block.get("method", {})
    current_method = method_section.get("current_method", "semantic")
    method_config = next((m for m in method_section.get("methods", []) if m.get("name") == current_method), {})
    method_config["name"] = current_method

    logger.info(f"Mapper method selected: {current_method}")

    # Get chunking
    chunking_config = mapper_block.get("chunking", {})
    current_strategy = chunking_config.get("current_strategy", "page")
    strategy_config = next((c for c in chunking_config.get("strategies", []) if c.get("name") == current_strategy), {})
    strategy_config["name"] = current_strategy
    method_config["chunking"] = strategy_config

    # Get storage config
    storage_section = mapper_block.get("storage", {})
    current_storage = storage_section.get("current_storage", "local")
    storage_config = next((s for s in storage_section.get("storages", []) if s.get("name") == current_storage), {})
    storage_config["name"] = current_storage

    logger.info(f"Storage used: {current_storage}")
    logger.info(f"Chunking strategy selected: {current_strategy}")

    # Download extracted and input JSON files
    temp_extracted_path = download_to_tempfile(storage_config, key_name="extracted_key", suffix=".json")
    temp_input_json_path = download_to_tempfile(storage_config, key_name="input_json_path", suffix=".json")

    try:
        # Initialize and invoke mapper
        mapper = get_mapper_by_name(current_method, method_config, chunking_config)
        mapping_path = mapper.process_and_save(
            temp_extracted_path,
            temp_input_json_path,
            storage_config
        )
    finally:
        cleanup_temp_file(temp_extracted_path, delete=False)
        cleanup_temp_file(temp_input_json_path, delete=False)

    return {
        "message": "Field mapping completed",
        "strategy_used": current_strategy,
        "storage_used": current_storage,
        "mapping_path": mapping_path
    }
