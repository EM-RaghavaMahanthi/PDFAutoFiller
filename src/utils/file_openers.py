import os
import subprocess
from src.utils.logger import logger

def open_app(file_path: str, app_name: str):
    """
    Opens a file with a specified macOS application using `open -a`.

    Args:
        file_path (str): Path to the file to open
        app_name (str): Name of the macOS app to open it with (e.g., "Adobe Acrobat Reader")

    Example:
        open_app("sample.pdf", "Adobe Acrobat Reader")
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        print(f"[!] File does not exist: {file_path}")
        return

    try:
        subprocess.run(["open", "-a", app_name, file_path], check=True)
        print(f"[✓] Opened {file_path} with {app_name}")
    except subprocess.CalledProcessError:
        print(f"[!] Failed to open {file_path} with {app_name}. Is the app installed?")
