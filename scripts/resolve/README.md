# YoutubeVoice Resolve internal utility

`YoutubeVoice_Import_Test.lua` is the primary non-provider, internal DaVinci Resolve Free validation utility for the accepted Hungarian P0 delivery fixture. The Python version is retained as a reference for environments where Resolve exposes Python 3.

Install it in the current user's Resolve Edit-script directory:

`%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit\YoutubeVoice_Import_Test.lua`

Restart Resolve, then run **Workspace > Scripts > Edit > YoutubeVoice_Import_Test**. The script saves the currently open project, creates an isolated timestamped project, sets 29.97 fps and 640x360, imports the controlled FCPXML, and validates source and narration media/placement.

The Resolve 21 Free installation tested here exposed only its Lua console and did not enumerate the installed Python file. If the Lua menu script is not listed after restart, open **Workspace > Console** (F6) and run:

`dofile([[C:/Projects/YoutubeVoice/scripts/resolve/YVTest.lua]])`

Resolve's default safe internal-Lua mode blocks the standard `io` library. In that mode the script reports its result in the Console and the saved timestamped Resolve project is the execution record; it does not write the optional JSON report. The accepted 2026-09-27 run completed with `success_pending_manual_subtitle_placement`.

Resolve's scripting API does not expose deterministic placement of an imported SRT onto a subtitle track, and Resolve 21.1 Free did not accept this SRT through `MediaPool:ImportMedia`. Import `captions_hu.srt` manually and place the subtitle item at 1.000 second, aligned with `hu_01.wav`.
