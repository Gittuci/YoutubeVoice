import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pipeline.config
from pipeline.utils import parse_srt

from webui.log_capture import run_with_logs
from webui.shared import init_session_state, get_vertex_client

init_session_state()

st.set_page_config(page_title="Phase 1.5 — Transcription", page_icon="🎙️")

st.title("🎙️ Phase 1.5 — Audio Transcription with Tone Tags")

if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

client = get_vertex_client()
if client is None:
    st.error("Vertex AI client not available. Check your VERTEX_API_KEY in .env.")
    st.stop()

TONE_TAGS = [
    "enthusiastic", "calm", "urgent", "explanatory", "slow",
    "emphatic", "questioning", "warm", "matter-of-fact", "excited",
    "gentle", "serious", "encouraging", "step-by-step",
]

TAG_COLORS = {
    "enthusiastic": "#ff6b35", "calm": "#4ecdc4", "urgent": "#e74c3c",
    "explanatory": "#3498db", "slow": "#9b59b6", "emphatic": "#e67e22",
    "questioning": "#f1c40f", "warm": "#ff9ff3", "matter-of-fact": "#95a5a6",
    "excited": "#f39c12", "gentle": "#a29bfe", "serious": "#636e72",
    "encouraging": "#00b894", "step-by-step": "#0984e3",
}

st.markdown("### Audio Source")

audio_source = st.radio(
    "Choose audio source",
    ["Use downloaded video audio", "Upload an audio file"],
    index=0 if st.session_state.video_path else 1,
    horizontal=True,
)

audio_path = None

if audio_source == "Use downloaded video audio":
    if st.session_state.video_path and os.path.isfile(st.session_state.video_path):
        st.success(f"Using video: {os.path.basename(st.session_state.video_path)}")
        audio_path = st.session_state.video_path
    else:
        st.warning("No video downloaded yet. Go to Phase 2 (Video) to download one, or upload an audio file below.")

if audio_source == "Upload an audio file":
    uploaded = st.file_uploader(
        "Upload audio or video file",
        type=["wav", "mp3", "mp4", "webm", "flac", "ogg", "opus", "aac", "m4a", "mkv", "mov", "avi"],
    )
    if uploaded:
        os.makedirs(pipeline.config.TEMP_DIR, exist_ok=True)
        temp_audio = os.path.join(pipeline.config.TEMP_DIR, f"upload_{uploaded.name}")
        with open(temp_audio, "wb") as f:
            f.write(uploaded.getbuffer())
        audio_path = temp_audio
        st.success(f"Uploaded: {uploaded.name}")

st.markdown("### Settings")

col1, col2 = st.columns(2)
with col1:
    transcriber = st.selectbox(
        "Transcriber",
        options=["gemini"],
        index=0,
        help="Speech-to-text model for transcription.",
    )
with col2:
    audio_language = st.selectbox(
        "Audio language",
        options=list(pipeline.config.LANG_NAMES.keys()),
        format_func=lambda k: pipeline.config.LANG_NAMES.get(k, k),
        index=0,
        help="Language spoken in the audio.",
    )

transcribe_done = st.session_state.transcribed

if transcribe_done:
    st.success("Transcription complete")
    st.button("Transcribe Audio", disabled=True)
else:
    if st.button("Transcribe Audio", use_container_width=True, disabled=not audio_path):
        st.session_state.is_running = True
        st.session_state.current_run = "Phase 1.5: Transcription"

        from pipeline.ears import run_transcription

        with st.status("Transcribing audio...", expanded=True) as status:
            try:
                srt_path, log_text = run_with_logs(
                    run_transcription, audio_path, pipeline.config.OUTPUT_DIR, transcriber, audio_language
                )
                st.text(log_text)

                st.session_state.transcribed_srt_path = srt_path
                st.session_state.transcribed = True

                if st.session_state.video_path:
                    st.session_state.srt_path = srt_path

                status.update(label=f"Transcription complete! SRT: {os.path.basename(srt_path)}", state="complete")
            except Exception as e:
                status.update(label=f"Transcription failed: {e}", state="error")
                st.error(str(e))

        st.session_state.is_running = False
        st.session_state.current_run = None
        st.rerun()

if st.session_state.transcribed and st.session_state.transcribed_srt_path:
    srt_path = st.session_state.transcribed_srt_path

    st.markdown("### SRT Preview with Tone Tags")

    try:
        entries = parse_srt(srt_path)
    except Exception:
        entries = []

    if entries:
        import re
        tag_pattern = re.compile(r"^\[(\w+(?:-\w+)*)\]\s*")

        st.caption(f"Total entries: {len(entries)}")

        detected_tags = set()
        tag_entry_map = {}
        for e in entries:
            m = tag_pattern.match(e["text"])
            if m:
                tag = m.group(1)
                detected_tags.add(tag)
                tag_entry_map.setdefault(tag, 0)
                tag_entry_map[tag] += 1

        if detected_tags:
            st.markdown("**Detected Tone Tags**")
            tag_cols = st.columns(min(len(detected_tags), 5))
            sorted_tags = sorted(detected_tags, key=lambda t: tag_entry_map.get(t, 0), reverse=True)
            for i, tag in enumerate(sorted_tags):
                col_idx = i % 5
                count = tag_entry_map.get(tag, 0)
                color = TAG_COLORS.get(tag, "#95a5a6")
                tag_cols[col_idx].markdown(
                    f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.85em;white-space:nowrap">[{tag}] ×{count}</span>',
                    unsafe_allow_html=True,
                )

        st.markdown("**All Segments**")
        with st.expander("Show all SRT segments", expanded=False):
            for e in entries:
                start = e["start_seconds"]
                end = e["end_seconds"]
                start_ts = f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{start % 60:06.3f}".replace(".", ",")
                end_ts = f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{end % 60:06.3f}".replace(".", ",")

                text = e["text"]
                m = tag_pattern.match(text)
                if m:
                    tag = m.group(1)
                    rest = text[m.end():]
                    color = TAG_COLORS.get(tag, "#95a5a6")
                    styled = (
                        f'<span style="background:{color};color:white;padding:1px 6px;border-radius:3px;'
                        f'font-size:0.85em;margin-right:4px">[{tag}]</span> {rest}'
                    )
                else:
                    styled = text

                st.markdown(
                    f'<span style="color:#888;font-size:0.8em">#{e["index"]} {start_ts} → {end_ts}</span> '
                    f'<span style="font-size:0.9em">{styled}</span>',
                    unsafe_allow_html=True,
                )
    else:
        st.warning("SRT parsed but no entries found.")

st.markdown("### Tone Tag Legend")
legend_cols = st.columns(4)
for i, tag in enumerate(TONE_TAGS):
    col_idx = i % 4
    color = TAG_COLORS.get(tag, "#95a5a6")
    legend_cols[col_idx].markdown(
        f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;'
        f'font-size:0.85em">[{tag}]</span>',
        unsafe_allow_html=True,
    )
