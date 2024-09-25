from typing import List, Optional

from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from pydantic.v1 import BaseModel, Field


GV_WATERMARK = "/Users/dtaibeau/Documents/Gigaverse/ffmpeg_testing/Mediamodifier-Design-Template.png"
MERGED_VIDEO_WITH_ST = "/Users/dtaibeau/Documents/Gigaverse/ffmpeg_testing/uploads/merged_vid_with_subtitles.mp4"
MERGED_VIDEO_WITH_WATERMARK = "/Users/dtaibeau/Documents/Gigaverse/ffmpeg_testing/uploads/merged_vid_with_watermark.mp4"


### PYDANTIC MODELS ###

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
    # reason: str
    merged_video_path: Optional[str] = None


### PROMPT SCHEMA ###

SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template(
    """The assistant is a video clip editor, the task is to identify the 10 most meaningful soundbites based on the 
    context of the conversation and for each find a window of approximately 30 seconds to 60 seconds that contains that 
    soundbite and will also serve as a great clip that discusses the topic in a meaningful way that's fit for a short 
    clip. For each soundbite, you must provide the start and end times, the corresponding text, and reasoning for why 
    the soundbite is meaningful. 

    Your task is to select exactly 10 meaningful soundbites from the transcript.
    Each soundbite should represent a key idea or important moment in the conversation that would resonate 
    with an audience.

    Here are the specific instructions:
    1. Select 10 different soundbites from the transcript. 
    2. Each soundbite should cover one or more complete ideas, and should not cut off mid-sentence.
    3. Provide for each soundbite:
       - Start time (hh:mm:ss.mmm) from the transcript
       - End time (hh:mm:ss.mmm) from the transcript
       - The soundbite text verbatim  but [edited for clarity]
       - A brief explanation of why you selected that soundbite and why it is meaningful.
       - a window of 30 seconds - 60seconds that includes the soundbite inside it where the idea articulated in the 
       sound is captured well. a good window is such that the person starts talking in an interesting way about a 
       subject, leads to the captivating soundbites, and ends with some sort of concluding statement
       
       The WINDOW is the most important thing to find correctly. while the soundbite is the core of the matter, the 
       task is to find the best 30seconds to 60seconds window around that soundbite that captures a meaningful 
       discussion around that soundbite

    Return the soundbites in a JSON format that includes these fields:
        - Reason: [reason for choosing this soundbite]
        - text: "Soundbite text"
        - Start: [start_time], 
        - End: [end_time]
        - window_start: [window_start_time]
        - window_end: [window_end_time] 
    
    - Ensure all 10 soundbites are distinct and meaningful in the context of the conversation.
    - Use the CORRECT timestamps from the transcript below!"""
)

USER_PROMPT = HumanMessagePromptTemplate.from_template(
    """Here is the transcript: {transcript}. """
)
