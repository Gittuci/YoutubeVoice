import os
import sys
import time
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pipeline.config
from pipeline.utils import parse_srt

from webui.log_capture import run_with_logs
from webui.shared import init_session_state, get_vertex_client, get_deepseek_client, scan_output_dir, STATE_KEYS

init_session_state()

st.set_page_config(page_title="Phase 3 — Subtitles", page_icon="📝")

st.title("📝 Phase 3 — Subtitle Translation")

if st.session_state.is_running:
    st.warning(f"A process is already running: {st.session_state.current_run}")
    st.stop()

deepseek_client = get_deepseek_client()
gemini_client = get_vertex_client()

if deepseek_client is None:
    st.error("DeepSeek client not available. Check your DEEPSEEK_API_KEY in .env.")
    st.stop()

if not st.session_state.srt_path:
    st.warning("Complete Phase 2 first — no master SRT file available.")
    st.stop()

st.markdown("### Master SRT")
st.info(f"Source SRT: {st.session_state.srt_path}")

master_entries = None
try:
    master_entries = parse_srt(st.session_state.srt_path)
    st.metric("Master entries", len(master_entries) if master_entries else 0)
except Exception as e:
    st.error(f"Could not parse master SRT: {e}")

with st.expander("Preview master SRT", expanded=False):
    if master_entries:
        rows = [{"#": e["index"], "Timestamp": f"{e['start_seconds']:.1f}s → {e['end_seconds']:.1f}s", "Text": e["text"][:80]} for e in master_entries]
        st.dataframe(rows, use_container_width=True, hide_index=True)

st.markdown("### Translate")

available_targets = [l for l in pipeline.config.LANG_NAMES if l != pipeline.config.SOURCE_LANG]
target_langs = st.multiselect(
    "Target languages",
    options=available_targets,
    default=[l for l in st.session_state.selected_langs if l in available_targets],
    key="translate_lang_picker",
)

if st.button("Translate Selected Languages", disabled=not target_langs, use_container_width=True):
    st.session_state.is_running = True
    st.session_state.current_run = "Phase 3: Translation"

    from pipeline.brains import load_master_srt, translate_language

    master_srt_text = load_master_srt(st.session_state.srt_path)
    source_lang_name = pipeline.config.LANG_NAMES.get(pipeline.config.SOURCE_LANG, "Hungarian")

    reference_srt = master_srt_text
    all_langs_to_process = []
    ref_lang = pipeline.config.REFERENCE_LANG

    if ref_lang != pipeline.config.SOURCE_LANG and ref_lang not in st.session_state.translated_langs:
        all_langs_to_process.append(ref_lang)

    for lang in target_langs:
        if lang not in all_langs_to_process:
            all_langs_to_process.append(lang)

    results = []
    progress = st.progress(0, text="Starting...")

    for idx, lang in enumerate(all_langs_to_process):
        lang_name = pipeline.config.LANG_NAMES.get(lang, lang)
        progress.progress((idx) / max(len(all_langs_to_process), 1), text=f"Translating to {lang_name}...")

        srt_source = reference_srt if lang != ref_lang else master_srt_text
        src_name = pipeline.config.LANG_NAMES.get(ref_lang, ref_lang) if lang != ref_lang else source_lang_name

        with st.status(f"Translating to {lang_name} ({lang})...", expanded=True) as status:
            try:
                translated, log_text = run_with_logs(
                    translate_language, srt_source, lang, deepseek_client, gemini_client, src_name
                )
                st.text(log_text)

                output_path = os.path.join(pipeline.config.OUTPUT_DIR, f"master_{lang}.srt")
                os.makedirs(pipeline.config.OUTPUT_DIR, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(translated)

                lang_set = set(st.session_state.translated_langs)
                lang_set.add(lang)
                st.session_state.translated_langs = lang_set

                if lang == ref_lang:
                    reference_srt = translated

                st.success(f"Saved: {output_path}")
                status.update(label=f"Translation to {lang_name} complete!", state="complete")
                results.append((lang, output_path, True, None))
            except Exception as e:
                status.update(label=f"Translation failed: {e}", state="error")
                st.error(str(e))
                results.append((lang, None, False, str(e)))

        time.sleep(1)

    progress.progress(1.0, text="Complete!")

    st.session_state.is_running = False
    st.session_state.current_run = None

    st.markdown("### Results")
    for lang, path, ok, err in results:
        if ok:
            st.success(f"**{lang}**: {path}")
        else:
            st.error(f"**{lang}**: {err}")
    st.rerun()

st.markdown("### Existing Translations")
output_dir = pipeline.config.OUTPUT_DIR
existing = []
if os.path.isdir(output_dir):
    output_state = scan_output_dir()
    for fname in output_state.get("srt_files", set()):
        if fname.startswith("master_") and fname.endswith(".srt") and fname != "master_hu.srt":
            lang_code = fname.replace("master_", "").replace(".srt", "")
            existing.append((lang_code, os.path.join(output_dir, fname)))

if existing:
    for lang_code, path in existing:
        with st.expander(f"master_{lang_code}.srt", expanded=False):
            try:
                entries = parse_srt(path)
                rows = [{"#": e["index"], "Timestamp": f"{e['start_seconds']:.1f}s", "Text": e["text"][:80]} for e in entries]
                st.dataframe(rows, use_container_width=True, hide_index=True)
                st.caption(f"{len(entries)} entries")

                if st.button(f"Delete master_{lang_code}.srt", key=f"del_{lang_code}"):
                    os.unlink(path)
                    lang_set = set(st.session_state.translated_langs)
                    lang_set.discard(lang_code)
                    st.session_state.translated_langs = lang_set
                    st.rerun()
            except Exception as e:
                st.error(f"Could not parse: {e}")
else:
    st.info("No translated SRT files found. Translate some languages above.")
