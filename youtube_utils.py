import streamlit as st
import yt_dlp
import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import requests
import tempfile
import io
import shutil


ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": "audio.%(ext)s",
    "quiet": True,
}


def video_exists_http(video_id):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}"
    r = requests.get(url)
    return r.status_code == 200


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

def display_youtube_player(url: str, start: int | None = None):
    youtube_id = get_youtube_id(url)
    st.session_state["youtube_id"] = youtube_id

    if start is not None:
        st.video(f"https://www.youtube.com/watch?v={youtube_id}&start={start}")
    else:
        st.video(f"https://www.youtube.com/watch?v={youtube_id}")


def youtube_link_at(video_id: str, seconds: int) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&start={seconds}"


def fetch_youtube_captions(
    youtube_id: str,
    language: str = "en",
    ) -> dict:
    """
    Fetch YouTube captions using youtube-transcript-api >=1.0.0
    """
    ytt_api = YouTubeTranscriptApi()
    try:
        fetched_transcript = ytt_api.fetch(youtube_id).to_raw_data()
    except NoTranscriptFound:
        fetched_transcript = None
    return fetched_transcript

 

import yt_dlp
import io

def download_youtube_audio(url: str) -> bytes:
    """
    Pobiera audio z YouTube do bytes.
    - Nie używa postprocessingu, żeby uniknąć błędów FFmpeg w pamięci.
    - Zwraca oryginalny audio format (webm/m4a), gotowy do Whisper.
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [],  # brak konwersji → brak problemów z FFmpeg
    }

    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp_file:
        ydl_opts["outtmpl"] = tmp_file.name
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            print(f"Download failed: {e}")
            return None

        tmp_file.seek(0)
        return tmp_file.read()

def fetch_youtube_metadata(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "title": info.get("title"),
        "description": info.get("description"),
        "channel": info.get("channel"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "tags": info.get("tags"),
    }
