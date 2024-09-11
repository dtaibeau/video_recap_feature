from loguru import logger
from typing import List
from uuid import uuid4
from datetime import datetime, time
import pytest

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel

from main import cut_video, merge_segments
import os

app = FastAPI()

UPLOAD_DIR = "uploads"


class VideoCutRequest(BaseModel):
    start_times: List[time]
    end_times: List[time]


# def validate_time_input_format(request: VideoCutRequest):
#     try:
#         datetime.strptime(request, '%H:%M:%S')
#     except ValueError:
#         raise HTTPException(status_code=400, detail=f"Invalid time for format: {time_str}")


@app.post("/cut-video/")
async def cut_video_endpoint(
    file: UploadFile = File(...),
    start_times: List[time] = Form(...),
    end_times: List[time] = Form(...)
):
    # validate input file
    if file.content_type != "video/mp4":
        raise HTTPException(status_code=400, detail="Only video/mp4 is supported")

    if len(start_times) != len(end_times):
        logger.error("Start times and end times must have the same length")
        raise HTTPException(status_code=400, detail="Start times and end times must have the same length")

    validated_request = VideoCutRequest(start_times=start_times, end_times=end_times)

    if not os.path.exists(UPLOAD_DIR):
        os.mkdir(UPLOAD_DIR)

    # save video locally
    video_path = os.path.join(UPLOAD_DIR, f"{uuid4()}.mp4")
    with open(video_path, "wb") as buffer:  # store temporarily
        buffer.write(await file.read())

    logger.info(f"Cutting video {video_path}")

    # cut video segments
    video_segment_paths = []
    for i, (start_time, end_time) in enumerate(zip(validated_request.start_times, validated_request.end_times)):
        segment_file_name = f"segment_{i}_{start_time.strftime('%H-%M-%S')}_{end_time.strftime('%H-%M-%S')}.mp4"
        video_segment_path = os.path.join(UPLOAD_DIR, segment_file_name)
        cut_video(video_path, start_time.strftime('%H:%M:%S'), end_time.strftime('%H:%M:%S'), video_segment_path)
        video_segment_paths.append(video_segment_path)

    merged_video_path = merge_segments(video_segment_paths)

    return {"message": "Video cut and merged successfully!", "output": merged_video_path}