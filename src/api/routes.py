from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from src.utils.job_manager import create_job, save_uploaded_file_async
from src.api.pipeline_runner_async import run_pipeline_async
from src.utils.stream_status import stream_status_async
from src.validations.embed_validator import EmbedValidator
from src.utils.stream_status import log_status
import os
import asyncio
import pandas as pd

router = APIRouter()


@router.get("/stream/{job_id}")
async def stream_logs(job_id: str):
    return await stream_status_async(job_id)

@router.post("/start")
async def start_pipeline(input_pdf: UploadFile = File(...), input_json: UploadFile = File(...)):
    job_id, job_dir = create_job()

    await save_uploaded_file_async(input_pdf, os.path.join(job_dir, "input.pdf"))
    await save_uploaded_file_async(input_json, os.path.join(job_dir, "input.json"))

    log_status(job_id, "[✓] Uploaded PDF and JSON")
    # Run async pipeline in background
    asyncio.create_task(run_pipeline_async(job_id))
    return {"job_id": job_id}

@router.get("/download/{job_id}")
async def download_filled_pdf(job_id: str, preview: str = "0"):
    job_dir = os.path.join(os.getcwd(), "data", "jobs", job_id)
    filled_pdf_path = os.path.join(job_dir, "filled_output.pdf")

    if not os.path.exists(filled_pdf_path):
        return JSONResponse(status_code=404, content={"error": f"Filled PDF not found for job ID: {job_id}"})

    as_attachment = preview != "1"
    return FileResponse(filled_pdf_path, filename=f"filled_{job_id}.pdf", media_type="application/pdf", headers={"Content-Disposition": "attachment" if as_attachment else "inline"})

@router.post("/validate/{job_id}")
async def validate_pdf(job_id: str, validation_pdf: UploadFile = File(...)):
    try:
        job_dir = os.path.join(os.getcwd(), "data", "jobs", job_id)
        if not os.path.exists(job_dir):
            return JSONResponse(status_code=404, content={"error": f"Invalid job ID: {job_id}"})

        validation_path = os.path.join(job_dir, validation_pdf.filename)
        contents = await validation_pdf.read()
        with open(validation_path, "wb") as f:
            f.write(contents)

        embed_pdf_path = os.path.join(job_dir, "embedded_output.pdf")
        if not os.path.exists(embed_pdf_path):
            return JSONResponse(status_code=404, content={"error": f"Embedded PDF not found for job ID: {job_id}"})

        storage_config = {
            "type": "local",
            "output_file": os.path.join(job_dir, "validation_stats.csv")
        }

        validator = EmbedValidator({})
        df = validator.validate(
            validation_path=validation_path,
            mapping_path=embed_pdf_path,
            storage_config=storage_config
        )
        log_status(job_id, f"[✅] Embed validation complete")

        return {
            "status": "success",
            "csv_path": f"/download/{job_id}?file=validation_stats.csv",
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records")
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
