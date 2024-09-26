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

from models import SYSTEM_PROMPT, USER_PROMPT, Soundbite, VideoTranscript, AllSoundbites, GV_WATERMARK, TRANSCRIPT_PATH
from subtitles import add_watermark, add_subtitles_to_segment, \
    create_ass_file_for_segment, match_soundbite_with_transcript, parse_transcript, format_timestamp_for_filename

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
    """
    Cuts video based on start and end timestamps.
    """
    # Format the filename to avoid invalid characters (like colons)
    formatted_start_time = format_timestamp_for_filename(start)
    formatted_end_time = format_timestamp_for_filename(end)

    # Construct the sanitized output file path using the formatted times
    sanitized_output_path = os.path.join(
        "uploads", f"segment_{formatted_start_time}_{formatted_end_time}.mp4"
    )

    logger.info(f"Cutting video from {start} to {end}. Input: {input_path}, Output: {sanitized_output_path}")

    try:
        # Run the ffmpeg command to cut the video
        ffmpeg.input(input_path, ss=start, to=end).output(sanitized_output_path, acodec='copy', vcodec='copy').run(
            overwrite_output=True)
        logger.info(f"Video successfully cut to {sanitized_output_path}")
        return sanitized_output_path
    except Exception as e:
        logger.error(f"Error cutting video: {str(e)}")
        raise


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
    """Processes video cut request by coordinating soundbite retrieval, video cutting, and merging asynchronously."""

    logger.info("PROCESSING CUT MERGE REQUEST")

    # Retrieve soundbites using the LLM
    soundbites = await retrieve_soundbites_with_llm(transcript)

    # Store the paths of processed video segments
    segment_paths = []

    # Parse full transcript to match subtitles with each segment
    transcript_segments = parse_transcript(TRANSCRIPT_PATH)

    for soundbite in soundbites:
        # Use formatted timestamps for the file names (no colons)
        formatted_start_time = format_timestamp_for_filename(soundbite.start_time)
        formatted_end_time = format_timestamp_for_filename(soundbite.end_time)

        # Construct the filename with sanitized timestamps
        segment_filename = f"segment_{formatted_start_time}_{formatted_end_time}.mp4"
        video_segment_path = os.path.join("uploads", segment_filename)
        logger.info(f"Attempting to cut video from {soundbite.start_time} to {soundbite.end_time}.")

        try:
            # Cut video based on the soundbite timestamp
            await to_thread(cut_video, video_path, soundbite.start_time, soundbite.end_time, video_segment_path)
            soundbite.file_path = video_segment_path
            logger.info(f"Successfully cut video segment: {video_segment_path}")

            # Save cut video as an artifact
            cut_video_artifact = video_segment_path.replace('.mp4', '_cut.mp4')
            os.rename(video_segment_path, cut_video_artifact)  # Renaming for clarity
            logger.info(f"Saved cut video segment for demo: {cut_video_artifact}")

        except Exception as e:
            logger.error(f"Error cutting video segment: {str(e)}")
            continue

        # Create .ass file for each segment based on the matched transcript
        segment_start_time = soundbite.start_time
        ass_file_path = os.path.join("uploads", f"subtitles_{formatted_start_time}_{formatted_end_time}.ass")
        transcript_text = match_soundbite_with_transcript(soundbite, transcript_segments)
        create_ass_file_for_segment(soundbite, transcript_text, ass_file_path, segment_start_time)

        # Add animated subtitles to the video segment using FFmpeg
        subtitled_segment_path = cut_video_artifact.replace('_cut.mp4', '_subtitled.mp4')
        await to_thread(add_subtitles_to_segment, cut_video_artifact, ass_file_path, subtitled_segment_path)
        logger.info(f"Subtitles added to video segment: {subtitled_segment_path}")

        # Save subtitled video as an artifact
        logger.info(f"Saved subtitled video segment for demo: {subtitled_segment_path}")

        # Add watermark to the subtitled video segment
        watermarked_segment_path = subtitled_segment_path.replace('_subtitled.mp4', '_watermarked.mp4')
        await to_thread(add_watermark, subtitled_segment_path, watermarked_segment_path, GV_WATERMARK)
        logger.info(f"Watermark added to video segment: {watermarked_segment_path}")

        # Save watermarked video as an artifact
        logger.info(f"Saved watermarked video segment for demo: {watermarked_segment_path}")

        # Store the processed segment path for merging later
        segment_paths.append(watermarked_segment_path)

    # Merge all watermarked segments into a single video
    try:
        merged_video_path = await to_thread(merge_segments, segment_paths)
        logger.info(f"Successfully merged all video segments into: {merged_video_path}")

        # Save the merged video as an artifact
        merged_video_artifact = merged_video_path.replace('.mp4', '_final_highlight_reel.mp4')
        os.rename(merged_video_path, merged_video_artifact)
        logger.info(f"Saved final highlight reel for demo: {merged_video_artifact}")

    except Exception as e:
        logger.error(f"Error during video merging: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to merge video segments.")

    return AllSoundbites(
        soundbites=soundbites,
        merged_video_path=merged_video_artifact
    )