import os
from fastapi.testclient import TestClient
from app import app  # Adjust import based on your project structure
import pytest
from unittest.mock import patch

client = TestClient(app)


@pytest.fixture
def test_video_file(tmp_path):
    # Create a temporary video file for testing
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"Test video content")
    return video_file


@patch("main.ffmpeg.input")  # Mock ffmpeg input to avoid actual file processing
def test_successful_cut_and_merge(mock_ffmpeg_input, test_video_file):
    # Mock the FFmpeg operations to prevent actual processing
    mock_ffmpeg_input.return_value.output.return_value.run.return_value = None

    # Test the endpoint
    with open(test_video_file, "rb") as video:
        response = client.post(
            "/cut-video/",
            files={"file": ("test_video.mp4", video, "video/mp4")},
            data={"start_times": ["00:00:00"], "end_times": ["00:01:00"]}
        )

    # Check that the request was successful
    assert response.status_code == 200
    assert response.json() == {"message": "Video cut successfully"}  # Customize response as needed


def test_cut_video_file_not_found():
    # Test for handling missing file
    response = client.post(
        "/cut-video/",
        files={"file": None},
        data={"start_times": ["00:00:00"], "end_times": ["00:01:00"]}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Video file not found."}  # Customize error handling as needed


@patch("main.ffmpeg.input")
def test_cut_video_with_corrupted_file(mock_ffmpeg_input, test_video_file):
    # Mock ffmpeg to raise an error for corrupted file
    mock_ffmpeg_input.side_effect = Exception("FFmpeg error: Corrupted file")

    with open(test_video_file, "rb") as video:
        response = client.post(
            "/cut-video/",
            files={"file": ("test_video.mp4", video, "video/mp4")},
            data={"start_times": ["00:00:00"], "end_times": ["00:01:00"]}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Error cutting video: FFmpeg error: Corrupted file"}


def test_cut_video_invalid_timestamps(test_video_file):
    # Test for invalid timestamps
    with open(test_video_file, "rb") as video:
        response = client.post(
            "/cut-video/",
            files={"file": ("test_video.mp4", video, "video/mp4")},
            data={"start_times": ["00:00:00"], "end_times": ["invalid-timestamp"]}
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid start or end times."}  # Adjust based on your validation


@patch("main.ffmpeg.input")
def test_cut_video_empty_file(mock_ffmpeg_input, tmp_path):
    # Create an empty file for testing
    empty_video_file = tmp_path / "empty_video.mp4"
    empty_video_file.touch()  # Create an empty file

    with open(empty_video_file, "rb") as video:
        response = client.post(
            "/cut-video/",
            files={"file": ("empty_video.mp4", video, "video/mp4")},
            data={"start_times": ["00:00:00"], "end_times": ["00:01:00"]}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Error cutting video: FFmpeg error"}


