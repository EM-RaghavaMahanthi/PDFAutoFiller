import os
from src.fillers import get_filler_by_name
from src.utils.stream_status import log_status

def run_fill_stage(job_id: str, pipeline_config: dict):
    log_status(job_id, "[✍️] Starting PDF fill stage...")

    job_dir = f"data/jobs/{job_id}"

    input_pdf_path = os.path.join(job_dir, "embedded_output.pdf")  # comes from Java
    extracted_path = os.path.join(job_dir, "extracted.json")
    mapping_path = os.path.join(job_dir, "mapped.json")
    input_json_path = os.path.join(job_dir, "input.json")
    output_pdf_path = os.path.join(job_dir, "filled_output.pdf")

    # Get filler config
    filler_block = pipeline_config.get("filler", {})
    method_block = filler_block.get("method", {})
    current_method = method_block.get("current_method", "fitz")
    method_config = next((m for m in method_block.get("methods", []) if m.get("name") == current_method), {})
    method_config["name"] = current_method

    log_status(job_id, f"[⚙️] Filler method selected: {current_method}")

    try:
        filler = get_filler_by_name(current_method, method_config)

        result = filler.fill_pdf(
            pdf_path=input_pdf_path,
            embed_pdf_path=input_pdf_path,  # reuse rebuilt.pdf if needed
            input_json_path=input_json_path,
            extracted_path=extracted_path,
            mapping_path=mapping_path,
            storage_config={"output_file": output_pdf_path}
        )

        log_status(job_id, f"[✅] Filling completed. Fields filled: {result.get('filled_fields', '?')}")
        log_status(job_id, "Done filling.")
    except Exception as e:
        log_status(job_id, f"[❌] Filling failed: {str(e)}")
        raise
