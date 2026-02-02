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

ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": "audio.%(ext)s",
    "quiet": True,
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

