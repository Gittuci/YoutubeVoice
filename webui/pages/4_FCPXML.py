import os
import sys
import html
import wave as wavemod
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pipeline.config
from pipeline.utils import parse_srt, wav_segment_name, ensure_output_video, wav_is_valid

from webui.log_capture import run_with_logs
from webui.shared import init_session_state, STATE_KEYS

init_session_state()

st.set_page_config(page_title="Phase 5 — FCPXML", page_icon="🎞️")

st.title("🎞️ Phase 5 — FCPXML Export for DaVinci Resolve")

if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

output_dir = pipeline.config.OUTPUT_DIR
wav_dir = os.path.join(output_dir, pipeline.config.WAV_SEGMENTS_DIR)

video_path = st.session_state.video_copy_path or st.session_state.video_path
if not video_path or not os.path.isfile(video_path):
    st.warning("No video available. Complete Phase 2 first.")
    st.stop()

languages_with_tts = [lang for lang, done in st.session_state.tts_complete.items() if done]

if not languages_with_tts:
    st.warning("No languages have generated voiceovers. Complete Phase 4 first.")
    st.stop()

st.markdown("### Generate FCPXML")
selected_lang = st.selectbox(
    "Language",
    options=languages_with_tts,
    format_func=lambda l: f"{l} \u2014 {pipeline.config.LANG_NAMES.get(l, l)}",
)

srt_path = os.path.join(output_dir, f"master_{selected_lang}.srt")

if st.button("Generate FCPXML", use_container_width=True, disabled=st.session_state.fcpxml_generated.get(selected_lang, False)):
    st.session_state.is_running = True
    st.session_state.current_run = f"Phase 5: FCPXML \u2014 {selected_lang}"

    from pipeline.fcpxml import build_fcpxml

    video_for_fcpxml = ensure_output_video(output_dir, video_path)
    st.session_state.video_copy_path = video_for_fcpxml

    entries = parse_srt(srt_path)
    wav_segments = []
    for i, entry in enumerate(entries):
        wav_filename = wav_segment_name(selected_lang, i)
        wav_path = os.path.join(wav_dir, wav_filename)
        if not wav_is_valid(wav_path):
            continue
        with wavemod.open(wav_path, "rb") as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            wav_dur = nframes / framerate if framerate > 0 else 0.0
        wav_segments.append((wav_path, entry["start_seconds"], wav_dur))

    fcpxml_output = os.path.join(output_dir, f"fcpxml_{selected_lang}.fcpxml")

    with st.status(f"Building FCPXML for {selected_lang}...", expanded=True) as status:
        try:
            result_path, log_text = run_with_logs(
                build_fcpxml,
                video_for_fcpxml,
                srt_path,
                selected_lang,
                wav_segments,
                fcpxml_output,
                st.session_state.ffmpeg_path,
            )
            st.text(log_text)

            fcpxml_gen = dict(st.session_state.fcpxml_generated)
            fcpxml_gen[selected_lang] = True
            st.session_state.fcpxml_generated = fcpxml_gen

            size_kb = os.path.getsize(result_path) / 1024
            status.update(label=f"FCPXML saved ({size_kb:.1f} KB)", state="complete")
            st.success(f"Generated: {result_path} ({size_kb:.1f} KB)")
        except Exception as e:
            status.update(label=f"FCPXML generation failed: {e}", state="error")
            st.error(str(e))

    st.session_state.is_running = False
    st.session_state.current_run = None
    st.rerun()

if st.session_state.fcpxml_generated.get(selected_lang):
    fcpxml_path = os.path.join(output_dir, f"fcpxml_{selected_lang}.fcpxml")
    if os.path.isfile(fcpxml_path):
        st.success(f"✅ FCPXML already generated for {selected_lang}")
        with open(fcpxml_path, "r", encoding="utf-8") as f:
            fcpxml_content = f.read()
        st.download_button(
            label=f"⬇ Download fcpxml_{selected_lang}.fcpxml",
            data=fcpxml_content,
            file_name=f"fcpxml_{selected_lang}.fcpxml",
            mime="application/xml",
            use_container_width=True,
        )

st.markdown("### Timeline Preview")
try:
    entries = parse_srt(srt_path)
    if entries:
        max_time = entries[-1]["end_seconds"]
        st.caption(f"Timeline: 0.0s \u2014 {max_time:.1f}s")

        colors = {"hu": "#3498db", "en": "#2ecc71", "de": "#e74c3c", "es": "#f39c12", "fr": "#9b59b6"}
        color = colors.get(selected_lang, "#3498db")

        html_builder = '<div style="position:relative; height:40px; background:#1a1a2e; border-radius:4px; margin:10px 0;">'
        for e in entries[:100]:
            start_pct = (e["start_seconds"] / max_time) * 100 if max_time > 0 else 0
            width_pct = ((e["end_seconds"] - e["start_seconds"]) / max_time) * 100 if max_time > 0 else 0
            html_builder += f'<div style="position:absolute; left:{start_pct:.2f}%; width:{width_pct:.2f}%; height:100%; background:{color}; opacity:0.7; border-right:1px solid #fff;" title="#{e["index"]}: {html.escape(e["text"][:50])}"></div>'
        html_builder += '</div>'
        st.markdown(html_builder, unsafe_allow_html=True)
        st.caption(f"Showing {min(len(entries), 100)} of {len(entries)} segments")
except Exception as e:
    st.warning(f"Could not render timeline: {e}")

st.markdown("### Import Instructions")
st.markdown("""
1. Open **DaVinci Resolve**
2. **File \u2192 Import \u2192 Timeline** (select `.fcpxml` file)
3. The video will appear on Track 1 (muted) and WAV voiceover clips at correct timestamps
4. Adjust audio levels and export as needed
""")

st.markdown("### Generated FCPXML Files")
fcpxml_gen = dict(st.session_state.fcpxml_generated)
if fcpxml_gen:
    for lang, done in fcpxml_gen.items():
        if done:
            path = os.path.join(output_dir, f"fcpxml_{lang}.fcpxml")
            if os.path.isfile(path):
                size_kb = os.path.getsize(path) / 1024
                with st.expander(f"fcpxml_{lang}.fcpxml ({size_kb:.1f} KB)", expanded=False):
                    with open(path, "r", encoding="utf-8") as f:
                        st.code(f.read()[:2000], language="xml")
else:
    st.info("No FCPXML files generated yet.")
