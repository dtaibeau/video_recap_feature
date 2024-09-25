import os
from asyncio import to_thread
from datetime import datetime
from typing import List
from uuid import uuid4
import ffmpeg
import openai
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from fastapi import HTTPException
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from models import SYSTEM_PROMPT, USER_PROMPT, Soundbite, VideoTranscript, AllSoundbites, GV_WATERMARK
from subtitles import create_srt_file, add_subtitles, add_watermark


### SETUP ###


load_dotenv(".env")

openai.api_key = os.getenv('OPENAI_API_KEY')

llm = ChatOpenAI(model="gpt-4o", temperature=0)


### CHAINING ###

prompt = ChatPromptTemplate.from_messages([SYSTEM_PROMPT, USER_PROMPT])

structured_llm = llm.with_structured_output(AllSoundbites)

chain = (prompt | structured_llm.with_config({"run_name": "soundbite_selection"}))


### SOUNDBITE RETRIEVAL ###

async def retrieve_soundbites_with_llm(transcript: VideoTranscript) -> List[Soundbite]:
    """Retrieve soundbites from a video and transcript using LLM."""
    logger.info("RETRIEVING SOUNDBITES FROM LLM")

    response = await chain.ainvoke({"transcript": transcript})

    logger.info(f"LLM response: {response}")

    try:

        soundbites = []

        for item in response.soundbites:
            if isinstance(item, Soundbite):
                soundbites.append(item)
            else:
                logger.error(f"Unexpected type in response: {type(item)}")
                raise HTTPException(status_code=500, detail=f"Unexpected response type: {type(item)}")

        return soundbites
    except Exception as e:
        logger.error(f"Error processing LLM response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")


### VIDEO CUTTING ###

def cut_video(input_path: str, start: str, end: str, output_path: str) -> str:
    """Cuts video based on start and end timestamps"""
    logger.info("ATTEMPTING TO CUT VIDEO")

    try:
        if os.path.getsize(input_path) == 0:
            raise HTTPException(status_code=500, detail="File is empty.")

        logger.info(f"Cutting video from {start} to {end}. Input: {input_path}, Output: {output_path}")

        ffmpeg.input(input_path, ss=start, to=end).output(output_path, acodec='copy', vcodec='copy').run()

        if os.path.exists(output_path):
            logger.info(f"Video successfully cut to {output_path}")
        else:
            logger.error(f"Failed to cut video to {output_path}")
            raise HTTPException(status_code=500, detail="Failed to cut video.")

        return output_path
    except Exception as e:
        logger.error(f"Error during video cutting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"FFmpeg error: {str(e)}")


### MERGING ###

def merge_segments(segment_paths: List[str]) -> str:
    """Merges video based on list of cut segments' paths"""
    logger.info("ATTEMPTING TO MERGE VIDEO")
    if not segment_paths:
        raise ValueError("No segments provided for merging.")

    list_file = f"uploads/{uuid4()}.txt"
    merged_output = f"uploads/merged_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    try:
        with open(list_file, "w") as f:
            for segment in segment_paths:
                if os.path.exists(segment):
                    f.write(f"file '{os.path.abspath(segment)}'\n")
                else:
                    logger.error(f"Segment does not exist: {segment}")

        # merge
        ffmpeg.input(list_file, format='concat', safe=0).output(merged_output, c='copy').run()

        if os.path.exists(merged_output):
            logger.info(f"Videos merged successfully to {merged_output}")
        else:
            logger.error(f"Failed to merge videos to {merged_output}")
            raise HTTPException(status_code=500, detail="Failed to merge video segments.")

    except Exception as e:
        logger.error(f"Error merging segments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error merging segments: {str(e)}")

    finally:
        if os.path.exists(list_file):
            os.remove(list_file)
        for segment in segment_paths:
            if os.path.exists(segment):
                os.remove(segment)

    return merged_output


### CUTTING + MERGING ###

async def process_video_cut_request(video_path: str, transcript: VideoTranscript) -> AllSoundbites:
    """Processes video cut request by coordinating soundbite retrieval, video cutting, and merging asynchronously"""
    logger.info("PROCESSING CUT MERGE REQUEST")

    soundbites = await retrieve_soundbites_with_llm(transcript)

    segment_paths = []

    for soundbite in soundbites:
        segment_filename = f"segment_{soundbite.start_time}_{soundbite.end_time}.mp4"
        video_segment_path = os.path.join("uploads", segment_filename)

        logger.info(f"Attempting to cut video from {soundbite.start_time} to {soundbite.end_time}.")

        try:
            # cut video
            await to_thread(cut_video, video_path, soundbite.start_time, soundbite.end_time, video_segment_path)
            segment_paths.append(video_segment_path)

            # update soundbite with filepath post cut
            soundbite.file_path = video_segment_path
            logger.info(f"Successfully cut video segment: {video_segment_path}")
        except Exception as e:
            logger.error(f"Error cut video segment: {str(e)}")

    try:
        merged_video_path = await to_thread(merge_segments, segment_paths)
    except Exception as e:
        logger.error(f"Error during video merging: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to merge video segments.")

    # create SRT file
    subtitles_path = os.path.join("uploads", "subtitles.srt")
    create_srt_file(soundbites, subtitles_path)

    # add subtitles to merged video
    os.system(f"ffmpeg -i {merged_video_path} -vf subtitles={subtitles_path} /Users/dtaibeau/Documents/Gigaverse"
              f"/ffmpeg_testing/uploads/merged_vid_with_subtitles.mp4")

    output_path = os.path.join("uploads", "merged_vid_with_subtitles.mp4")

    watermark_path = GV_WATERMARK

    final_output_path = os.path.join("uploads", "merged_vid_with_watermark_and_subtitles.mp4")

    add_watermark(output_path, final_output_path, watermark_path)

    return AllSoundbites(
        soundbites=soundbites,
        merged_video_path=final_output_path
    )

