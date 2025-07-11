import os
import subprocess
from src.utils.stream_status import log_status

import asyncio


async def fill_with_java(job_id: str, pipeline_config: dict):
    await log_status(job_id, "[🧩] Filling PDF form using Java Itext...")

    job_dir = f"data/jobs/{job_id}"
    original_pdf = os.path.join(job_dir, "embedded_output.pdf")
    input_json = os.path.join(job_dir, "input.json")
    filled_pdf = os.path.join(job_dir, "filled_output.pdf")

    jar_path = "filler.jar"

    # Validate files
    for path in [original_pdf, input_json]:
        if not os.path.exists(path):
            await log_status(job_id, f"[❌] Missing required file for Java stage: {path}")
            raise FileNotFoundError(f"Missing required file: {path}")

    # Build and run command
    cmd = [
        "java", "-jar", jar_path,
        original_pdf,
        input_json,
        filled_pdf
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        await log_status(job_id, "[✅] Filling pdf completed successfully.")
        await log_status(job_id, result.stdout.strip())
    except subprocess.CalledProcessError as e:
        await log_status(job_id, f"[❌] Java Filling failed: {e.stderr.strip()}")
        raise RuntimeError("Java Filling step failed") from e
