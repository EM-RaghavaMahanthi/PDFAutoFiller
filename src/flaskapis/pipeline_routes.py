# src/flaskapis/pipeline_routes.py

import os
import uuid
from flask import Blueprint, request, jsonify
from threading import Thread
from src.utils.job_manager import create_job, save_uploaded_file
from src.flaskapis.pipeline_runner import run_pipeline
from flask import send_file
from flask_cors import cross_origin


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
        return send_file(
            filled_pdf_path,
            as_attachment=True,
            download_name=f"filled_{job_id}.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        return jsonify({"error": f"Failed to send file: {str(e)}"}), 500

