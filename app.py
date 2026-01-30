import streamlit as st
from dotenv import dotenv_values
from openai import OpenAI, AuthenticationError
from hashlib import md5
from pydub import AudioSegment
from pydub.utils import make_chunks
import json
import tempfile
from io import BytesIO
import yt_dlp
import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": "audio.%(ext)s",
    "quiet": True,
}

CHUNK_LENGTH_MINS = 15
AUDIO_TRANSCRIBE_MODEL = "whisper-1"
MODEL = "gpt-4o"
LANGUAGE = "Polish"
env = dotenv_values(".env")

def get_openai_client():
    return OpenAI(api_key=st.session_state["openai_api_key"])

def summarize_text(text, language=LANGUAGE):
    openai_client = get_openai_client()
    prompt = f"Summarize the following text in a concise manner:\n\n{text}"
    stream = openai_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"Your task is to create text summary. Input is transcription of a video with timestamps. Output should contain general summary and summary of each section (if applies). Response language should be {language}."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content is not None:
            yield delta.content

def split_audio_into_chunks(audio_bytes, chunk_length_ms=CHUNK_LENGTH_MINS * 60 * 1000):
    """
    Splits the audio into chunks of the specified length.
    """
    audio = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
    chunks = make_chunks(audio, chunk_length_ms)
    return chunks

def transcribe_audio(audio_bytes):
    openai_client = get_openai_client()
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.mp3"
    transcript = openai_client.audio.transcriptions.create(
        file=audio_file,
        model=AUDIO_TRANSCRIBE_MODEL,
        response_format="verbose_json",
    )
    return transcript

def format_srt_entry(index, start_time, end_time, text):
    """
    Formats a single SRT entry.
    """
    def format_time(seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{int(seconds):02},{milliseconds:03}"

    start = format_time(start_time)
    end = format_time(end_time)
    return f"{index}\n{start} --> {end}\n{text}\n"

def parse_transcript(transcript):
    lines = []
    if st.session_state["is_srt"]:
        return transcript["srt"]
    else:
        for s in transcript["full_transcription"]:
            if st.session_state["is_timestamped"]:
                # Convert start and end times to minutes and seconds
                start_minutes, start_seconds = divmod(int(s['start']), 60)
                end_minutes, end_seconds = divmod(int(s['end']), 60)
                # Format the time as MM:SS
                lines.append(
                    f"[{start_minutes:02d}:{start_seconds:02d} – {end_minutes:02d}:{end_seconds:02d}] {s['text']}"
                )
            else:
                lines.append(s['text'])
        return "\n".join(lines)

def create_transcription(audio_bytes):
    """
    Splits the audio into chunks, transcribes each chunk, and appends timestamps.
    """
    chunks = split_audio_into_chunks(audio_bytes)
    full_transcription = []
    srt_output = []
    current_time_offset = 0  # Track the cumulative time offset in seconds
    progress_bar = st.progress(0, text = "Transcribing audio in progress...")
    for i, chunk in enumerate(chunks):
        progress_bar.progress((i + 1) / len(chunks), text = f"Transcribing audio... (chunk {i + 1} of {len(chunks)})")
        current_time_offset = i * (CHUNK_LENGTH_MINS * 60)
        transcript = transcribe_audio(chunk.export(format="mp3").read())
        
        for segment in transcript.segments:
            start_time = segment.start + current_time_offset
            end_time = segment.end + current_time_offset
            text = segment.text.strip()

            # Append to full transcription
            full_transcription.append({
                "start": start_time,
                "end": end_time,
                "text": text
            })
            srt_output.append(format_srt_entry(len(srt_output) + 1, start_time, end_time, text))
        # current_time_offset += chunk.duration_seconds

    progress_bar.empty()
    # Return SRT or plain text based on the session state
    return {
        "srt": "\n".join(srt_output),  # SRT formatted text
        "full_transcription": full_transcription  # Plain text transcription with timestamps
    }

def get_youtube_id(url:str) -> str | None:
    """
    Extract YouTube video ID from a URL.
    Returns video ID or None if not found.
    """

    if not url:
        return None

    # 1. Short links: youtu.be/VIDEO_ID
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/") or None

    # 2. Standard links: youtube.com/watch?v=VIDEO_ID
    if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        query = parse_qs(parsed.query)
        if "v" in query:
            return query["v"][0]

        # 3. Embedded / shorts / live
        path_match = re.match(r"^/(embed|shorts|live)/([^/?]+)", parsed.path)
        if path_match:
            return path_match.group(2)

    return None

def display_youtube_player(url: str):
    youtube_id = get_youtube_id(url)
    st.session_state["youtube_id"] = youtube_id
    st.components.v1.html(
    f"""
    <iframe width="560" height="315"
    src="https://www.youtube.com/embed/{youtube_id}"
    frameborder="0"
    allowfullscreen></iframe>
    """,
    height=340,
    )

def fetch_youtube_captions(
    youtube_id: str,
    language: str = "en",
    ) -> dict:
    """
    Fetch YouTube captions using youtube-transcript-api >=1.0.0
    """
    ytt_api = YouTubeTranscriptApi()
    feteched_transcript =  ytt_api.fetch(youtube_id).to_raw_data()
    return feteched_transcript

 




def download_youtube_audio(url: str):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# OpenAI API key protection
if not st.session_state.get("openai_api_key"):
    if "OPENAI_API_KEY" in env:
        st.session_state["openai_api_key"] = env["OPENAI_API_KEY"]

    else:
        st.info("Add your OpenAI API key to use the app.")
        st.page_link("https://platform.openai.com/account/api-keys", label="Get your API key here", help= "Don't have an API key yet?", icon="🔑")
        st.session_state["openai_api_key"] = st.text_input("API key", type="password")
        if st.session_state["openai_api_key"]:
            st.rerun()

if not st.session_state.get("openai_api_key"):
    st.stop()


### MAIN

# Session state initialization
if "file_bytes_md5" not in st.session_state:
    st.session_state["file_bytes_md5"] = None

if "file_bytes" not in st.session_state:
    st.session_state["file_bytes"] = None

if "is_video" not in st.session_state:
    st.session_state["is_video"] = None

if "audio_file_path" not in st.session_state:
    st.session_state["audio_file_path"] = None

if "transcript" not in st.session_state:
    st.session_state["transcript"] = None

if "editable_text" not in st.session_state:
    st.session_state["edtitable_text"] = None

if "is_srt" not in st.session_state:
    st.session_state["is_srt"] = False

if "is_timestamped" not in st.session_state:
    st.session_state["is_timestamped"] = False

if "youtube_id" not in st.session_state:
    st.session_state["youtube_id"] = None


with st.sidebar:
    st.sidebar.title("Settings")
    st.session_state["is_srt"] = st.toggle("Subtitle format (.srt)", value=True, key="srt_format")
    settings_info = f"""
    Warning: \n
    Any change of these settings will reset text in a transcription box to its original state. Also, changing settings during transcription will stop the process.
    """
    if not st.session_state["is_srt"]:
        st.session_state["is_timestamped"] = st.toggle("Add timestamps", value=False, key="timestamped")
    
    st.info(settings_info, icon="ℹ️")


st.title("VIDEO/AUDIO SUMMARY")

tab0, tab1 = st.tabs(["Upload file", "Parse YouTube video"])
with tab0:
    uploaded_file = st.file_uploader("Send a file for transcription", type=["mp3", "mp4", "wav", "mov", "ogg"], key="video_file")
    if uploaded_file:
        file_extension = uploaded_file.name.split(".")[-1].lower()  # Get file extension
        file_bytes = uploaded_file.read()
        file_bytes_md5 = md5(file_bytes).hexdigest()
        if file_extension in ["mp3", "wav", "m4a", "ogg"]:
            st.session_state["is_video"] = False
        elif file_extension in ["mp4", "mov"]:
            st.session_state["is_video"] = True
        # on file change:
        if st.session_state["file_bytes_md5"] != file_bytes_md5:
            st.session_state["file_bytes_md5"] = file_bytes_md5
            st.session_state["file_bytes"] = file_bytes
            st.session_state["transcript"] = None
            st.session_state["edtitable_text"] = None
            st.session_state["audio_file_path"] = None
            st.session_state["video_subtitles"] = None
            
            # if file is video
            if st.session_state["is_video"]: 
                st.video(st.session_state["file_bytes"], format="video/mp4")
                # Save uploaded video to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
                    temp_video_file.write(file_bytes)
                    temp_video_path = temp_video_file.name
                info_audio_placeholder = st.empty()
                info_audio_placeholder.info("Extracting audio, please wait...")
                # Convert video to audio
                audio = AudioSegment.from_file(temp_video_path, format="mp4")
                # Save audio to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
                    audio.export(temp_audio_file.name, format="mp3")
                    st.session_state["audio_file_path"] = temp_audio_file.name  
                    info_audio_placeholder.success("Audio was extracted.")
                    st.write("Extracted audio:")
                    st.audio(st.session_state["audio_file_path"], format="audio/mp3")
            
            else:  # if the file is audio
                st.audio(file_bytes, format=f"audio/{file_extension}")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_audio_file:
                    temp_audio_file.write(file_bytes)
                    st.session_state["audio_file_path"] = temp_audio_file.name
                st.success("Audio file uploaded successfully. Ready for transcription.")

        # Uploaded file didn't change
        else:
            if st.session_state["is_video"]:
                if st.session_state["transcript"]:
                    st.video(st.session_state["file_bytes"], format="video/mp4", subtitles=st.session_state["transcript"]["srt"])
                else:
                    st.video(st.session_state["file_bytes"], format="video/mp4")
                st.write("Audio:")
            st.audio(st.session_state["audio_file_path"], format="audio/mp3")
            
        info_transcribe_placeholder = st.empty()
        if st.session_state["transcript"] is None: 
            if st.button("Start Transcription"):
                info_transcribe_placeholder.info("Transcribing audio... (this may take a while depending on the length of the audio)")  
                try:
                    transcript = create_transcription(open(st.session_state["audio_file_path"], "rb").read()) 
                except AuthenticationError:
                    info_transcribe_placeholder.error("Invalid API key. Please check your OpenAI API key and try again (refresh site).")
                    st.stop()
                except Exception as e:
                    info_transcribe_placeholder.error(f"An error occurred: {str(e)}")
                    st.stop()
                st.session_state["transcript"] = transcript
                st.rerun()

        if st.session_state["transcript"]:
            info_transcribe_placeholder.success("Transcription completed.")
            transcription_text = parse_transcript(st.session_state["transcript"]) 
            if st.button("Generate"):
                placeholder = st.empty()
                full_text = ""

                for token in summarize_text(transcription_text):
                    full_text += token
                    placeholder.markdown(full_text)


with tab1:
    url = st.text_input("Input your link here:")
    if url:
        display_youtube_player(url)
        st.session_state["transcript"] = fetch_youtube_captions(st.session_state["youtube_id"], language="eng")
        if st.button("Generate"):
            placeholder = st.empty()
            full_text = ""

            for token in summarize_text(st.session_state["transcript"]):
                full_text += token
                placeholder.markdown(full_text)