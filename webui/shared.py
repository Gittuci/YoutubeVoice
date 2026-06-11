import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.config
from pipeline.utils import find_ffmpeg

STATE_KEYS = {
    "video_path": None,
    "video_copy_path": None,
    "srt_path": None,
    "transcribed_srt_path": None,
    "transcribed": False,
    "translated_langs": set(),
    "tts_complete": {},
    "fcpxml_generated": {},
    "is_running": False,
    "current_run": None,
    "log_captured": [],
    "ffmpeg_path": None,
    "selected_langs": {"de", "es", "fr"},
    "youtube_url": "",
}


def init_session_state():
    for key, default in STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state.ffmpeg_path is None:
        try:
            st.session_state.ffmpeg_path = find_ffmpeg()
        except FileNotFoundError:
            st.session_state.ffmpeg_path = None


@st.cache_resource
def get_vertex_client():
    if pipeline.config.vertex_api_key:
        return pipeline.config.create_vertex_client()
    return None


@st.cache_resource
def get_deepseek_client():
    if pipeline.config.deepseek_api_key:
        from openai import OpenAI
        return OpenAI(
            base_url=pipeline.config.DEEPSEEK_BASE_URL,
            api_key=pipeline.config.deepseek_api_key,
        )
    return None


@st.cache_data(ttl=5)
def scan_output_dir():
    output_dir = pipeline.config.OUTPUT_DIR
    files = {}
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            full = os.path.join(output_dir, f)
            if os.path.isfile(full):
                files[f] = os.path.getsize(full)
    srt_files = {f for f in files if f.endswith(".srt")}
    wav_files = []
    if os.path.isdir(wav_dir):
        wav_files = [f for f in os.listdir(wav_dir) if f.endswith(".wav")]
    audio_files = {f for f in files if f.endswith(".wav") and f == "audio.wav"}
    fcpxml_files = {f for f in files if f.endswith(".fcpxml")}
    return {"srt_files": srt_files, "wav_files": wav_files, "audio_files": audio_files, "fcpxml_files": fcpxml_files, "all_files": files}
