# video_recap_feature

This project processes video segments by cutting them based on soundbites, generating `.ass` subtitle files with karaoke-style effects, and embedding the subtitles into the video. The result is a highlight reel with synced animated subtitles and a watermark.

## Features

- **Animated Subtitles**: Generates karaoke-style subtitles with customizable timing per word.
- **Soundbite Retrieval**: Retrieves meaningful and complete ideas using OpenAI's gpt-4o.
- **Subtitle Embedding**: Adds `.ass` subtitles to a video segment using FFmpeg.
- **Custom Styles**: Supports customizable text style, colors, and position of subtitles.
- **Video Watermarking**: Embeds a watermark into the video using FFmpeg.
- **Cut and Merge Videos**: Cuts videos based on timestamped soundbites and merges segments seamlessly.

## Requirements

- Python 3.x
- FFmpeg
- Dependencies listed in `poetry.toml`
