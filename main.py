import ffmpeg


def cut_video(input_path: str, start: str, end: str) -> str:
    output_path = input_path.replace(".mp4", "_cut.mp4")
    ffmpeg.input(input_path, ss=start, to=end).output(output_path).run()
    return output_path