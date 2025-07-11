import os
import yaml
from jinja2 import Template
from src.utils.stream_status import log_status
from src.utils.job_manager import get_job_dir

# Import updated async-compatible stages
from src.api.stages.extract_stage import run_extract_stage
from src.api.stages.map_stage import run_map_stage
from src.api.stages.embed_java_stage import run_embed_java_stage
from src.api.stages.fill_with_java import fill_with_java
from src.api.stages.fill_stage import run_fill_stage

import traceback

def render_jinja_config(template_path: str, context: dict) -> dict:
    with open(template_path, 'r') as f:
        template = Template(f.read())
    rendered_yaml = template.render(**context)
    return yaml.safe_load(rendered_yaml)

async def run_pipeline_async(job_id: str):
    job_dir = get_job_dir(job_id)
    input_config_path = "input_config.yaml.j2"
    context = {"job_dir": job_dir}
    pipeline_config = render_jinja_config(input_config_path, context)

    try:
        await log_status(job_id, "[🚀] Starting pipeline...")

        # Step 1: Extract
        await log_status(job_id, "[🔍] Extracting fields from PDF...")
        await run_extract_stage(job_id, pipeline_config)

        # Step 2: Map (async)
        await log_status(job_id, "[🧠] Running LLM-based mapping...")
        await run_map_stage(job_id, pipeline_config)

        # Step 3: Embed Java
        await log_status(job_id, "[📎] Embedding fields into PDF using Java...")
        await run_embed_java_stage(job_id, pipeline_config)

        # Step 4: Fill
        await log_status(job_id, "[✍️] Filling final PDF with values...")
        await fill_with_java(job_id, pipeline_config)

        #run_fill_stage(job_id, pipeline_config)

        await log_status(job_id, "[✅] Pipeline completed successfully.")

    except Exception as e:
        await log_status(job_id, f"[❌] Pipeline failed: {str(e)}")
        traceback.print_exc()
