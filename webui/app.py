import os
import streamlit as st

from webui.shared import (
    STATE_KEYS,
    init_session_state,
    get_vertex_client,
    get_deepseek_client,
    scan_output_dir,
)
from pipeline import config as pipeline_config
from pipeline.utils import find_ffmpeg

init_session_state()

st.set_page_config(page_title="Foltvilag Pipeline", page_icon="🎬", layout="wide")

st.title("🎬 Foltvilag — Multi-Language Video Voiceover Pipeline")

st.sidebar.header("Pipeline Status")

output_state = scan_output_dir()

vertex_ok = bool(pipeline_config.vertex_api_key)
deepseek_ok = bool(pipeline_config.deepseek_api_key)
ffmpeg_ok = st.session_state.ffmpeg_path is not None

st.sidebar.subheader("API Keys")
st.sidebar.markdown(f"{'🟢' if vertex_ok else '🔴'} Vertex AI")
st.sidebar.markdown(f"{'🟢' if deepseek_ok else '🔴'} DeepSeek")
st.sidebar.markdown(f"{'🟢' if ffmpeg_ok else '🔴'} ffmpeg")

st.sidebar.subheader("Project Files")
if output_state["srt_files"]:
    st.sidebar.markdown(f"SRT: {len(output_state['srt_files'])} files")
if output_state["wav_files"]:
    st.sidebar.markdown(f"WAV: {len(output_state['wav_files'])} segments")
if output_state["fcpxml_files"]:
    st.sidebar.markdown(f"FCPXML: {len(output_state['fcpxml_files'])} files")

st.sidebar.subheader("Target Languages")
available_langs = list(pipeline_config.LANG_NAMES.keys())
selected = st.sidebar.multiselect(
    "Languages to generate",
    options=available_langs,
    default=[l for l in st.session_state.selected_langs if l in available_langs],
)
st.session_state.selected_langs = set(selected)

st.sidebar.subheader("Phase Progress")
phases = [
    ("Phase 1.5 — Transcription", st.session_state.transcribed),
    ("Phase 2 — Video & SRT", bool(st.session_state.video_path) and bool(st.session_state.srt_path)),
    ("Phase 3 — Translation", len(st.session_state.translated_langs) > 0),
    ("Phase 4 — Voiceover", len(st.session_state.tts_complete) > 0),
    ("Phase 5 — FCPXML", len(st.session_state.fcpxml_generated) > 0),
]
for label, done in phases:
    st.sidebar.markdown(f"{'✅' if done else '⬜'} {label}")

if st.session_state.is_running:
    st.sidebar.warning(f"⏳ Running: {st.session_state.current_run}")

st.header("Quick Start")

url = st.text_input("YouTube URL", value=st.session_state.youtube_url, placeholder="https://www.youtube.com/watch?v=...")
st.session_state.youtube_url = url

if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    if st.button("Run Full Pipeline", use_container_width=True, disabled=not url or not st.session_state.selected_langs):
        st.info("Use the sidebar pages to run individual phases. Full pipeline run coming soon.")
with col2:
    if st.button("Reset Session", use_container_width=True):
        for key, default in STATE_KEYS.items():
            st.session_state[key] = default
        try:
            st.session_state.ffmpeg_path = find_ffmpeg()
        except FileNotFoundError:
            st.session_state.ffmpeg_path = None
        st.rerun()

st.header("Output Files")

if output_state["all_files"]:
    file_data = []
    for fname, size in output_state["all_files"].items():
        ext = os.path.splitext(fname)[1]
        file_data.append({"File": fname, "Size (KB)": f"{size / 1024:.1f}", "Type": ext})
    st.dataframe(file_data, use_container_width=True, hide_index=True)
else:
    st.info("No output files yet. Start by downloading a video on the Video page.")

st.markdown("---")
st.caption("Navigate to individual phases using the sidebar: Video → Subtitles → Voiceover → FCPXML")
