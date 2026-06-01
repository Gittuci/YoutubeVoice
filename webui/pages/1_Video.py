import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pipeline.config
from pipeline.utils import parse_srt

from webui.log_capture import run_with_logs
from webui.shared import init_session_state, get_vertex_client, STATE_KEYS

init_session_state()

st.set_page_config(page_title="Phase 2 — Video", page_icon="🎥")

st.title("🎥 Phase 2 — Video Download & Analysis")

if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

client = get_vertex_client()

if client is None:
    st.error("Vertex AI client not available. Check your VERTEX_API_KEY in .env.")
    st.stop()

st.markdown("### Download YouTube Video")

url = st.text_input(
    "YouTube URL",
    value=st.session_state.youtube_url,
    placeholder="https://www.youtube.com/watch?v=...",
    key="video_page_url",
)
st.session_state.youtube_url = url

video_done = bool(st.session_state.video_path)

col1, col2 = st.columns(2)

with col1:
    if video_done:
        st.success(f"✅ Downloaded: {os.path.basename(st.session_state.video_path)}")
        st.button("Download Video", disabled=True)
    else:
        if st.button("Download Video", use_container_width=True, disabled=not url):
            st.session_state.is_running = True
            st.session_state.current_run = "Phase 2: Video Download"

            from pipeline.eyes import download_video

            temp_video_path = os.path.join(pipeline.config.TEMP_DIR, "video.mp4")
            os.makedirs(pipeline.config.TEMP_DIR, exist_ok=True)

            with st.status("Downloading video...", expanded=True) as status:
                try:
                    actual_path, log_text = run_with_logs(download_video, url, temp_video_path)
                    st.session_state.video_path = actual_path
                    st.text(log_text)
                    status.update(label="Download complete!", state="complete")
                except Exception as e:
                    status.update(label=f"Download failed: {e}", state="error")
                    st.error(str(e))

            st.session_state.is_running = False
            st.session_state.current_run = None
            st.rerun()

with col2:
    srt_done = bool(st.session_state.srt_path)
    if srt_done:
        st.success(f"✅ Analyzed: {os.path.basename(st.session_state.srt_path)}")
        st.button("Analyze Video", disabled=True)
    else:
        if st.button("Analyze Video", use_container_width=True, disabled=not video_done):
            st.session_state.is_running = True
            st.session_state.current_run = "Phase 2: Video Analysis"

            from pipeline.eyes import analyze_video, _validate_srt

            with st.status("Analyzing video with Gemini Vision...", expanded=True) as status:
                try:
                    srt_text, log_text = run_with_logs(analyze_video, st.session_state.video_path, client)
                    st.text(log_text)

                    st.write("Validating SRT...")
                    srt_text = _validate_srt(srt_text)

                    output_path = os.path.join(pipeline.config.OUTPUT_DIR, "master_hu.srt")
                    os.makedirs(pipeline.config.OUTPUT_DIR, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(srt_text)

                    st.session_state.srt_path = output_path
                    status.update(label=f"Analysis complete! SRT saved: {output_path}", state="complete")
                except Exception as e:
                    status.update(label=f"Analysis failed: {e}", state="error")
                    st.error(str(e))

            st.session_state.is_running = False
            st.session_state.current_run = None
            st.rerun()

if st.session_state.video_path:
    st.markdown("### Video Info")
    try:
        from pipeline.fcpxml import _get_video_info
        info = _get_video_info(st.session_state.video_path, st.session_state.ffmpeg_path)
        c1, c2, c3 = st.columns(3)
        c1.metric("Resolution", f"{info['width']}x{info['height']}")
        c2.metric("Frame Rate", f"{info['frame_rate']:.2f} fps")
        c3.metric("Duration", f"{info['duration']:.1f}s")
    except Exception as e:
        st.warning(f"Could not read video info: {e}")

if st.session_state.srt_path and os.path.isfile(st.session_state.srt_path):
    st.markdown("### SRT Preview")
    with st.expander("Show SRT content", expanded=False):
        try:
            entries = parse_srt(st.session_state.srt_path)
            rows = []
            for e in entries:
                start = e["start_seconds"]
                end = e["end_seconds"]
                start_ts = f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{start % 60:06.3f}".replace(".", ",")
                end_ts = f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{end % 60:06.3f}".replace(".", ",")
                rows.append({"#": e["index"], "Timestamp": f"{start_ts} → {end_ts}", "Text": e["text"][:100]})
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(f"Total entries: {len(entries)}")
        except Exception as e:
            st.error(f"Could not parse SRT: {e}")
