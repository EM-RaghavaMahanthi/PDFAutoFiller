import os
from src.extractors import get_extractor_by_name
from src.utils.stream_status import log_status

def run_extract_stage(job_id: str, pipeline_config: dict):
    log_status(job_id, "[📄] Starting extraction...")

    job_dir = f"data/jobs/{job_id}"
    input_pdf_path = os.path.join(job_dir, "input.pdf")
    output_json_path = os.path.join(job_dir, "extracted.json")

    # Get extractor method from config
    extractor_block = pipeline_config.get("extractor", {})
    method_block = extractor_block.get("method", {})
    current_method = method_block.get("current_method", "fitz")
    method_config = next(
        (m for m in method_block.get("methods", []) if m.get("name") == current_method),
        {}
    )

    log_status(job_id, f"[⚙️] Extractor method: {current_method}")

    try:
        extractor = get_extractor_by_name(current_method, method_config)
        storage_config = {"name": "local", "output_path": output_json_path}

        extracted_data = extractor.extract(input_pdf_path, storage_config)
        log_status(job_id, "[✅] Extraction completed.")
    except Exception as e:
        log_status(job_id, f"[❌] Extraction failed: {str(e)}")
        raise
