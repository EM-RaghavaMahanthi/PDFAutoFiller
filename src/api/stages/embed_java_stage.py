import os
import subprocess
from src.utils.stream_status import log_status

async def run_embed_java_stage(job_id: str, pipeline_config: dict):
    await log_status(job_id, "[🧩] Rebuilding PDF form using Java utility...")

    job_dir = f"data/jobs/{job_id}"
    original_pdf = os.path.join(job_dir, "input.pdf")
    extracted_json = os.path.join(job_dir, "extracted.json")
    mapping_json = os.path.join(job_dir, "mapped.json")
    radio_json = os.path.join(job_dir, "radio_groups.json")
    rebuilt_pdf = os.path.join(job_dir, "embedded_output.pdf")

    jar_path = "rebuilder.jar"

    # Validate files
    for path in [original_pdf, extracted_json, mapping_json]:
        if not os.path.exists(path):
            await log_status(job_id, f"[❌] Missing required file for Java stage: {path}")
            raise FileNotFoundError(f"Missing required file: {path}")

    # Build and run command
    cmd = [
        "java", "-jar", jar_path,
        original_pdf,
        extracted_json,
        mapping_json,
        radio_json,
        rebuilt_pdf
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        await log_status(job_id, "[✅] Java embedding completed successfully.")
    except subprocess.CalledProcessError as e:
        await log_status(job_id, f"[❌] Java embedding failed: {e.stderr.strip()}")
        raise RuntimeError("Java embedding step failed") from e
