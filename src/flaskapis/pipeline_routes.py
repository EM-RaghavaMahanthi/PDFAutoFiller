# src/flaskapis/pipeline_routes.py

import os
import uuid
from flask import Blueprint, request, jsonify
from threading import Thread
from src.utils.job_manager import create_job, save_uploaded_file
from src.flaskapis.pipeline_runner import run_pipeline
from flask import send_file
from werkzeug.utils import secure_filename
from flask_cors import cross_origin
from src.validations.embed_validator import EmbedValidator
from src.utils.stream_status import log_status


pipeline_bp = Blueprint("pipeline", __name__)

@pipeline_bp.route("/start", methods=["POST"])
@cross_origin()

def start_pipeline():

    if "input_pdf" not in request.files or "input_json" not in request.files:
        return jsonify({"error": "Both input_pdf and input_json are required."}), 400

    job_id, job_dir = create_job()

    # Save both files
    save_uploaded_file(request.files["input_pdf"], os.path.join(job_dir, "input.pdf"))
    save_uploaded_file(request.files["input_json"], os.path.join(job_dir, "input.json"))

    # Start pipeline in background thread
    thread = Thread(target=run_pipeline, args=(job_id,))
    thread.start()

    return jsonify({"job_id": job_id})

@pipeline_bp.route("/download/<job_id>", methods=["GET"])
def download_filled_pdf(job_id):
    """
    Download the final filled PDF after the pipeline finishes.
    """
    job_dir = os.path.join(os.getcwd(), "data", "jobs", job_id)
    filled_pdf_path = os.path.join(job_dir, "filled_output.pdf")

    if not os.path.exists(filled_pdf_path):
        return jsonify({"error": f"Filled PDF not found for job ID: {job_id}"}), 404

    try:
        preview_mode = request.args.get("preview") == "1"
        return send_file(
            filled_pdf_path,
            as_attachment=not preview_mode,
            download_name=f"filled_{job_id}.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        return jsonify({"error": f"Failed to send file: {str(e)}"}), 500


@pipeline_bp.route("/validate/<job_id>", methods=["POST"])
@cross_origin()
def validate_pdf(job_id):
    try:
        if "validation_pdf" not in request.files:
            return jsonify({"error": "Missing validation_pdf file"}), 400

        validation_pdf = request.files["validation_pdf"]
        if validation_pdf.filename == "":
            return jsonify({"error": "Empty filename for validation_pdf"}), 400

        job_dir = os.path.join(os.getcwd(), "data", "jobs", job_id)
        if not os.path.exists(job_dir):
            return jsonify({"error": f"Invalid job ID: {job_id}"}), 404

        validation_path = os.path.join(job_dir, secure_filename(validation_pdf.filename))
        validation_pdf.save(validation_path)

        embed_pdf_path = os.path.join(job_dir, "embedded_output.pdf")
        if not os.path.exists(embed_pdf_path):
            return jsonify({"error": f"Embedded PDF not found for job ID: {job_id}"}), 404

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
        return jsonify({
            "status": "success",
            "csv_path": f"/download/{job_id}?file=validation_stats.csv",
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records")
        })
        
    except Exception as e:
        return jsonify({"[❌] error": str(e)}), 500
