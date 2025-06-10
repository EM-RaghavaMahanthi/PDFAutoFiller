# src/flaskapis/job_manager.py

import os
import uuid

def create_job():
    job_id = str(uuid.uuid4())
    job_dir = f"data/jobs/{job_id}"
    os.makedirs(job_dir, exist_ok=True)
    return job_id, job_dir

def get_job_dir(job_id):
    return f"data/jobs/{job_id}"

def save_uploaded_file(file, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)
