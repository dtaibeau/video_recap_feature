import re
import subprocess
from typing import List
import os
from loguru import logger
import textwrap

from main import Soundbite
from models import GV_WATERMARK, MERGED_VIDEO_WITH_ST, MERGED_VIDEO_WITH_WATERMARK, TranscriptSegment

logger.info(os.path.exists("uploads/sample.mp4"))


def wrap_text(text: str, width: int = 60) -> List[str]:
    """Wraps the text for better readability on screen."""
    return textwrap.wrap(text, width=width)


def format_timestamp_for_filename(timestamp: str) -> str:
    """Convert 'hh:mm:ss.sss' timestamp to 'hh_mm_ss.sss' for use in filenames."""
    return timestamp.replace(":", "_")


def parse_transcript(transcript_path: str) -> List[TranscriptSegment]:
    """
    Parses the full transcript and returns a list of segments with start times and text.
    """
    transcript_segments = []
    with open(transcript_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3}) (.+)", line.strip())
            if match:
                start_time = match.group(1)
                text = match.group(2)
                transcript_segments.append(TranscriptSegment(start_time=start_time, text=text))
    return transcript_segments


def match_soundbite_with_transcript(soundbite: Soundbite, transcript_segments: List[TranscriptSegment]) -> str:
    """
    Match the soundbite timestamps with the corresponding transcript text.
    """
    relevant_text = ""
    for segment in transcript_segments:
        if soundbite.start_time <= segment.start_time <= soundbite.end_time:
            relevant_text += segment.text + " "
    return relevant_text.strip()


def time_to_milliseconds(time_str: str):
    """Convert 'hh:mm:ss.sss' to total milliseconds."""
    hours, minutes, seconds = map(float, time_str.split(':'))
    return int(hours * 3600000 + minutes * 60000 + seconds * 1000)


def create_ass_file_for_segment(soundbite: Soundbite, transcript_text: str, ass_file_path: str, segment_start_time: str, margin_v: int = 50):
    """
    Creates an .ass file for the video segment with line-by-line karaoke-style subtitles using {\\k}.
    The start and end times of the subtitles are offset to match the start of the video segment.
    The karaoke effect applies to the entire line instead of word-by-word, with the specified color settings.
    """
    segment_start_ms = time_to_milliseconds(segment_start_time)
    soundbite_start_ms = time_to_milliseconds(soundbite.start_time)
    soundbite_end_ms = time_to_milliseconds(soundbite.end_time)

    # Calculate the total duration of the soundbite in milliseconds
    total_duration_ms = soundbite_end_ms - soundbite_start_ms

    # Wrap the transcript into lines (you can adjust the width for line breaks)
    lines = wrap_text(transcript_text, width=60)

    with open(ass_file_path, "w") as ass_file:
        ass_file.write("[Script Info]\n")
        ass_file.write(f"Title: Soundbite Subtitle\n")
        ass_file.write("ScriptType: v4.00+\nPlayDepth: 0\n")
        ass_file.write("\n[V4+ Styles]\n")
        ass_file.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                       "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                       "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        ass_file.write(
            f"Style: Default,Red Hat Display,24,&H00FFFFFF,&H00602DE9,&H00602DE9,&H00000000,0,0,0,0,100,100,0,"
            f"0,1,1.5,0,2,10,10,{margin_v},1\n")  # Default style with requested color settings

        ass_file.write("\n[Events]\n")
        ass_file.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        # Ensure the last line covers the entire duration of the soundbite
        remaining_duration_ms = total_duration_ms  # Initialize remaining duration for each line

        # Generate karaoke subtitles with dynamic timing for each line
        for i, line in enumerate(lines):
            words = line.split()
            total_chars = sum(len(word) for word in words)  # Calculate total characters in the line

            # Calculate the duration per character
            duration_per_char = (total_duration_ms / total_chars) * 0.4 if total_chars > 0 else 0

            karaoke_text = ""
            for word in words:
                word_duration_ms = len(word) * duration_per_char  # Word duration based on character count
                word_duration_cs = int(word_duration_ms / 10)  # Convert to centiseconds
                karaoke_text += f"{{\\k{word_duration_cs}}}{word} "

            # Format the start and end times
            formatted_start_time = milliseconds_to_ass_time(soundbite_start_ms - segment_start_ms)
            soundbite_start_ms += int(len(line) * duration_per_char)  # Adjust time for the next line
            formatted_end_time = milliseconds_to_ass_time(soundbite_start_ms - segment_start_ms)

            # Subtract the used time from the remaining duration
            remaining_duration_ms -= (len(line) * duration_per_char)

            # Write the dialogue line with karaoke effect
            dialogue = f"Dialogue: 0,{formatted_start_time},{formatted_end_time},Default,,0,0,0,,{karaoke_text.strip()}\n"
            ass_file.write(dialogue)

        # Ensure the last subtitle covers the full duration
        if remaining_duration_ms > 0:
            formatted_end_time = milliseconds_to_ass_time(soundbite_end_ms - segment_start_ms)
            dialogue = f"Dialogue: 0,{formatted_end_time},{formatted_end_time},Default,,0,0,{margin_v},, \n"
            ass_file.write(dialogue)


def milliseconds_to_ass_time(ms: int) -> str:
    """
    Convert milliseconds to ASS time format: h:mm:ss.cs
    """
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    centiseconds = (ms % 1000) // 10

    return f"{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}"


# def format_time(time_str: str) -> str:
#     """
#     Convert time in 'hh:mm:ss.sss' format to ASS-compatible 'h:mm:ss.cs' format.
#     """
#     match = re.match(r"(\d+):(\d+):(\d+)\.(\d+)", time_str)
#     if not match:
#         return time_str  # Return original if format is incorrect
#
#     hours, minutes, seconds, milliseconds = match.groups()
#     centiseconds = round(int(milliseconds) / 10)
#
#     # Return formatted time without leading zeros for hours
#     return f"{int(hours)}:{minutes}:{seconds}.{centiseconds:02d}"


def add_subtitles_to_segment(video_segment_path: str, ass_file_path: str, output_path: str):
    """
    Adds the .ass subtitles to the video segment using the FFmpeg command with the 'fflags +genpts' option.
    """
    command = f"ffmpeg -fflags +genpts -i {video_segment_path} -vf 'ass={ass_file_path}' -c:v libx264 -c:a copy {output_path}"
    os.system(command)


def add_watermark(video_path: str, output_path: str, watermark_path: str):
    """
    Adds a PNG watermark to the video using FFmpeg"""
    logger.info("Starting to add watermark to video...")

    try:
        command = (
            f"ffmpeg -i {video_path} "
            f"-i {watermark_path} "
            f'-filter_complex "overlay=W-w-100:H-h-700" '
            f"-c:v libx264 -c:a copy {output_path}"
        )

        logger.info(f"Running command: {command}")
        os.system(command)
        logger.info(f"Watermark added successfully to {output_path}")

    except Exception as e:
        logger.error(f"Error adding watermark: {str(e)}")
        raise

