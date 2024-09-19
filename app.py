import openai
from loguru import logger
from uuid import uuid4
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pytube import YouTube

from main import process_video_cut_request, VideoTranscript, TranscriptSegment
import os

app = FastAPI()

UPLOAD_DIR = "uploads"


def format_time(seconds):
    """Format seconds to hh:mm:ss"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


# get transcript
def parse_transcript(file_content: str) -> VideoTranscript:
    """Parse tactiq.io transcript from .txt into VideoTranscript"""
    segments = []

    for line in file_content.splitlines():
        if line.strip() and not line.startswith("#") and not "youtube.com" in line:
            timestamp, text = line.split(" ", 1)
            segments.append(TranscriptSegment(start_time=timestamp.strip(), text=text.strip()))

    return VideoTranscript(segments=segments)


@app.post("/cut-video/")
async def cut_video_endpoint(transcript_file: UploadFile = File(...)):
    """Endpoint to handle video cutting based on the uploaded transcript file."""
    if not os.path.exists(UPLOAD_DIR):
        os.mkdir(UPLOAD_DIR)

    video_path = os.path.join(UPLOAD_DIR, "sample.mp4")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    logger.info(f"Using local video file: {video_path}")

    # read and parse the transcript file
    try:
        transcript_data = await transcript_file.read()
        transcript_content = transcript_data.decode("utf-8")
        transcript_model = parse_transcript(transcript_content)
    except Exception as e:
        logger.error(f"Error parsing transcript file: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse transcript file")

    # cut and merge
    try:
        video_cut_response = await process_video_cut_request(video_path, transcript_model)
    except HTTPException as e:
        logger.error(f"Error during video processing: {e}")
        raise e

    return {
        "message": "Video processed successfully!",
        "merged_output": video_cut_response.merged_video_path,
        "summary": video_cut_response.summary
    }




