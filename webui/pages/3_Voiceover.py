import os
import sys
import time
import threading
import wave as wavemod
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pipeline.config
from pipeline.utils import parse_srt, wav_segment_name

from webui.log_capture import run_with_logs
from webui.shared import init_session_state, get_vertex_client, STATE_KEYS

init_session_state()

st.set_page_config(page_title="Phase 4 — Voiceover", page_icon="🔊")

st.title("🔊 Phase 4 — TTS Voiceover Generation")


@st.cache_data(ttl=10)
def _build_segment_rows(srt_path_key, wav_dir_key, lang_key):
    entries = parse_srt(srt_path_key)
    rows = []
    for e in entries:
        wav_filename = wav_segment_name(lang_key, e["index"] - 1)
        wav_path = os.path.join(wav_dir_key, wav_filename)
        wav_exists = os.path.isfile(wav_path) and os.path.getsize(wav_path) > 0
        wav_status = "✅" if wav_exists else "⬜"
        wav_dur = ""
        if wav_exists:
            try:
                with wavemod.open(wav_path, "rb") as wf:
                    wav_dur = f"{wf.getnframes() / wf.getframerate():.1f}s"
            except Exception:
                pass
        rows.append({
            "#": e["index"],
            "Window": f"{e['start_seconds']:.1f}s\u2013{e['end_seconds']:.1f}s ({e['end_seconds'] - e['start_seconds']:.1f}s)",
            "Text": e["text"][:60],
            "WAV": f"{wav_status} {wav_dur}",
        })
    return rows


def _count_existing_wavs(wav_dir_key: str, lang_key: str, total_segments: int) -> int:
    count = 0
    for i in range(total_segments):
        wav_path = os.path.join(wav_dir_key, wav_segment_name(lang_key, i))
        if os.path.isfile(wav_path) and os.path.getsize(wav_path) > 0:
            count += 1
    return count


if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

client = get_vertex_client()

if client is None:
    st.error("Vertex AI client not available. Check your VERTEX_API_KEY in .env.")
    st.stop()

output_dir = pipeline.config.OUTPUT_DIR
wav_dir = os.path.join(output_dir, pipeline.config.WAV_SEGMENTS_DIR)

available_langs = list(pipeline.config.LANG_NAMES.keys())

existing_srts = []
for lang in available_langs:
    srt_path = os.path.join(output_dir, f"master_{lang}.srt")
    if os.path.isfile(srt_path):
        existing_srts.append(lang)

if not existing_srts:
    st.warning("No SRT files found. Complete Phase 2 and Phase 3 first.")
    st.stop()

st.markdown("### Select Language")
selected_lang = st.selectbox("Language", options=existing_srts, format_func=lambda l: f"{l} \u2014 {pipeline.config.LANG_NAMES.get(l, l)}")

srt_path = os.path.join(output_dir, f"master_{selected_lang}.srt")

st.markdown("### Segment Preview")
try:
    rows = _build_segment_rows(srt_path, wav_dir, selected_lang)
    total_segments = len(rows)
    existing_count = _count_existing_wavs(wav_dir, selected_lang, total_segments)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"Total: {total_segments} segments | Language: {selected_lang}")
except Exception as e:
    st.error(f"Could not parse SRT: {e}")
    st.stop()

st.markdown("### Generation Settings")
col_mode, col_workers, col_rpm = st.columns(3)
with col_mode:
    parallel_mode = st.checkbox("Parallel generation", value=True,
                                help="Generate multiple TTS segments concurrently (faster, respects rate limits)")
with col_workers:
    max_workers = st.number_input("Max workers", min_value=1, max_value=5, value=3,
                                   help="Maximum concurrent TTS API calls")
with col_rpm:
    rpm_limit = st.number_input("RPM limit", min_value=1, max_value=60, value=10,
                                 help="Maximum requests per minute (rate limit)")

st.markdown("### Status")
ready_pct = (existing_count / max(total_segments, 1)) * 100
st.progress(ready_pct / 100, text=f"{existing_count} of {total_segments} WAVs cached ({ready_pct:.0f}%)")

already_done = st.session_state.tts_complete.get(selected_lang, False)
gen_button_disabled = already_done

if st.button("Generate Voiceover", use_container_width=True, disabled=gen_button_disabled):
    st.session_state.is_running = True
    st.session_state.current_run = f"Phase 4: TTS \u2014 {selected_lang}"

    lang_name = pipeline.config.LANG_NAMES.get(selected_lang, selected_lang)

    if parallel_mode:
        from pipeline.voice import generate_voiceover_parallel

        progress_lock = threading.Lock()
        gen_progress = {"completed": 0, "total": total_segments, "status": "init", "result": None, "error": None}

        def on_progress(completed, total, status):
            with progress_lock:
                gen_progress["completed"] = completed
                gen_progress["total"] = total
                gen_progress["status"] = status

        def run_generation():
            try:
                segments = generate_voiceover_parallel(
                    srt_path, selected_lang, client,
                    st.session_state.ffmpeg_path, wav_dir,
                    max_workers=max_workers, rpm_limit=rpm_limit,
                    on_progress=on_progress,
                )
                with progress_lock:
                    gen_progress["result"] = segments
            except Exception as e:
                with progress_lock:
                    gen_progress["error"] = str(e)

        gen_thread = threading.Thread(target=run_generation, daemon=True)
        gen_thread.start()

        status_widget = st.status(f"Generating TTS for {lang_name} ({total_segments} segments, parallel)...", expanded=True)
        progress_bar = st.progress(0, text="Initializing...")
        log_area = st.empty()

        _log_lines = []
        def collect_logs():
            with progress_lock:
                c = gen_progress["completed"]
                t = gen_progress["total"]
                s = gen_progress["status"]
            pct = c / max(t, 1)
            label = f"{c} of {t} segments ({s})"
            if s == "cached":
                label += " [cached]"
            progress_bar.progress(pct, text=label)
            _log_lines.append(f"[{s}] {c}/{t}")
            if len(_log_lines) > 30:
                del _log_lines[:-30]
            log_area.code("\n".join(_log_lines), language=None)

        while gen_thread.is_alive():
            collect_logs()
            time.sleep(1.5)

        gen_thread.join(timeout=5)
        collect_logs()

        with progress_lock:
            error = gen_progress["error"]
            segments = gen_progress["result"]

        if error:
            status_widget.update(label=f"Generation failed: {error}", state="error")
            st.error(error)
            st.session_state.is_running = False
            st.session_state.current_run = None
            st.stop()

        progress_bar.progress(1.0, text=f"{len(segments) if segments else 0} segments done!")
        status_widget.update(label=f"Voiceover complete! ({len(segments)}/{total_segments} segments)", state="complete")
        st.success(f"Generated {len(segments)} WAV segments for {selected_lang}")

    else:
        from pipeline.voice import generate_voiceover

        with st.status(f"Generating TTS for {lang_name} ({total_segments} segments, sequential)...", expanded=True) as status_widget:
            try:
                segments, log_text = run_with_logs(
                    generate_voiceover,
                    srt_path, selected_lang, client,
                    st.session_state.ffmpeg_path, wav_dir,
                )
                st.text(log_text)
                status_widget.update(label=f"Voiceover complete! ({len(segments)} segments)", state="complete")
                st.success(f"Generated {len(segments)} WAV segments for {selected_lang}")
            except Exception as e:
                status_widget.update(label=f"Voiceover failed: {e}", state="error")
                st.error(str(e))
                st.session_state.is_running = False
                st.session_state.current_run = None
                st.stop()

    tts_complete = dict(st.session_state.tts_complete)
    tts_complete[selected_lang] = True
    st.session_state.tts_complete = tts_complete

    st.session_state.is_running = False
    st.session_state.current_run = None
    _build_segment_rows.clear()
    st.rerun()

if st.session_state.tts_complete.get(selected_lang):
    st.success(f"✅ Voiceover already generated for {selected_lang}")

st.markdown("### Generated WAV Segments")
if os.path.isdir(wav_dir):
    lang_wavs = sorted([f for f in os.listdir(wav_dir) if f.startswith(f"{selected_lang}_seg_") and f.endswith(".wav")])
    if lang_wavs:
        st.caption(f"{len(lang_wavs)} WAV files for {selected_lang}")
        for wav_file in lang_wavs[:20]:
            wav_path = os.path.join(wav_dir, wav_file)
            col_a, col_b = st.columns([3, 1])
            with col_a:
                try:
                    with wavemod.open(wav_path, "rb") as wf:
                        dur = wf.getnframes() / wf.getframerate()
                    st.caption(f"{wav_file} ({dur:.1f}s)")
                except Exception:
                    st.caption(wav_file)
            with col_b:
                if os.path.getsize(wav_path) < 10 * 1024 * 1024:
                    st.audio(wav_path)
        if len(lang_wavs) > 20:
            st.caption(f"... and {len(lang_wavs) - 20} more files")
    else:
        st.info(f"No WAV files yet for {selected_lang}")

st.markdown("### Voiceover Status")
cols = st.columns(len(available_langs) if available_langs else 1)
for i, lang in enumerate(available_langs):
    done = st.session_state.tts_complete.get(lang, False)
    cols[i].metric(lang, "✅ Done" if done else "⬜ Pending")
