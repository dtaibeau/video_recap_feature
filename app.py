from loguru import logger
from typing import List
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from main import cut_video, merge_segments
import os

app = FastAPI()

UPLOAD_DIR = "uploads"


@app.post("/cut-video/")
async def cut_video_endpoint(
    file: UploadFile = File(...),
    start_times: List[str] = Form(...),
    end_times: List[str] = Form(...)
):

    if len(start_times) != len(end_times):
        logger.error("Start times and end times must have the same length")
        raise HTTPException(status_code=400, detail="Start times and end times must have the same length")

    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.mkdir(upload_dir)

    # save video locally
    video_path = os.path.join(UPLOAD_DIR, f"{uuid4()}.mp4")

    # write as binary since video
    with open(video_path, "wb") as buffer:  # store temporarily
        buffer.write(await file.read())

    logger.info(f"Cutting video {video_path}")

    # cut video segments
    video_segment_paths = []
    for i, (start_time, end_time) in enumerate(zip(start_times, end_times)):
        video_segment_path = f"uploads/segment_{i}_{start_time.replace(':', '-')}_{end_time.replace(':', '-')}.mp4"
        cut_video(video_path, start_time, end_time, video_segment_path)
        video_segment_paths.append(video_segment_path)

    merged_video_path = merge_segments(video_segment_paths)

    return {"message": "Video cut and merged successfully!", "output": merged_video_path}