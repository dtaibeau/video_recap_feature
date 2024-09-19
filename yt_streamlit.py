# import json
# from pytube import YouTube
# from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
# from langchain_openai import ChatOpenAI
# from langchain.prompts import PromptTemplate
# from langchain.chains import LLMChain
# from langchain_core.output_parsers import PydanticOutputParser
# from pydantic import BaseModel, Field
# from typing import List, Dict, Optional
# import streamlit as st
# import concurrent.futures
# import time
#
#
#
# ### video details + transcript using pytube and youtube_transcript_api
# def get_video_details_and_transcript(url: str) -> Optional[tuple[str, str, List[Dict[str, str]]]]:
#     """
#     Fetches video details and transcript for given YouTube URL.
#
#     Args:
#         url (str): The URL of the YouTube video
#
#     Returns:
#         Optional[tuple[str, str, List[Dict[str, str]]]]: A tuple containing the video title, description, and transcript,
#         or None if an error occurs
#     """
#     try:
#         st.write("Fetching video details...")  # debug print
#         yt = YouTube(url)
#         title = yt.title
#         description = yt.vid_info.get('videoDetails', {}).get('shortDescription')
#         st.write(f"Fetched description: {description}")
#         video_id = yt.video_id
#         st.write(f"Video ID: {video_id}")
#         st.write("Fetching transcript...")  # debug print
#         transcript = YouTubeTranscriptApi.get_transcript(video_id)
#         st.write("Transcript fetched successfully")  # debug print
#         return title, description, transcript
#     except TranscriptsDisabled as e:
#         st.error(f"Transcript API Error: {e}")
#         return None
#     except Exception as e:
#         st.error(f"General Error: {e}")
#         return None
#
#
# ### identifying speakers and correcting transcript w/ langchain
# def identify_speakers(title: str, description: str, transcript: List[Dict[str, str]]) -> TranscriptWithSpeakers:
#     st.write("Initializing LLMChain...")  # debug print
#     llm = ChatOpenAI(model="gpt-4o", openai_api_key=openai_api_key)
#
#     prompt_template = PromptTemplate.from_template(
#         """You are given a video, and your task is to identify the different speakers' names and correct the text.
#         Given the video title: {title} and description: {description}, identify the speakers in the following transcript segments
#         and the text they spoke in one segment until the next speaker starts speaking, along with appropriate capitalization and punctuation.
#
#         Transcript:
#         {transcript}
#
#         Provide the output in JSON format with a 'segments' key, and each segment should contain 'speaker' and 'text'."""
#     )
#
#     parser = PydanticOutputParser(pydantic_object=TranscriptWithSpeakers)
#
#     chain = prompt_template | llm | parser
#
#     # debug print
#     st.write("Transcript:", transcript)
#
#     ### batching
#     grouped_transcript = []
#     current_speaker = transcript[0]['text']  # debug print
#     current_text = []
#     for segment in transcript:
#         if 'speaker' in segment:
#             current_speaker = segment['speaker']
#         if 'text' in segment:
#             current_text.append(segment['text'])
#         else:
#             current_text.append(segment)
#
#         if segment['text'] == current_speaker:
#             grouped_transcript.append({"speaker": current_speaker, "text": " ".join(current_text)})
#             current_text = [segment['text']]
#
#     grouped_transcript.append({"speaker": current_speaker, "text": " ".join(current_text)})
#
#     # debug print
#     st.write("Grouped Transcript:", grouped_transcript)
#
#     ### batch processing
#     batch_size = 20
#     transcript_batches = [grouped_transcript[i:i + batch_size] for i in range(0, len(grouped_transcript), batch_size)]
#     responses = []
#
#     for i, batch in enumerate(transcript_batches):
#         st.write(f"Processing batch {i + 1} of {len(transcript_batches)}")
#         transcript_text = "\n".join([f"{segment['speaker']}: {segment['text']}" for segment in batch])
#         inputs = {"title": title, "description": description, "transcript": transcript_text}
#
#         try:
#             st.write("Invoking LLMChain for batch...")
#             start_time = time.time()
#             response = chain.invoke(inputs)
#             end_time = time.time()
#             st.write(f"LLMChain invocation complete for batch. Time taken: {end_time - start_time} seconds")
#
#             if isinstance(response, TranscriptWithSpeakers):
#                 responses.extend(response.segments)
#             else:
#                 st.write("Response validation failed for batch.")
#                 raise ValueError("The response format is incorrect. Expected a dictionary with 'segments' key.")
#         except Exception as e:
#             st.write(f"Error processing batch {i + 1}: {e}")
#
#     combined_transcript = TranscriptWithSpeakers(segments=responses)
#     return combined_transcript
#
#
# ### save transcript to JSON
# def save_transcript_to_json(transcript: TranscriptWithSpeakers, filename: str):
#     st.write(f"Saving transcript to {filename}...")
#     with open(filename, 'w') as f:
#         json.dump(transcript.model_dump(), f, indent=4)
#     st.write("Transcript saved successfully.")