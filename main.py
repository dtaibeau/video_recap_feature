import os
from datetime import datetime
from typing import List
from uuid import uuid4

import ffmpeg


def cut_video(input_path: str, start: str, end: str, output_path: str) -> str:
    ffmpeg.input(input_path, ss=start, to=end).output(output_path).run()
    return output_path


def merge_segments(segment_paths: List[str]) -> str:
    list_file = f"uploads/{uuid4()}.txt"

    with open(list_file, "w") as f:
        for segment in segment_paths:
            f.write(f"file '{os.path.abspath(segment)}'\n")

    merged_output = merged_output = f"uploads/merged_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    # merge
    ffmpeg.input(list_file, format='concat', safe=0).output(merged_output, c='copy').run()

    return merged_output
