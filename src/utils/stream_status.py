# src/flaskapis/stream_status.py

import os
import time
from flask import Response

def stream_status(job_id):
    status_path = f"data/jobs/{job_id}/status.log"

    def event_stream():
        last_size = 0
        while True:
            if os.path.exists(status_path):
                with open(status_path, "r") as f:
                    f.seek(last_size)
                    new_lines = f.readlines()
                    last_size = f.tell()
                    for line in new_lines:
                        yield f"data: {line.strip()}\n\n"
            time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")


def log_status(job_id, message):
    os.makedirs(f"data/jobs/{job_id}", exist_ok=True)
    with open(f"data/jobs/{job_id}/status.log", "a") as f:
        f.write(message.strip() + "\n")
        f.flush()
