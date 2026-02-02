import streamlit as st
from dotenv import dotenv_values
from openai import OpenAI, AuthenticationError
from hashlib import md5
from pydub import AudioSegment
import tempfile
from io import BytesIO

import youtube_utils 
import audio_utils 


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
            {"role": "system", "content": f"  Response language should be {language}."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content is not None:
            yield delta.content


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

if "youtube_id" not in st.session_state:
    st.session_state["youtube_id"] = None



st.title("VIDEO/AUDIO SUMMARY")

tab0, tab1 = st.tabs(["Upload file", "Parse YouTube video"])

### File upload option
with tab0: 
    uploaded_file = st.file_uploader("Send a file for transcription", type=["mp3", "mp4", "wav", "mov", "ogg"], key="video_file")
    if uploaded_file:
        file_extension = uploaded_file.name.split(".")[-1].lower()  # Get file extension
        file_bytes = uploaded_file.read()
        file_bytes_md5 = md5(file_bytes).hexdigest()
        # Recognize if the file is video or audio
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
                    st.session_state["transcript"] = audio_utils.create_transcription(open(st.session_state["audio_file_path"], "rb").read(), get_openai_client()) 
                except AuthenticationError:
                    info_transcribe_placeholder.error("Invalid API key. Please check your OpenAI API key and try again (refresh site).")
                    st.stop()
                except Exception as e:
                    info_transcribe_placeholder.error(f"An error occurred: {str(e)}")
                    st.stop()
                # st.session_state["transcript"] = transcript
                st.rerun()

        if st.session_state["transcript"]:
            info_transcribe_placeholder.success("Transcription completed.")
            # transcription_text = parse_transcript(st.session_state["transcript"]) 
            if st.button("Generate summary", key = "uploaded_file_btn" ):
                placeholder = st.empty()
                full_text = ""

                for token in summarize_text(st.session_state["transcript"]):
                    full_text += token
                    placeholder.markdown(full_text)

### Youtube link option
with tab1:
    url = st.text_input("Input your link here:")
    if url:
        youtube_utils.display_youtube_player(url)
        st.session_state["transcript"] = youtube_utils.fetch_youtube_captions(st.session_state["youtube_id"], language="eng")
        if st.button("Generate summary", key = "youtube_btn"):
            placeholder = st.empty()
            full_text = ""

            for token in summarize_text(st.session_state["transcript"]):
                full_text += token
                placeholder.markdown(full_text)