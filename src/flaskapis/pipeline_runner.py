# src/flaskapis/pipeline_runner.py

import os
import yaml
from jinja2 import Template
from src.utils.stream_status import log_status
from src.utils.job_manager import get_job_dir
from src.flaskapis.stages.extract_stage import run_extract_stage
from src.flaskapis.stages.map_stage import run_map_stage
from src.flaskapis.stages.embed_java_stage import run_embed_java_stage
from src.flaskapis.stages.fill_stage import run_fill_stage

def render_jinja_config(template_path: str, context: dict) -> dict:
    with open(template_path, 'r') as f:
        template = Template(f.read())
    rendered_yaml = template.render(**context)
    return yaml.safe_load(rendered_yaml)

def run_pipeline(job_id: str):
    job_dir = get_job_dir(job_id)
    input_config_path = "input_config.yaml.j2"

    # Render config once
    context = {"job_dir": job_dir}
    pipeline_config = render_jinja_config(input_config_path, context)

    log_status(job_id, "[🚀] Starting pipeline...")

    # Step 1: Extract
    run_extract_stage(job_id, pipeline_config)

    # Step 2: Map
    run_map_stage(job_id, pipeline_config)

    # Step 3: Java Util
    run_embed_java_stage(job_id, pipeline_config)

    # # Step 4: Fill
    run_fill_stage(job_id, pipeline_config)

    log_status(job_id, "[✅] Pipeline completed successfully.")
