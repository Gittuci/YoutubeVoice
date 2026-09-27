-- Internal DaVinci Resolve Free utility for the YoutubeVoice P0 delivery test.
-- Run from Workspace > Scripts > Edit > YoutubeVoice_Import_Test.

local ROOT = [[C:\Projects\YoutubeVoice]]
local RUN = ROOT .. [[\output\test_runs\2026-09-27_111835]]
local DELIVERY = RUN .. [[\resolve_delivery]]
local VIDEO = ROOT .. [[\output\video.mp4]]
local FCPXML = DELIVERY .. [[\youtubevoice_hu.fcpxml]]
local CAPTIONS = DELIVERY .. [[\captions_hu.srt]]

local EXPECTED_NARRATION = {
    ["hu_01.wav"] = 1.000000,
    ["hu_02.wav"] = 16.000000,
    ["hu_03.wav"] = 47.000000,
    ["hu_04.wav"] = 73.111053,
}

local HAS_FILE_IO = type(io) == "table" and type(io.open) == "function"

local function file_exists(path)
    if not HAS_FILE_IO then return nil end
    local handle = io.open(path, "rb")
    if handle then
        handle:close()
        return true
    end
    return false
end

local function json_escape(value)
    return value:gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\b", "\\b")
        :gsub("\f", "\\f")
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
        :gsub("\t", "\\t")
end

local function is_array(value)
    local count = 0
    local maximum = 0
    for key, _ in pairs(value) do
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
            return false, 0
        end
        count = count + 1
        if key > maximum then maximum = key end
    end
    return count == maximum, maximum
end

local function json_encode(value, indent)
    indent = indent or 0
    local kind = type(value)
    if kind == "nil" then return "null" end
    if kind == "boolean" or kind == "number" then return tostring(value) end
    if kind == "string" then return '"' .. json_escape(value) .. '"' end
    if kind ~= "table" then return '"' .. json_escape(tostring(value)) .. '"' end

    local prefix = string.rep("  ", indent)
    local child_prefix = string.rep("  ", indent + 1)
    local array, length = is_array(value)
    local parts = {}
    if array then
        for index = 1, length do
            parts[#parts + 1] = child_prefix .. json_encode(value[index], indent + 1)
        end
        if #parts == 0 then return "[]" end
        return "[\n" .. table.concat(parts, ",\n") .. "\n" .. prefix .. "]"
    end

    local keys = {}
    for key, _ in pairs(value) do keys[#keys + 1] = tostring(key) end
    table.sort(keys)
    for _, key in ipairs(keys) do
        parts[#parts + 1] = child_prefix
            .. '"' .. json_escape(key) .. '": '
            .. json_encode(value[key], indent + 1)
    end
    if #parts == 0 then return "{}" end
    return "{\n" .. table.concat(parts, ",\n") .. "\n" .. prefix .. "}"
end

local function write_json(path, value)
    if not HAS_FILE_IO then return false end
    local handle, open_error = io.open(path, "wb")
    if not handle then error("Could not write report: " .. tostring(open_error)) end
    handle:write(json_encode(value, 0), "\n")
    handle:close()
    return true
end

local function append_step(report, step)
    report.steps[#report.steps + 1] = step
end

local function error_with_traceback(message)
    -- Resolve's internal Lua sandbox may not expose the debug library.
    if debug and debug.traceback then
        return debug.traceback(message, 2)
    end
    return tostring(message)
end

local function get_resolve_application()
    -- Internal menu scripts receive `resolve` as a global. The Resolve()
    -- function is primarily needed by the standalone Lua interpreter.
    local internal_resolve = rawget(_G, "resolve")
    if internal_resolve then return internal_resolve end

    local resolve_factory = rawget(_G, "Resolve")
    if type(resolve_factory) == "function" then
        return resolve_factory()
    end
    return nil
end

local run_stamp = os.date("%Y-%m-%d_%H%M%S")
local project_name = "YoutubeVoice_Lua_Test_" .. run_stamp
local report_path = RUN .. "\\resolve_internal_lua_report_" .. run_stamp .. ".json"
local latest_path = RUN .. [[\latest_resolve_internal_lua_report.json]]
local report = {
    status = "failed",
    started_at_local = os.date("%Y-%m-%dT%H:%M:%S%z"),
    project_name = project_name,
    provider_calls = 0,
    script_language = "Lua 5.1",
    filesystem_checks_available = HAS_FILE_IO,
    steps = {},
    inputs = {video = VIDEO, fcpxml = FCPXML, captions = CAPTIONS},
}

-- File access is intentionally unavailable in Resolve's default safe internal
-- scripting mode. External Lua writes a launch marker; internal Lua reports to
-- the Console and records its result by saving the timestamped Resolve project.
if HAS_FILE_IO then write_json(latest_path, report) end

local ok, failure = xpcall(function()
    for _, path in ipairs({VIDEO, FCPXML, CAPTIONS}) do
        local exists = file_exists(path)
        if exists == false then error("Missing required input: " .. path) end
    end
    if HAS_FILE_IO then
        append_step(report, "Verified required delivery files exist")
    else
        append_step(report, "Resolve safe mode blocks direct file checks; import paths supplied to Resolve")
    end

    local app = get_resolve_application()
    if not app then error("Resolve application object is unavailable") end
    report.resolve_product = app:GetProductName()
    report.resolve_version = app:GetVersionString()

    local project_manager = app:GetProjectManager()
    local current_project = project_manager:GetCurrentProject()
    if current_project then
        report.previous_project = current_project:GetName()
        report.previous_project_saved = project_manager:SaveProject() and true or false
    end

    local project = project_manager:CreateProject(project_name)
    if not project then error("Could not create isolated project " .. project_name) end
    append_step(report, "Created isolated timestamped project")

    report.project_settings_request_accepted = project:SetSettings({
        timelineFrameRate = "29.97",
        timelineResolutionWidth = "640",
        timelineResolutionHeight = "360",
    }) and true or false

    local project_settings = project:GetSettings()
    report.project_settings_after_request = {
        timelineFrameRate = tostring(project_settings.timelineFrameRate),
        timelineResolutionWidth = tostring(project_settings.timelineResolutionWidth),
        timelineResolutionHeight = tostring(project_settings.timelineResolutionHeight),
    }

    local media_pool = project:GetMediaPool()
    local timeline = media_pool:ImportTimelineFromFile(FCPXML, {
        timelineName = "YoutubeVoice HU ElevenLabs Natural Lua Test",
        importSourceClips = true,
        sourceClipsPath = ROOT,
    })
    if not timeline then error("Resolve returned no timeline from FCPXML import") end
    project:SetCurrentTimeline(timeline)
    append_step(report, "Imported FCPXML timeline")

    local settings = timeline:GetSettings()
    local fps = tonumber(settings.timelineFrameRate) or 29.97
    local timeline_start = tonumber(timeline:GetStartFrame()) or 0
    local timeline_end = tonumber(timeline:GetEndFrame()) or timeline_start
    local tracks = {}
    local flat_items = {}

    for _, track_type in ipairs({"video", "audio", "subtitle"}) do
        local track_records = {}
        local track_count = timeline:GetTrackCount(track_type) or 0
        for track_index = 1, track_count do
            local item_records = {}
            local items = timeline:GetItemListInTrack(track_type, track_index) or {}
            for key, value in pairs(items) do
                -- Resolve's Lua bridge can expose object lists as either
                -- index->object or object->index tables depending on context.
                local item = value
                if type(item) == "number" then item = key end
                -- Subtitle timeline objects do not expose GetMediaPoolItem.
                local media_pool_item = nil
                if item.GetMediaPoolItem then
                    media_pool_item = item:GetMediaPoolItem()
                end
                local properties = media_pool_item and media_pool_item:GetClipProperty() or {}
                local start_frame = item.GetStart and (tonumber(item:GetStart(true)) or 0) or 0
                local end_frame = item.GetEnd and (tonumber(item:GetEnd(true)) or 0) or 0
                local record = {
                    name = item.GetName and item:GetName() or (track_type .. " item"),
                    type = item.GetType and item:GetType() or track_type,
                    track_type = track_type,
                    start_seconds = (start_frame - timeline_start) / fps,
                    end_seconds = (end_frame - timeline_start) / fps,
                    file_path = properties["File Path"],
                }
                item_records[#item_records + 1] = record
                flat_items[#flat_items + 1] = record
            end
            track_records[#track_records + 1] = {
                index = track_index,
                name = timeline:GetTrackName(track_type, track_index),
                items = item_records,
            }
        end
        tracks[track_type] = track_records
    end

    local narration_items = {}
    local video_count = 0
    local all_paths_exist = true
    local no_preview = true
    for _, item in ipairs(flat_items) do
        if EXPECTED_NARRATION[item.name] then narration_items[item.name] = item end
        local lower_name = string.lower(item.name or "")
        local lower_path = string.lower(item.file_path or "")
        if item.track_type == "video"
            and (lower_name == "video.mp4"
                or lower_name == "authoritative_video.mp4"
                or string.match(lower_path, "[/\\]video%.mp4$") ~= nil) then
            video_count = video_count + 1
        end
        if item.file_path and item.file_path ~= "" then
            local exists = file_exists(item.file_path)
            if exists == false then all_paths_exist = false end
            if string.find(string.lower(item.file_path), "preview", 1, true) then no_preview = false end
        end
    end

    local narration_count = 0
    local placement_matches = true
    local tolerance_seconds = 2.0 / fps
    for name, expected_start in pairs(EXPECTED_NARRATION) do
        local item = narration_items[name]
        if item then
            narration_count = narration_count + 1
            if math.abs(item.start_seconds - expected_start) > tolerance_seconds then
                placement_matches = false
            end
        else
            placement_matches = false
        end
    end

    local subtitle_media = media_pool:ImportMedia({CAPTIONS}) or {}
    report.subtitle_media_imported = next(subtitle_media) ~= nil
    report.subtitle_manual_placement = {
        required = true,
        timeline_start_seconds = 1.0,
        align_to = "beginning of hu_01.wav",
        reason = "Resolve scripting does not expose deterministic SRT placement on a subtitle track",
    }

    local validations = {
        timeline_frame_rate_is_29_97 = math.abs(fps - 29.97) < 0.001,
        authoritative_video_present = video_count == 1,
        four_narration_clips_present = narration_count == 4,
        narration_placement_matches = placement_matches,
        all_reported_media_paths_exist = all_paths_exist,
        no_preview_mp4_referenced = no_preview,
    }
    report.timeline = {
        name = timeline:GetName(),
        frame_rate = fps,
        start_frame = timeline_start,
        end_frame = timeline_end,
        duration_seconds = (timeline_end - timeline_start) / fps,
        tracks = tracks,
    }
    report.validations = validations

    local failed_validations = {}
    for validation_name, passed in pairs(validations) do
        if not passed then
            failed_validations[#failed_validations + 1] = validation_name
        end
    end
    table.sort(failed_validations)
    if #failed_validations > 0 then
        error("Imported timeline failed validations: " .. table.concat(failed_validations, ", "))
    end
    report.project_saved = project_manager:SaveProject() and true or false
    if not report.project_saved then error("Resolve failed to save the script-created project") end

    app:OpenPage("edit")
    append_step(report, "Validated timeline and saved project")
    report.status = "success_pending_manual_subtitle_placement"
end, error_with_traceback)

if not ok then
    report.error = tostring(failure)
end
report.finished_at_local = os.date("%Y-%m-%dT%H:%M:%S%z")
if HAS_FILE_IO then
    write_json(report_path, report)
    write_json(latest_path, report)
end
print("YoutubeVoice Resolve Lua test: " .. report.status)
if report.subtitle_media_imported == false then
    print("Subtitle: Resolve did not accept SRT through the scripting API. Manually import captions_hu.srt and place it at 1.000 second, aligned with hu_01.wav.")
end
if HAS_FILE_IO then
    print("Report: " .. report_path)
elseif report.error then
    print("Error: " .. report.error)
else
    print("Resolve safe mode blocks JSON file output; the timestamped project is the test record.")
end
