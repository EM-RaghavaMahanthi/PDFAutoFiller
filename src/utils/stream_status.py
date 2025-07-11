# src/flaskapis/stream_status.py

import os
import time
from flask import Response
import asyncio
import aiofiles
from fastapi.responses import StreamingResponse



async def stream_status_async(job_id: str):
    status_path = f"data/jobs/{job_id}/status.log"

    async def event_stream():
        last_size = 0
        try:
            while True:
                if os.path.exists(status_path):
                    async with aiofiles.open(status_path, "r") as f:
                        await f.seek(last_size)
                        while True:
                            line = await f.readline()
                            if not line:
                                break
                            last_size = await f.tell()
                            yield f"data: {line.strip()}\n\n"
                await asyncio.sleep(0.1)  
        except asyncio.CancelledError:
            return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def log_status_async(job_id: str, message: str):
    log_dir = f"data/jobs/{job_id}"
    os.makedirs(log_dir, exist_ok=True)

    async with aiofiles.open(f"{log_dir}/status.log", "a") as f:
        await f.write(message.strip() + "\n")
        await f.flush()

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


async def log_status(job_id, message):
    os.makedirs(f"data/jobs/{job_id}", exist_ok=True)
    async with aiofiles.open(f"data/jobs/{job_id}/status.log", "a") as f:
        await f.write(message.strip() + "\n")
        await f.flush()
