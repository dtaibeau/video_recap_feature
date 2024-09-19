import pytest
from pydantic.v1 import ValidationError
from main import AllSoundbites, Soundbite

# Mock LLM response data
mock_llm_response = {
    "soundbites": [
        {
            "start_time": "00:00:10",
            "end_time": "00:00:20",
            "text": "This is a sample soundbite.",
            "reasoning": "It captures the main idea."
        },
        {
            "start_time": "00:01:10",
            "end_time": "00:01:30",
            "text": "This is another soundbite."
        }
    ],
    "summary": "These are the top 2 soundbites from the video.",
    "merged_video_path": "uploads/merged_video.mp4"
}


# Test valid LLM response structure
def test_llm_response_structure():
    try:
        # Validate the LLM response structure
        all_soundbites = AllSoundbites(**mock_llm_response)
        assert len(all_soundbites.soundbites) == 2
        assert all_soundbites.merged_video_path == "uploads/merged_video.mp4"
        assert all_soundbites.summary == "These are the top 2 soundbites from the video."
    except ValidationError as e:
        pytest.fail(f"Validation failed: {e}")


# Test missing fields in the response
def test_llm_response_missing_fields():
    incomplete_response = {
        "soundbites": [
            {
                "start_time": "00:00:10",
                "text": "This is a sample soundbite."
            }
        ],
        "summary": "Summary with missing fields."
    }

    # Expecting validation error due to missing fields (end_time, merged_video_path)
    with pytest.raises(ValidationError):
        AllSoundbites(**incomplete_response)


# Test empty soundbites in the response
def test_llm_response_empty_soundbites():
    empty_response = {
        "soundbites": [],
        "summary": "No soundbites found.",
        "merged_video_path": "uploads/merged_video.mp4"
    }

    all_soundbites = AllSoundbites(**empty_response)
    assert len(all_soundbites.soundbites) == 0
    assert all_soundbites.merged_video_path == "uploads/merged_video.mp4"
    assert all_soundbites.summary == "No soundbites found."


# Test invalid timestamp format in the response
def test_llm_response_invalid_timestamp():
    invalid_response = {
        "soundbites": [
            {
                "start_time": "invalid_time_format",
                "end_time": "00:00:20",
                "text": "This is a sample soundbite."
            }
        ],
        "summary": "Invalid timestamps in the response.",
        "merged_video_path": "uploads/merged_video.mp4"
    }

    # Expecting validation error due to invalid timestamp format
    with pytest.raises(ValidationError):
        AllSoundbites(**invalid_response)
