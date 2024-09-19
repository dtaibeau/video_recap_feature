import os
import re
from asyncio import to_thread
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import ffmpeg
import openai
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from fastapi import HTTPException
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, \
    ChatPromptTemplate
from loguru import logger
from pydantic import ValidationError
from pydantic.v1 import BaseModel, Field


### SETUP ###

load_dotenv(".env")

openai.api_key = os.getenv('OPENAI_API_KEY')

llm = ChatOpenAI(model="gpt-4o", temperature=0)


# pydantic models
class TranscriptSegment(BaseModel):
    """Data model for a transcript segment from Tactiq.io"""
    start_time: str
    text: str


class VideoTranscript(BaseModel):
    """Data model for the entire transcript from Tactiq.io"""
    segments: List[TranscriptSegment]


class Soundbite(BaseModel):
    """Data model for individual soundbite and validation of timestamp + segment text"""
    start_time: str = Field(..., regex=r'\d{2}:\d{2}:\d{2}(\.\d{1,3})?')
    end_time: str = Field(..., regex=r'\d{2}:\d{2}:\d{2}(\.\d{1,3})?')
    text: str
    file_path: Optional[str] = None
    reasoning: Optional[str] = None  # llm reasoning for selecting particular soundbite


class AllSoundbites(BaseModel):
    """Data model for all soundbites"""
    soundbites: List[Soundbite]
    summary: str
    merged_video_path: Optional[str] = None


# PROMPT_TEMPLATE = """
#     Here is a transcript: {transcript}. Your task is to select the most meaningful soundbites from the transcript.
#     Each soundbite should represent a key idea or important moment in the conversation that would resonate with an audience.
#
#     Here are the specific instructions:
#     1. Select 10 different windows in the transcript that are each between **30 to 60 seconds** long.
#     2. Each window must contain at least one complete sentence or idea, and should not cut off mid-sentence.
#     3. For each soundbite, add an extra 30 seconds to 1 minute of context around it to ensure natural start and end points without abrupt cuts.
#     4. For each soundbite, provide the following information:
#        - Start time (hh:mm:ss)
#        - End time (hh:mm:ss)
#        - The soundbite text
#        - A brief explanation of why you selected that soundbite and why it is meaningful in the context of the conversation.
#
#     Return the results in this format:
#     1. Start: [start_time], End: [end_time]
#        "Soundbite text"
#        Reason: [reason for choosing this soundbite]
#
#     If you need to extend the soundbite to include more context, do so within the 30-second to 1-minute boundary.
#     """

SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template(
    """You are an expert in analyzing video transcripts. Your task is to identify the 10 most meaningful 
    soundbites based on the context of the conversation. For each soundbite, you must provide the start and 
    end times, the corresponding text, and reasoning for why the soundbite is meaningful. Each soundbite should 
    be between 5 and 10 seconds long."""
)


USER_PROMPT = HumanMessagePromptTemplate.from_template(
    """Here is a transcript: {transcript}. Your task is to select exactly 10 meaningful soundbites from the transcript.
    Each soundbite should represent a key idea or important moment in the conversation that would resonate with an audience.

    Here are the specific instructions:
    1. Select 10 different soundbites from the transcript. Each soundbite must be **5 to 10 seconds** long.
    2. Each soundbite should cover one or more complete ideas, and should not cut off mid-sentence.
    3. Provide for each soundbite:
       - Start time (hh:mm:ss)
       - End time (hh:mm:ss)
       - The soundbite text
       - A brief explanation of why you selected that soundbite and why it is meaningful.
       
    Return the soundbites in this format:
    1. Start: [start_time], End: [end_time]
       "Soundbite text"
       Reason: [reason for choosing this soundbite]
       
    Ensure all 10 soundbites are distinct and meaningful in the context of the conversation."""
)

prompt = ChatPromptTemplate.from_messages([SYSTEM_PROMPT, USER_PROMPT])

structured_llm = llm.with_structured_output(Soundbite)

chain = (prompt | structured_llm.with_config({"run_name": "soundbite_selection"}))


# retrieve soundbites
async def retrieve_soundbites_with_llm(transcript: VideoTranscript) -> List[Soundbite]:
    """Retrieve soundbites from a video and transcript using LLM."""
    logger.info("RETRIEVING SOUNDBITES FROM LLM")

    response = await chain.ainvoke({"transcript": transcript})

    logger.info(f"LLM response: {response}")

    try:
        if not isinstance(response, list):
            response = [response]

        soundbites = []

        # if len(response) < 10:
        #     logger.error(f"Expected 10 soundbites, but received {len(response)}")
        #     raise HTTPException(status_code=500, detail="Insufficient soundbites returned from LLM")

        for item in response:
            if isinstance(item, Soundbite):
                soundbites.append(item)
            else:
                logger.error(f"Unexpected type in response: {type(item)}")
                raise HTTPException(status_code=500, detail=f"Unexpected response type: {type(item)}")

        return soundbites
    except Exception as e:
        logger.error(f"Error processing LLM response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")


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


def merge_segments(segment_paths: List[str]) -> str:
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


async def process_video_cut_request(video_path: str, transcript: VideoTranscript) -> AllSoundbites:
    """Process video cut request by coordinating soundbite retrieval, video cutting, and merging asynchronously."""
    logger.info("PROCESSING CUT MERGE REQUEST")

    soundbites = await retrieve_soundbites_with_llm(transcript)

    segment_paths = []

    for soundbite in soundbites:
        segment_filename = f"segment_{soundbite.start_time}_{soundbite.end_time}.mp4"
        video_segment_path = os.path.join("uploads", segment_filename)

        logger.info(f"Attempting to cut video from {soundbite.start_time} to {soundbite.end_time}.")

        if os.path.exists(video_segment_path):
            logger.info(f"Segment created: {video_segment_path}")
        else:
            logger.error(f"Failed to create segment: {video_segment_path}")

        try:
            # cut video asynchronously
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

        # Return updated soundbites with merged video path
    return AllSoundbites(
        soundbites=soundbites,
        summary="Soundbites processed and video merged",
        merged_video_path=merged_video_path  # Include the merged video path
    )
