import streamlit as st
from pydub import AudioSegment
from pydub.utils import make_chunks
import json
import tempfile
from io import BytesIO


CHUNK_LENGTH_MINS = 15
AUDIO_TRANSCRIBE_MODEL = "whisper-1"

def split_audio_into_chunks(audio_bytes, chunk_length_ms=CHUNK_LENGTH_MINS * 60 * 1000):
    """
    Splits the audio into chunks of the specified length.
    """
    audio = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
    chunks = make_chunks(audio, chunk_length_ms)
    return chunks

def transcribe_audio(audio_bytes, client):
    openai_client = client
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

def create_transcription(audio_bytes, client):
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
        transcript = transcribe_audio(chunk.export(format="mp3").read(), client)
        
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
        # "srt": 
        "\n".join(srt_output),  # SRT formatted text
        #  "full_transcription": 
    #    full_transcription  # Plain text transcription with timestamps
    }