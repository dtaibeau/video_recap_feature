from asyncio.log import logger
from fastapi import FastAPI, File, UploadFile, Form
from main import cut_video
import os

app = FastAPI()


@app.post("/cut-video/")
async def cut_video_endpoint(
    file: UploadFile = File(...),
    start_time: str = Form(...),
    end_time: str = Form(...)
    ):

    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.mkdir(upload_dir)
    # save video locally
    video_path = os.path.join(upload_dir, file.filename)

    # write as binary since video
    with open(video_path, "wb") as buffer:  # store temporarily
        buffer.write(await file.read())

    logger.info(f"Cutting video {video_path}")

    # call video cutting function
    output_path = cut_video(video_path, start_time, end_time)
    return {"message": "Video cut successfully!", "output": output_path}