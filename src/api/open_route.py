# src/routes/extract.py
from fastapi import APIRouter
from src.models.request_models import OpenFileRequest
from src.utils.logger import logger
from src.utils.render_jinja_config import render_jinja_config
import os
import subprocess

router = APIRouter()

def open_file_with_app(label: str,file_path: str, app_name: str) -> bool:
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        logger.warning(f"[!] File does not exist: {file_path}")
        return False

    try:
        subprocess.run(["open", "-a", app_name, file_path], check=True)
        logger.info(f"[✓] Opened {label} at {file_path} with {app_name}")
        return True
    except subprocess.CalledProcessError:
        logger.warning(f"[!] Failed to open {label} at {file_path} with {app_name}")
        return False

@router.post("/open")
def open_files(request: OpenFileRequest):
    config_path = request.config_path

    if not os.path.exists(config_path):
        return {"message": f"[!] Config file not found at {config_path}"}

    # Render config with variables in the request
    config = render_jinja_config(config_path, request.dict())
    fileopen_config = config.get("fileopen", {})

    if not fileopen_config.get("open", 0):
        logger.info("[i] File opening is disabled in config.")
        return {"message": "File opening is disabled in config."}

    files = fileopen_config.get("files", {})
    apps = fileopen_config.get("apps", {})
    opened_files = []

    for label, path in files.items():
        abs_path = os.path.abspath(os.path.expandvars(path))

        if not os.path.exists(abs_path):
            logger.warning(f"[!] File for '{label}' does not exist: {abs_path}")
            continue

        ext = os.path.splitext(abs_path)[1].lower().lstrip(".")
        app_name = apps.get(ext)

        if not app_name:
            logger.info(f"[i] No app configured for '.{ext}' (label: {label}). Skipping.")
            continue

        success = open_file_with_app(label, abs_path, app_name)
        if success:
            opened_files.append({label: abs_path})

    return {
        "message": "File opening completed.",
        "opened_files": opened_files
    }
