from fastapi import APIRouter
from src.models.request_models import MapFieldsRequest
from src.mappers.direct_mapper import SemanticMapper
from src.llm.llm_selector import LLMSelector
from src.utils.logger import logger
import yaml

router = APIRouter()

@router.post("/map-fields")
def map_fields(request: MapFieldsRequest):
    with open("pipeline_config.yaml", "r") as f:
        pipeline_config = yaml.safe_load(f)

    mapper_config = pipeline_config.get("mapper", {})
    LLM_NAME = mapper_config.get("LLM", "claude")

    chunking_config = mapper_config.get("chunking", {})
    current_strategy = chunking_config.get("current_strategy", "page")
    strategy_list = chunking_config.get("strategies", [])

    selected_strategy_config = next(
        (cfg for cfg in strategy_list if cfg.get("name") == current_strategy),
        {}
    )
    selected_strategy_config["name"] = current_strategy

    logger.info(f"LLM used: {LLM_NAME}")
    logger.info(f"Chunking strategy selected: {current_strategy}")

    pdf_path = request.pdf_path
    input_json_path = request.input_json_path

    llm_selector = LLMSelector(provider=LLM_NAME)
    llm = llm_selector.llm

    mapper = SemanticMapper(llm, config=selected_strategy_config)
    mapping_path = mapper.process_and_save(pdf_path, input_json_path)

    return {
        "message": "Field mapping completed",
        "strategy_used": current_strategy,
        "mapping_path": mapping_path
    }
