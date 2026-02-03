import re
import streamlit as st

CHAPTER_RE = re.compile(
    r"####\s+\d+\.\s+(?P<title>.+?)\s+\((?P<start>\d+:\d+)[–-](?P<end>\d+:\d+)\)"
)


def extract_chapters(markdown: str) -> list[dict]:
    chapters = []

    for match in CHAPTER_RE.finditer(markdown):
        chapters.append({
            "title": match.group("title"),
            "start": match.group("start"),
            "end": match.group("end"),
        })

    return chapters

def timestamp_to_seconds(ts: str) -> int:
    m, s = map(int, ts.split(":"))
    return m * 60 + s



