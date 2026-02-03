import streamlit as st
from dotenv import dotenv_values
from openai import OpenAI, AuthenticationError
from hashlib import md5
from pydub import AudioSegment
import tempfile
from io import BytesIO

import youtube_utils 
import audio_utils 
import summary


MODEL = "gpt-4o"
LANGUAGE = "Polish"

env = dotenv_values(".env")

def get_openai_client():
    return OpenAI(api_key=st.session_state["openai_api_key"])

def render_player(video_id, autoplay):
    start = st.session_state.get("seek_to", 0)

    if start is not None:
        st.video(f"https://www.youtube.com/watch?v={video_id}", start_time=start, autoplay=autoplay)
    else:
        st.video(f"https://www.youtube.com/watch?v={video_id}")

def set_seek(seconds: int):
    st.session_state.seek_to = seconds

def render_chapter_buttons(chapters):
    st.subheader("📚 Rozdziały")

    for i, ch in enumerate(chapters):
        seconds = summary.timestamp_to_seconds(ch["start"])
        st.button(
            f"▶ {ch['title']} ({ch['start']})",
            key=f"chapter_{i}",
            on_click=set_seek,
            args=(seconds,),
        )
        # if st.button(
        #     f"▶ {ch['title']} ({ch['start']})",
        #     key=f"chapter_{i}_{seconds}",
        # ):
        #     st.session_state.seek_to = seconds

def summarize_text(text, context, language=LANGUAGE):
    openai_client = get_openai_client()
    prompt = f""""
    \n Transciption:{text}
        Transcription context: {context}
    """
    stream = openai_client.chat.completions.create(
        model=MODEL,
        messages=[
              {"role": "system", "content": f"""
               Your task is to create a precise, concise, and accurate summary. 
               Input is transcription of a video with timestamps. 
               Output format:
                1. TL;DR (3–5 points)
                - The main points/conclusions of the film.

                2. Film Structure (Chapters)
                - Divide the content into logical sections.
                - Use the following chapter header format for each chapter:
                        #### N. Chapter Title (MM:SS–MM:SS)
                        - Add bullet points describing this chapter
                - Chapter numbers N must be sequential (1, 2, 3…)
                - Timestamps must always be in the format MM:SS (minutes:seconds)
                - Other sections (TL;DR, Key Terms, Conclusions) can have standard Markdown headers (###, ### etc.)

                3. Key Terms and Ideas
                - A list of terms with a brief explanation
                - Only terms that actually appear in the material

                4. Author's Conclusions
                - What is the author's main point or message?

                5. Limitations/Claims
                - Highlight any uncertainties, simplifications, or things left unsaid in the film.

                Answer Format:
                - Markdown
                - Clear headings
                - Bullet points where possible
                - No introductions or meta summaries
               Rules:
                - Rely solely on the provided material.
                - Do not add external knowledge.
                - If something cannot be clearly concluded, state it.
                - Maintain a neutral, analytical tone. 
               Response language should be {language}.
               """},
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

def request_generation():
    st.session_state["generate_requested"] = True



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

if "yt_transcript" not in st.session_state:
    st.session_state["yt_transcript"] = None

if "editable_text" not in st.session_state:
    st.session_state["edtitable_text"] = None

if "youtube_id" not in st.session_state:
    st.session_state["youtube_id"] = None

if "context" not in st.session_state:
    st.session_state["context"] = ""

if "full_summary" not in st.session_state:
    st.session_state["full_summary"] = None

if "yt_full_summary" not in st.session_state:
    st.session_state["yt_full_summary"] = None

if "seek_to" not in st.session_state:
    st.session_state.seek_to = 0

if "generate_requested" not in st.session_state:
    st.session_state["generate_requested"] = False

st.set_page_config(layout="wide")

left_col, center_col, right_col = st.columns([1, 4, 1])

with center_col:
    st.title("VIDEO/AUDIO SUMMARY")
    upload_tab, youtube_tab = st.tabs(["Upload file", "Parse YouTube video"])
    ### File upload option
    with upload_tab: 
        uploaded_file = st.file_uploader("Send a file for transcription", type=["mp3", "mp4", "wav", "mov", "ogg"], key="video_file")
        video_col, summary_col = st.columns(2, gap="small")
        with video_col:
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
                        st.success("Audio file uploaded successfully.")

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
                    st.session_state["context"] = st.text_area("You can add additional context for the summary here")
                    if st.button("Generate summary", key = "uploaded_file_btn" ):
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
        with summary_col:
            if st.session_state["transcript"]:
                info_transcribe_placeholder.info("Transcription completed. Generating summary...")  
                # transcription_text = parse_transcript(st.session_state["transcript"]) 
                # if st.button("Generate summary", key = "uploaded_file_btn" ):
                st.session_state["full_summary"] = ""
                placeholder = st.empty()
                for token in summarize_text(st.session_state["transcript"], st.session_state["context"]):
                    st.session_state["full_summary"] += token
                    placeholder.markdown(st.session_state["full_summary"])
                info_transcribe_placeholder.success("Transcription completed.")

    ### Youtube link option
    with youtube_tab:
        url = st.text_input("Input your link here:")
        youtube_id = youtube_utils.get_youtube_id(url)
        if youtube_id:
            if not youtube_utils.video_exists_http(youtube_id):
                st.error("Video not found or private.")
        # else:
        #     st.warning("Invalid YouTube URL.")
        yt_video_col, yt_summary_col = st.columns(2, gap="small")

        if youtube_id and youtube_id != st.session_state["youtube_id"]: #new url provided
            st.session_state["youtube_id"]=youtube_id
            st.session_state["generate_requested"] = False
            with yt_video_col:
                render_player(youtube_id, False)
                st.button("Generate summary", on_click=request_generation)

        else: 
            if st.session_state["generate_requested"]:
                with yt_summary_col:
                    with st.spinner("In progress..."):
                        st.session_state["yt_transcript"]= youtube_utils.fetch_youtube_captions(st.session_state["youtube_id"], language="eng")
                        st.session_state["yt_full_summary"] = ""
                        with st.container(height=700):
                            placeholder = st.empty()
                        for token in summarize_text(st.session_state["yt_transcript"], youtube_utils.fetch_youtube_metadata(url)):
                            st.session_state["yt_full_summary"] += token
                            placeholder.markdown(st.session_state["yt_full_summary"])
                    with st.spinner("Generating summary..."):
                        chapters = summary.extract_chapters(st.session_state["yt_full_summary"])
                        # render_player(st.session_state["youtube_id"])
                        st.session_state["generate_requested"] = False
                with yt_video_col:
                    render_player(youtube_id, True)
                    if chapters:
                        with st.container(height=340):
                            render_chapter_buttons(chapters)

            else:
                with yt_video_col:
                        if youtube_id:
                            render_player(youtube_id, True)
                            # youtube_utils.display_youtube_player(url)
                            if st.session_state["yt_full_summary"]:
                                chapters = summary.extract_chapters(st.session_state["yt_full_summary"])
                                with st.container(height=340):
                                    render_chapter_buttons(chapters)
                with yt_summary_col:
                    if st.session_state["yt_full_summary"]:
                        video_id = st.session_state["youtube_id"]
                        # render_player(video_id)
                        with st.container(height=700):
                            st.markdown(st.session_state["yt_full_summary"])
                        # clean_md = summary.CHAPTER_RE.sub("", st.session_state["yt_full_summary"])
                        # st.markdown(clean_md)