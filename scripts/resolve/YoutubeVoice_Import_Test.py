"""Internal DaVinci Resolve utility for the YoutubeVoice P0 delivery test.

Install this file in Resolve's per-user Fusion/Scripts/Utility directory, then
run it from Workspace > Scripts. It uses Resolve's internal ``resolve`` global,
so it works without external scripting access.
"""

from __future__ import annotations

import hashlib
import json
import time
import traceback
from pathlib import Path


ROOT = Path(r"C:\Projects\YoutubeVoice")
RUN = ROOT / "output" / "test_runs" / "2026-09-27_111835"
DELIVERY = RUN / "resolve_delivery"
VIDEO = ROOT / "output" / "video.mp4"
FCPXML = DELIVERY / "youtubevoice_hu.fcpxml"
CAPTIONS = DELIVERY / "captions_hu.srt"

VIDEO_SHA256 = "6582AC24DF91F6CBD89F71FCBFAC7E7C7421BAE9489E71C5734F3CDA0887D7FB"
EXPECTED_NARRATION = {
    "hu_01.wav": 1.000000,
    "hu_02.wav": 16.000000,
    "hu_03.wav": 47.000000,
    "hu_04.wav": 73.111053,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def get_resolve():
    internal = globals().get("resolve")
    if internal is not None and hasattr(internal, "GetProjectManager"):
        return internal
    import DaVinciResolveScript as dvr_script

    external = dvr_script.scriptapp("Resolve")
    if external is None:
        raise RuntimeError("Could not obtain the Resolve application object")
    return external


def clip_record(item, timeline_start: float, fps: float) -> dict[str, object]:
    media_pool_item = item.GetMediaPoolItem()
    properties = media_pool_item.GetClipProperty() if media_pool_item else {}
    start_frame = float(item.GetStart(True))
    end_frame = float(item.GetEnd(True))
    return {
        "name": item.GetName(),
        "type": item.GetType(),
        "start_frame": start_frame,
        "end_frame": end_frame,
        "start_seconds": (start_frame - timeline_start) / fps,
        "end_seconds": (end_frame - timeline_start) / fps,
        "file_path": properties.get("File Path") or None,
    }


def main() -> None:
    run_stamp = time.strftime("%Y-%m-%d_%H%M%S")
    project_name = f"YoutubeVoice_Script_Test_{run_stamp}"
    report_path = RUN / f"resolve_internal_script_report_{run_stamp}.json"
    report: dict[str, object] = {
        "status": "failed",
        "started_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "project_name": project_name,
        "provider_calls": 0,
        "inputs": {
            "video": str(VIDEO),
            "fcpxml": str(FCPXML),
            "captions": str(CAPTIONS),
        },
        "steps": [],
    }

    try:
        required = (VIDEO, FCPXML, CAPTIONS)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing required inputs: {missing}")
        actual_video_hash = sha256(VIDEO)
        if actual_video_hash != VIDEO_SHA256:
            raise RuntimeError(f"Authoritative video hash mismatch: {actual_video_hash}")
        report["video_sha256"] = actual_video_hash
        report["steps"].append("Verified authoritative source-video hash")

        app = get_resolve()
        report["resolve_product"] = app.GetProductName()
        report["resolve_version"] = app.GetVersionString()
        project_manager = app.GetProjectManager()

        current_project = project_manager.GetCurrentProject()
        if current_project is not None:
            report["previous_project"] = current_project.GetName()
            report["previous_project_saved"] = bool(project_manager.SaveProject())

        project = project_manager.CreateProject(project_name)
        if project is None:
            raise RuntimeError(f"Resolve could not create isolated project {project_name}")
        report["steps"].append("Created isolated timestamped project")

        requested_settings = {
            "timelineFrameRate": "29.97",
            "timelineResolutionWidth": "640",
            "timelineResolutionHeight": "360",
        }
        report["project_settings_request_accepted"] = bool(
            project.SetSettings(requested_settings)
        )
        report["project_settings_after_request"] = {
            key: project.GetSettings().get(key) for key in requested_settings
        }

        media_pool = project.GetMediaPool()
        timeline = media_pool.ImportTimelineFromFile(
            str(FCPXML),
            {
                "timelineName": "YoutubeVoice HU ElevenLabs Natural Script Test",
                "importSourceClips": True,
                "sourceClipsPath": str(ROOT),
            },
        )
        if timeline is None:
            raise RuntimeError("Resolve returned no timeline from the FCPXML import")
        project.SetCurrentTimeline(timeline)
        report["steps"].append("Imported FCPXML timeline")

        settings = timeline.GetSettings()
        fps = float(settings.get("timelineFrameRate") or 29.97)
        timeline_start = float(timeline.GetStartFrame())
        timeline_end = float(timeline.GetEndFrame())
        tracks: dict[str, list[dict[str, object]]] = {}
        flat_items: list[dict[str, object]] = []
        for track_type in ("video", "audio", "subtitle"):
            track_records = []
            for track_index in range(1, timeline.GetTrackCount(track_type) + 1):
                items = timeline.GetItemListInTrack(track_type, track_index) or []
                item_records = [clip_record(item, timeline_start, fps) for item in items]
                flat_items.extend(item_records)
                track_records.append(
                    {
                        "index": track_index,
                        "name": timeline.GetTrackName(track_type, track_index),
                        "items": item_records,
                    }
                )
            tracks[track_type] = track_records

        narration_items = {
            item["name"]: item
            for item in flat_items
            if item["name"] in EXPECTED_NARRATION
        }
        tolerance_seconds = 2.0 / fps
        narration_placement_matches = all(
            name in narration_items
            and abs(float(narration_items[name]["start_seconds"]) - expected_start)
            <= tolerance_seconds
            for name, expected_start in EXPECTED_NARRATION.items()
        )
        video_items = [item for item in flat_items if item["name"] == "video.mp4"]
        resolved_media_paths = [
            item["file_path"] for item in flat_items if item.get("file_path")
        ]
        all_reported_paths_exist = all(Path(path).is_file() for path in resolved_media_paths)

        subtitle_media = media_pool.ImportMedia([str(CAPTIONS)]) or []
        report["subtitle_media_imported"] = bool(subtitle_media)
        report["subtitle_manual_placement"] = {
            "required": True,
            "timeline_start_seconds": 1.0,
            "align_to": "beginning of hu_01.wav",
            "reason": "Resolve's scripting API does not expose deterministic SRT-to-subtitle-track placement.",
        }

        validations = {
            "timeline_frame_rate_is_29_97": abs(fps - 29.97) < 0.001,
            "authoritative_video_present": len(video_items) == 1,
            "four_narration_clips_present": len(narration_items) == 4,
            "narration_placement_matches": narration_placement_matches,
            "all_reported_media_paths_exist": all_reported_paths_exist,
            "no_preview_mp4_referenced": not any(
                "preview" in str(path).lower() for path in resolved_media_paths
            ),
        }
        report["timeline"] = {
            "name": timeline.GetName(),
            "frame_rate": fps,
            "start_frame": timeline_start,
            "end_frame": timeline_end,
            "duration_seconds": (timeline_end - timeline_start) / fps,
            "tracks": tracks,
        }
        report["validations"] = validations
        report["project_saved"] = bool(project_manager.SaveProject())
        if not report["project_saved"]:
            raise RuntimeError("Resolve failed to save the script-created test project")
        if not all(validations.values()):
            raise RuntimeError(f"Imported timeline failed validation: {validations}")

        app.OpenPage("edit")
        report["steps"].append("Validated timeline and saved project")
        report["status"] = "success_pending_manual_subtitle_placement"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
    finally:
        report["finished_at_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        RUN.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        latest_path = RUN / "latest_resolve_internal_script_report.json"
        latest_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


main()
