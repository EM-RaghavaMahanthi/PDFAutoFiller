import os
from src.mappers import get_mapper_by_name
from src.utils.stream_status import log_status

async def run_map_stage(job_id: str, pipeline_config: dict):
    log_status(job_id, "[🧠] Starting mapping...")

    job_dir = f"data/jobs/{job_id}"
    extracted_path = os.path.join(job_dir, "extracted.json")
    input_json_path = os.path.join(job_dir, "input.json")
    input_pdf_path = os.path.join(job_dir, "input.pdf")
    key_variants_path = os.path.join(job_dir, "input_key_variants.json")
    field_name_variants_path = os.path.join(job_dir, "field_name_variants.json")

    # Get mapper config
    mapper_block = pipeline_config.get("mapper", {})
    method_block = mapper_block.get("method", {})
    current_method = method_block.get("current_method", "semantic")
    method_config = next((m for m in method_block.get("methods", []) if m.get("name") == current_method), {})
    method_config["name"] = current_method

    # Get chunking config
    chunking_config = mapper_block.get("chunking", {})
    current_strategy = chunking_config.get("current_strategy", "page")
    strategy_config = next((c for c in chunking_config.get("strategies", []) if c.get("name") == current_strategy), {})
    strategy_config["name"] = current_strategy
    method_config["chunking"] = strategy_config


    log_status(job_id, f"[⚙️] Mapper method: {current_method}")
    log_status(job_id, f"[⚙️] Chunking strategy: {current_strategy}")
    log_status(job_id, f"[⚙️] llm used: {method_config["llm"]}")

    try:
        mapper = get_mapper_by_name(current_method, method_config, chunking_config)
        await mapper.process_and_save(
            extracted_path,
            input_json_path,
            input_pdf_path,
            {"output_path": os.path.join(job_dir, "mapped.json"),"radio_groups":os.path.join(job_dir, "radio_groups.json")},
            key_variants_path,
            field_name_variants_path
        )
        log_status(job_id, "[✅] Mapping completed.")
    except Exception as e:
        log_status(job_id, f"[❌] Mapping failed: {str(e)}")
        raise
