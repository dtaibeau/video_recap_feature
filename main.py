import os
from datetime import datetime
from typing import List
from uuid import uuid4
import ffmpeg
from fastapi import HTTPException


def cut_video(input_path: str, start: str, end: str, output_path: str) -> str:
    ffmpeg.input(input_path, ss=start, to=end).output(output_path).run()
    return output_path


def merge_segments(segment_paths: List[str]) -> str:
    if not segment_paths:
        raise ValueError("No segments provided for merging.")

    list_file = f"uploads/{uuid4()}.txt"
    merged_output = f"uploads/merged_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    try:
        with open(list_file, "w") as f:
            for segment in segment_paths:
                f.write(f"file '{os.path.abspath(segment)}'\n")

        # merge
        ffmpeg.input(list_file, format='concat', safe=0).output(merged_output, c='copy').run()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging segments: {str(e)}")

    finally:
        # clean
        if os.path.exists(list_file):
            os.remove(list_file)
        for segment in segment_paths:
            if os.path.exists(segment):
                os.remove(segment)

    return merged_output
