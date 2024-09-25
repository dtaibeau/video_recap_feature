from typing import List
import numpy as np
from PIL import Image
from moviepy.video.VideoClip import ImageClip
from moviepy.video.fx.resize import resize
from moviepy.editor import VideoFileClip, CompositeVideoClip
import moviepy.editor as mp

import ffmpeg
from loguru import logger

from main import Soundbite
import os

from models import GV_WATERMARK, MERGED_VIDEO_WITH_ST, MERGED_VIDEO_WITH_WATERMARK

logger.info(os.path.exists("uploads/sample.mp4"))
logger.info(os.path.exists("uploads/subtitles.srt"))


def add_watermark(video_path: str, output_path: str, watermark_path: str):
    """
    Adds a PNG watermark to the video using FFmpeg"""
    logger.info("Starting to add watermark to video...")

    try:
        command = (
            f"ffmpeg -i {video_path} -i {watermark_path} "
            f"-filter_complex \"[1][0]scale2ref=w=iw*0.2:h=ow/mdar[wm][base];[base][wm]overlay=W-w-10:H-h-10:"
            f"format=auto,format=yuv420p[watermark];[watermark]lut=a='val*0.5'\" "
            f"-c:v libx264 -c:a copy {output_path} -y"
        )

        logger.info(f"Running command: {command}")
        os.system(command)
        logger.info(f"Watermark added successfully to {output_path}")

    except Exception as e:
        logger.error(f"Error adding watermark: {str(e)}")
        raise


# def add_watermark(video_path: str, output_path: str, watermark_path: str):
#     """Adds a PNG watermark to the video using MoviePy"""
#     logger.info("Starting to add watermark to video...")
#     try:
#         video = mp.VideoFileClip(video_path)
#
#
#         watermark = (mp.ImageClip(watermark_path)
#                 .set_duration(video.duration)
#                 .resize(height=50)
#                 .set_opacity(0.8)
#                 .set_pos("center"))
#
#         final = mp.CompositeVideoClip([video, watermark])
#
#         final.write_videofile(output_path, codec="libx264", audio_codec="aac")
#
#         logger.info(f"Watermark added successfully to {output_path}")
#     except Exception as e:
#         logger.error(f"Error adding watermark: {str(e)}")
#         raise


def add_subtitles(video_path: str, subtitles_path: str, output_path: str) -> str:
    """Adds subtitles to a video using an SRT file"""
    logger.info(f"adding watermark to video")

    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles={subtitles_path}")
            .run(overwrite_output=True)
        )

        if os.path.exists(output_path):
            logger.info(f"Subtitles video successfully created at {output_path}")
            return output_path
        else:
            raise FileNotFoundError("Failed to create subtitled video")
    except Exception as e:
        logger.error(f"Error adding subtitles: {str(e)}")
        raise


def create_srt_file(soundbites: List[Soundbite], subtitles_path: str):
    """Creates SRT file based on provided soundbites data"""
    with open(subtitles_path, "w") as srt_file:
        for index, soundbite in enumerate(soundbites, start=1):
            start_time = soundbite.start_time.replace('.', ',')
            end_time = soundbite.end_time.replace('.', ',')

            srt_file.write(f"{index}\n")
            srt_file.write(f"{start_time} --> {end_time}\n")
            srt_file.write(f"{soundbite.text}\n\n")


def format_time(seconds):
    """Convert seconds to hh:mm:ss,ms format for SRT file"""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"





