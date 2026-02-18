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
from translation import t


MODEL = "gpt-4o"

env = dotenv_values(".env")




def get_openai_client():
    return OpenAI(api_key=st.session_state["openai_api_key"])

def render_youtube_player(video_id, autoplay):
    start = st.session_state.get("seek_to", 0)

    if start is not None:
        st.video(f"https://www.youtube.com/watch?v={video_id}", start_time=start, autoplay=autoplay)
    else:
        st.video(f"https://www.youtube.com/watch?v={video_id}")

def render_local_player(file_path, is_video=True):
    start = st.session_state.get("seek_to", 0)

    if is_video:
        if start is not None:
            st.video(file_path, start_time=start)
        else:
            st.video(file_path)
    else:
        if start is not None:
            st.audio(file_path, start_time=start)
        else:
            st.audio(file_path)

def set_seek(seconds: int):
    st.session_state.seek_to = seconds

def render_chapter_buttons(chapters):
    st.subheader(t("chapters", lang))

    for i, ch in enumerate(chapters):
        seconds = summary.timestamp_to_seconds(ch["start"])
        st.button(
            f"▶ {ch['title']} ({ch['start']})",
            key=f"chapter_{i}",
            on_click=set_seek,
            args=(seconds,),
        )

def summarize_text(text, context, language):
    
    openai_client = get_openai_client()
    prompt = f""""
    \n Transciption:{text}
        Transcription context: {context}
        Response language: {language}
    """
    stream = openai_client.chat.completions.create(
        model=MODEL,
        messages=[
              {"role": "system", "content": f"""
               Translate response to {language}.
               Your task is to create a precise, concise, and accurate summary. 
               Input is transcription of a video with timestamps. 
               Output format:
                1. TL;DR (3–5 points)
                - The main points/conclusions of the film.

                2. Film Structure (Chapters)
                - If chapters are provided in the video context, use them. If not, create your own logical division into chapters based on the content.
                - Use the following chapter header format for each chapter:
                        #### N. Chapter Title (MM:SS–MM:SS)
                        - Add bullet points describing this chapter
                - Chapter numbers N must be sequential (1, 2, 3…)
                - Timestamps must always be in the format MM:SS (minutes:seconds)
                - chapter timestamps cannot exceed the video length
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

def request_generation():
    st.session_state["generate_requested"] = True

def request_yt_transcription():
    st.session_state["yt_transcription_requested"] = True

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

if "video_file_path" not in st.session_state:
    st.session_state["video_file_path"] = None

if "transcript" not in st.session_state:
    st.session_state["transcript"] = None

if "full_summary" not in st.session_state:
    st.session_state["full_summary"] = None

if "chapters" not in st.session_state:
    st.session_state["chapters"] = None

if "context" not in st.session_state:
    st.session_state["context"] = ""

if "yt_transcript" not in st.session_state:
    st.session_state["yt_transcript"] = None

if "youtube_id" not in st.session_state:
    st.session_state["youtube_id"] = None

if "yt_full_summary" not in st.session_state:
    st.session_state["yt_full_summary"] = None

if "seek_to" not in st.session_state:
    st.session_state.seek_to = 0

if "generate_requested" not in st.session_state:
    st.session_state["generate_requested"] = False

if "yt_chapters" not in st.session_state:
    st.session_state["yt_chapters"] = None

if "lang" not in st.session_state:
    st.session_state.lang = "english"

st.set_page_config(layout="wide")

with st.sidebar:
    st.session_state.lang = st.selectbox(
    "Language",
    ["english", "polish"],
    index=["english", "polish"].index(st.session_state.lang),
    )
    lang = st.session_state["lang"]
    st.info(t("lang_info", lang))


left_col, center_col, right_col = st.columns([1, 4, 1])

with center_col:
    st.title("VIDEO/AUDIO SUMMARY")
    youtube_tab, upload_tab = st.tabs(["YouTube video", t("upload", lang)])
    ### Youtube link option
    with youtube_tab:
        url = st.text_input(t("input_label", lang), value=st.session_state.get('url', ''), key="youtube_url_input")
        st.session_state["url"] = url
        youtube_id = youtube_utils.get_youtube_id(url)
        video_exists = youtube_utils.video_exists_http(youtube_id)
        if youtube_id:
            if not video_exists:
                st.error(t("video_error", lang))
        yt_video_col, yt_summary_col = st.columns(2, gap="small")

        if (youtube_id and youtube_id != st.session_state["youtube_id"]): #new url provided
            st.session_state["youtube_id"]=youtube_id
            st.session_state["yt_full_summary"] = None
            st.session_state["generate_requested"] = False
            with yt_video_col:
                if video_exists:
                    render_youtube_player(youtube_id, False)
                    st.button(t("generate", lang), on_click=request_generation)

        else: #url didn't change
            if st.session_state["generate_requested"]:
                with yt_video_col:
                    render_youtube_player(youtube_id, True)
                    if st.session_state["yt_full_summary"] and st.session_state["yt_chapters"]:
                        with st.container(height=340):
                            render_chapter_buttons(st.session_state["yt_chapters"])
                with yt_summary_col:
                    with st.container(height=700):
                        with st.spinner(t("loading", lang)):
                            placeholder = st.empty()
                            try:
                                st.session_state["yt_transcript"] = youtube_utils.fetch_youtube_captions(st.session_state["youtube_id"], language="eng")
                            except youtube_utils.RequestBlocked:
                                 st.session_state["yt_transcript"] = None
                                 st.error(t("video_error", lang))
                                 st.stop()
                            
                            if st.session_state["yt_transcript"] is None and  not st.session_state["yt_transcription_requested"]:
                                st.error(t("no_captions", lang))
                                st.info(t("no_transcription_info", lang))
                            else:
                                st.session_state["yt_full_summary"] = ""
                                for token in summarize_text(st.session_state["yt_transcript"], youtube_utils.fetch_youtube_metadata(url), st.session_state["lang"]):
                                    st.session_state["yt_full_summary"] += token
                                    placeholder.markdown(st.session_state["yt_full_summary"])
                                st.session_state["yt_chapters"] = summary.extract_chapters(st.session_state["yt_full_summary"])
                                st.session_state["generate_requested"] = False
                                st.rerun()
            else:
                with yt_video_col:
                        if st.session_state["youtube_id"]:
                            render_youtube_player(youtube_id, True)
                            if not st.session_state["yt_full_summary"]:
                                st.button(t("generate", lang), on_click=request_generation)
                            if st.session_state["yt_full_summary"]:
                                chapters = summary.extract_chapters(st.session_state["yt_full_summary"])
                                with st.container(height=340):
                                    render_chapter_buttons(chapters)

                with yt_summary_col:
                    if st.session_state["yt_full_summary"]:
                        video_id = st.session_state["youtube_id"]
                        with st.container(height=700):
                            st.markdown(st.session_state["yt_full_summary"])
                            st.button(t("regenerate", lang), on_click=request_generation)



    ### File upload option
    with upload_tab: 
        uploaded_file = st.file_uploader(t("send_file", lang), type=["mp3", "mp4", "wav", "mov", "ogg"], key="video_file")
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
                    st.session_state["video_file_path"] = None
                    st.session_state["full_summary"] = None
                    
                    # if file is video
                    if st.session_state["is_video"]: 
                        st.video(st.session_state["file_bytes"], format="video/mp4")
                        # Save uploaded video to a temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
                            temp_video_file.write(file_bytes)
                            temp_video_path = temp_video_file.name
                            st.session_state["video_file_path"] = temp_video_path
                        info_audio_placeholder = st.empty()
                        # Convert video to audio
                        audio = AudioSegment.from_file(temp_video_path, format="mp4")
                        # Save audio to a temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
                            audio.export(temp_audio_file.name, format="mp3")
                            st.session_state["audio_file_path"] = temp_audio_file.name  
                    
                    else:  # if the file is audio
                        st.audio(file_bytes, format=f"audio/{file_extension}")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_audio_file:
                            temp_audio_file.write(file_bytes)
                            st.session_state["audio_file_path"] = temp_audio_file.name
                        st.success(t("audio_upload_success", lang))

                # Uploaded file didn't change
                else:
                    if st.session_state["is_video"]:
                        file_path = st.session_state["video_file_path"]
                    else:
                        file_path = st.session_state["audio_file_path"]      
                    render_local_player(file_path, st.session_state["is_video"])

                info_transcribe_placeholder = st.empty()
                if st.session_state["transcript"] is None: 
                    st.session_state["context"] = st.text_area(t("context", lang), height=100)
                    if st.button(t("generate", lang), key = "uploaded_file_btn" ):
                        info_transcribe_placeholder.info(t("transcribing_info", lang))  
                        try:
                            st.session_state["transcript"] = audio_utils.create_transcription(open(st.session_state["audio_file_path"], "rb").read(), get_openai_client()) 
                        except AuthenticationError:
                            info_transcribe_placeholder.error(t("invalid_api_key", lang))
                            st.stop()
                        except Exception as e:
                            info_transcribe_placeholder.error(f"An error occurred: {str(e)}")
                            st.stop()
                        # st.session_state["transcript"] = transcript
                        st.rerun()

                if st.session_state["full_summary"]:
                    if st.session_state["chapters"]:
                        with st.container(height=365):
                            render_chapter_buttons(st.session_state["chapters"])
        with summary_col:
            if st.session_state["transcript"]:
                if not st.session_state["full_summary"]:
                    info_transcribe_placeholder.info(t("summarizing_info", lang))  
                    st.session_state["full_summary"] = ""
                    with st.container(height=700):
                        placeholder = st.empty()
                        for token in summarize_text(st.session_state["transcript"], st.session_state["context"], st.session_state["lang"]):
                            st.session_state["full_summary"] += token
                            placeholder.markdown(st.session_state["full_summary"])
                    st.session_state["chapters"] = summary.extract_chapters(st.session_state["full_summary"])
                    info_transcribe_placeholder.success(t("summary_completed", lang))
                    st.rerun()
                else:
                    with st.container(height=700):
                        st.markdown(st.session_state["full_summary"])
