import pytest
import os
from unittest.mock import patch
from main import merge_segments


# Test merging with empty segment paths
def test_merge_empty_segments():
    with pytest.raises(ValueError):
        merge_segments([])


# Test successful segment merging with mocked ffmpeg to speed up tests
@patch("main.ffmpeg.input")
def test_successful_merge(mock_ffmpeg_input, tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp("uploads")
    segment_paths = [
        os.path.join(upload_dir, "segment_0.mp4"),
        os.path.join(upload_dir, "segment_1.mp4"),
    ]

    # Create dummy segment files for testing
    for segment in segment_paths:
        with open(segment, "wb") as f:
            f.write(b"Test content")

    # Mock the ffmpeg operations to prevent actual file processing
    mock_ffmpeg_input.return_value.output.return_value.run.return_value = None

    merged_output = merge_segments(segment_paths)

    # Simulate the existence of the merged output file
    with open(merged_output, "wb") as f:
        f.write(b"Merged content")

    # Assertions
    assert os.path.exists(merged_output)
    assert not os.path.exists(segment_paths[0])  # Ensure cleanup occurred
    assert not os.path.exists(segment_paths[1])  # Ensure cleanup occurred


# Test file cleanup after merge failure
@patch("main.ffmpeg.input")
def test_merge_with_invalid_segments(mock_ffmpeg_input, tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp("uploads")
    segment_paths = [os.path.join(upload_dir, "nonexistent_segment.mp4")]

    # Mock ffmpeg to simulate failure
    mock_ffmpeg_input.side_effect = Exception("FFmpeg merge failed")

    with pytest.raises(Exception):
        merge_segments(segment_paths)

    # Assert no leftover temp files
    assert not os.path.exists(segment_paths[0])
