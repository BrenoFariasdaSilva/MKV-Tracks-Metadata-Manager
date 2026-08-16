"""
Generate editable track-name rename reports for Matroska video files.
"""

from __future__ import annotations  # Enable modern annotations on older supported Python versions.

import argparse  # Parse command-line arguments.
from dataclasses import dataclass  # Define compact typed records.
import json  # Read and write report JSON.
import os  # Replace completed report files atomically.
from pathlib import Path  # Represent filesystem paths.
import re  # Parse existing report group keys.
import subprocess  # Run ffprobe safely with argument lists.
import sys  # Return meaningful CLI exit statuses.
import tempfile  # Create temporary files for safe report writes.
from typing import Any  # Type dynamic ffprobe JSON values.
from tqdm import tqdm  # Display report-generation progress.

from audio_language_detector import detect_audio_track_language  # Resolve metadata or sampled audio language.
from mkvpropedit_wrapper import find_executable  # Locate MKVToolNix command-line tools.
from subtitle_language_detector import detect_subtitle_track_language  # Resolve metadata or text subtitle language.


INPUT_DIR = "E:/Movies/"  # Store default recursive input directory.
AUDIO_REPORT_PATH = Path(__file__).with_name("audio_report.json")  # Store audio report output beside this script.
SUBTITLE_REPORT_PATH = Path(__file__).with_name("subtitles_report.json")  # Store subtitle report output beside this script.
SUPPORTED_EXTENSIONS = (".mkv", ".mk3d")  # Limit edits to Matroska video containers supported by mkvpropedit.
MISSING_TRACK_NAME = "<missing audio track name>"  # Display unnamed tracks without colliding with empty JSON keys.
MISSING_SUBTITLE_TRACK_NAME = "<missing subtitle track name>"  # Display unnamed subtitle tracks without colliding with empty JSON keys.
ESCAPED_TRACK_NAME_PREFIX = "\\"  # Escape literal marker-like track names in report group keys.
OCCURRENCE_SUFFIX_PATTERN = re.compile(r"^(?P<path>.+) \[audio:(?P<audio>\d+)(?: track-id:(?P<track_id>[^\s\]]+))?(?: uid:(?P<uid>[^\]]+))?(?: stream:(?P<stream>[^\]]+))?\]$")  # Parse occurrence keys.
SUBTITLE_OCCURRENCE_SUFFIX_PATTERN = re.compile(r"^(?P<path>.+) \[subtitle:(?P<subtitle>\d+)(?: track-id:(?P<track_id>[^\s\]]+))?(?: uid:(?P<uid>[^\]]+))?\]$")  # Parse subtitle occurrence keys.
GROUP_KEY_PATTERN = re.compile(r"^(?P<name>.*) \((?P<count>\d+)\)$")  # Parse grouped current-name keys.


@dataclass(frozen=True)
class AudioTrackRecord:
    """
    Stores one audio-track occurrence from one media file.
    """

    file_path: Path  # Store absolute file path.
    relative_path: str  # Store path relative to INPUT_DIR.
    audio_position: int  # Store zero-based audio stream position.
    stream_index: int | None  # Store MKVToolNix track ID.
    track_uid: int | None  # Store Matroska track UID.
    current_name: str  # Store current audio track name metadata.
    detected_language: str  # Store detected canonical language or empty text.


@dataclass(frozen=True)
class VideoTrackRecord:
    """
    Stores one video-track occurrence from one media file.
    """

    file_path: Path  # Store absolute file path.
    relative_path: str  # Store path relative to INPUT_DIR.
    video_position: int  # Store zero-based video stream position.
    stream_index: int | None  # Store MKVToolNix track ID.
    track_uid: int | None  # Store Matroska track UID.
    current_name: str  # Store current video track name metadata.


@dataclass(frozen=True)
class SubtitleTrackRecord:
    """
    Stores one subtitle-track occurrence from one media file.
    """

    file_path: Path  # Store absolute file path.
    relative_path: str  # Store path relative to INPUT_DIR.
    subtitle_position: int  # Store zero-based subtitle stream position.
    stream_index: int | None  # Store MKVToolNix track ID.
    track_uid: int | None  # Store Matroska track UID.
    current_name: str  # Store current subtitle track name metadata.
    detected_language: str  # Store detected canonical language or empty text.
    codec_id: str  # Store Matroska subtitle codec ID.
    codec_name: str  # Store MKVToolNix subtitle codec name.


def display_track_name(track_name: str) -> str:
    """
    Convert a raw track name into a stable report display value.

    :param track_name: Raw audio-track name.
    :return: Report display value.
    """

    normalized_name = track_name.strip()  # Normalize surrounding whitespace.
    if normalized_name == "":  # Verify whether the track name is missing.
        return MISSING_TRACK_NAME  # Return explicit missing-name marker.
    if normalized_name == MISSING_TRACK_NAME or normalized_name.startswith(ESCAPED_TRACK_NAME_PREFIX):  # Verify whether the visible name needs escaping.
        return f"{ESCAPED_TRACK_NAME_PREFIX}{normalized_name}"  # Return escaped visible track name.
    return normalized_name  # Return visible track name.


def raw_track_name(display_name: str) -> str:
    """
    Convert a report display value back into a raw track name.

    :param display_name: Report display value.
    :return: Raw audio-track name.
    """

    if display_name == MISSING_TRACK_NAME:  # Verify whether report value means an empty track name.
        return ""  # Return empty track name.
    if display_name.startswith(ESCAPED_TRACK_NAME_PREFIX):  # Verify whether report value was escaped.
        return display_name[1:]  # Return unescaped track name.
    return display_name  # Return regular display value.


def display_subtitle_track_name(track_name: str) -> str:
    """
    Convert a raw subtitle track name into a stable report display value.

    :param track_name: Raw subtitle track name.
    :return: Report display value.
    """

    normalized_name = track_name.strip()  # Normalize surrounding whitespace.
    if normalized_name == "":  # Verify whether the track name is missing.
        return MISSING_SUBTITLE_TRACK_NAME  # Return explicit missing-name marker.
    if normalized_name == MISSING_SUBTITLE_TRACK_NAME or normalized_name.startswith(ESCAPED_TRACK_NAME_PREFIX):  # Verify whether the visible name needs escaping.
        return f"{ESCAPED_TRACK_NAME_PREFIX}{normalized_name}"  # Return escaped visible track name.
    return normalized_name  # Return visible track name.


def raw_subtitle_track_name(display_name: str) -> str:
    """
    Convert a subtitle report display value back into a raw track name.

    :param display_name: Subtitle report display value.
    :return: Raw subtitle track name.
    """

    if display_name == MISSING_SUBTITLE_TRACK_NAME:  # Verify whether report value means an empty track name.
        return ""  # Return empty track name.
    if display_name.startswith(ESCAPED_TRACK_NAME_PREFIX):  # Verify whether report value was escaped.
        return display_name[1:]  # Return unescaped track name.
    return display_name  # Return regular display value.


def parse_group_key(group_key: str) -> tuple[str, int | None]:
    """
    Parse a grouped report key into display name and occurrence count.

    :param group_key: Report group key.
    :return: Display name and parsed count when available.
    """

    match = GROUP_KEY_PATTERN.match(group_key)  # Match trailing occurrence count.
    if match is None:  # Verify whether the group key has expected form.
        return group_key, None  # Return unparsed group key.
    return match.group("name"), int(match.group("count"))  # Return parsed display name and count.


def build_occurrence_key(track: AudioTrackRecord) -> str:
    """
    Build a unique editable key for one audio-track occurrence.

    :param track: Audio track occurrence.
    :return: Unique occurrence key.
    """

    track_id_label = str(track.stream_index) if track.stream_index is not None else "unknown"  # Build MKVToolNix track ID label.
    uid_label = str(track.track_uid) if track.track_uid is not None else "unknown"  # Build Matroska track UID label.
    return f"{track.relative_path} [audio:{track.audio_position + 1} track-id:{track_id_label} uid:{uid_label}]"  # Return path plus exact track identity.


def parse_occurrence_key(occurrence_key: str) -> tuple[str, int, int | None, int | None] | None:
    """
    Parse a report occurrence key into relative path and zero-based audio position.

    :param occurrence_key: Report occurrence key.
    :return: Relative path, zero-based audio position, track ID, and track UID, or None.
    """

    match = OCCURRENCE_SUFFIX_PATTERN.match(occurrence_key)  # Match occurrence suffix.
    if match is None:  # Verify whether occurrence key has expected shape.
        return None  # Return no parsed occurrence.
    audio_position = int(match.group("audio")) - 1  # Convert one-based report ordinal to zero-based position.
    if audio_position < 0:  # Verify parsed audio position is valid.
        return None  # Return no parsed occurrence.
    raw_track_id = match.group("track_id") or match.group("stream")  # Read current or legacy track ID label.
    raw_uid = match.group("uid")  # Read Matroska track UID label.
    track_id = int(raw_track_id) if raw_track_id is not None and raw_track_id.isdigit() else None  # Parse track ID when numeric.
    track_uid = int(raw_uid) if raw_uid is not None and raw_uid.isdigit() else None  # Parse track UID when numeric.
    return match.group("path"), audio_position, track_id, track_uid  # Return parsed occurrence identity.


def build_subtitle_occurrence_key(track: SubtitleTrackRecord) -> str:
    """
    Build a unique editable key for one subtitle-track occurrence.

    :param track: Subtitle track occurrence.
    :return: Unique occurrence key.
    """

    track_id_label = str(track.stream_index) if track.stream_index is not None else "unknown"  # Build MKVToolNix track ID label.
    uid_label = str(track.track_uid) if track.track_uid is not None else "unknown"  # Build Matroska track UID label.
    return f"{track.relative_path} [subtitle:{track.subtitle_position + 1} track-id:{track_id_label} uid:{uid_label}]"  # Return path plus exact track identity.


def parse_subtitle_occurrence_key(occurrence_key: str) -> tuple[str, int, int | None, int | None] | None:
    """
    Parse a subtitle report occurrence key into relative path and zero-based subtitle position.

    :param occurrence_key: Subtitle report occurrence key.
    :return: Relative path, zero-based subtitle position, track ID, and track UID, or None.
    """

    match = SUBTITLE_OCCURRENCE_SUFFIX_PATTERN.match(occurrence_key)  # Match occurrence suffix.
    if match is None:  # Verify whether occurrence key has expected shape.
        return None  # Return no parsed occurrence.
    subtitle_position = int(match.group("subtitle")) - 1  # Convert one-based report ordinal to zero-based position.
    if subtitle_position < 0:  # Verify parsed subtitle position is valid.
        return None  # Return no parsed occurrence.
    raw_track_id = match.group("track_id")  # Read track ID label.
    raw_uid = match.group("uid")  # Read Matroska track UID label.
    track_id = int(raw_track_id) if raw_track_id is not None and raw_track_id.isdigit() else None  # Parse track ID when numeric.
    track_uid = int(raw_uid) if raw_uid is not None and raw_uid.isdigit() else None  # Parse track UID when numeric.
    return match.group("path"), subtitle_position, track_id, track_uid  # Return parsed occurrence identity.


def read_existing_desired_names(report_path: Path) -> dict[str, str]:
    """
    Read existing manually edited desired names by current track display name.

    :param report_path: Existing report path.
    :return: Desired-name mapping keyed by track display name.
    """

    if not report_path.exists():  # Verify whether an existing report is present.
        return {}  # Return empty mapping.

    try:  # Read and parse existing JSON report.
        existing_data = json.loads(report_path.read_text(encoding="utf-8"))  # Load existing report JSON.
    except (OSError, json.JSONDecodeError):  # Handle missing, unreadable, or malformed report content.
        return {}  # Return empty mapping.

    if not isinstance(existing_data, dict):  # Verify top-level report shape.
        return {}  # Return empty mapping.

    desired_names: dict[str, str] = {}  # Store safe desired-name values.
    for group_key, group_value in existing_data.items():  # Iterate existing report groups.
        if not isinstance(group_key, str) or not isinstance(group_value, dict):  # Verify group entry shape.
            continue  # Skip malformed group.
        display_name, parsed_count = parse_group_key(group_key)  # Parse current-name display key.
        desired_value = group_value.get("desired_new_name")  # Read desired name field.
        occurrence_count = len([key for key in group_value if key != "desired_new_name"])  # Count existing occurrences.
        if parsed_count is not None and parsed_count != occurrence_count:  # Verify group count matches occurrence entries.
            continue  # Skip unsafe stale group.
        if isinstance(desired_value, str):  # Verify desired value is editable text.
            desired_names[display_name] = desired_value  # Preserve user desired name.

    return desired_names  # Return preserved desired names.


def resolve_selected_file(input_dir: Path, selected_file: str | None) -> Path | None:
    """
    Resolve one exact selected media file under the input directory.

    :param input_dir: Input directory path.
    :param selected_file: Relative or absolute selected file path.
    :return: Selected media path or None.
    """

    if selected_file is None or selected_file.strip() == "":  # Verify whether file selection was provided.
        return None  # Return no selected file.

    try:  # Resolve root and selected media paths.
        root_path = input_dir.resolve(strict=False)  # Resolve input directory path.
        selected_path = Path(selected_file)  # Build selected path object.
        media_path = selected_path if selected_path.is_absolute() else root_path / selected_path  # Resolve relative selections under input directory.
        resolved_media_path = media_path.resolve(strict=False)  # Resolve final selected path.
        resolved_media_path.relative_to(root_path)  # Verify selected path remains under input directory.
    except (OSError, ValueError):  # Handle invalid or escaping selected paths.
        print(f"Selected file is outside input directory or invalid: {selected_file}")  # Report invalid selection.
        return None  # Return no selected file.

    if not resolved_media_path.exists() or not resolved_media_path.is_file():  # Verify selected file exists.
        print(f"Selected file not found: {resolved_media_path}")  # Report missing selected file.
        return None  # Return no selected file.
    if resolved_media_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify selected file is supported Matroska.
        print(f"Selected file is not a supported Matroska file: {resolved_media_path}")  # Report unsupported selected file.
        return None  # Return no selected file.

    return resolved_media_path  # Return exact selected file path.


def discover_supported_files(input_dir: Path, selected_file: str | None = None) -> list[Path]:
    """
    Recursively discover supported Matroska video files.

    :param input_dir: Input directory path.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Sorted supported file paths.
    """

    if not input_dir.exists() or not input_dir.is_dir():  # Verify input directory can be scanned.
        return []  # Return no files when input directory is unavailable.
    selected_path = resolve_selected_file(input_dir, selected_file) if selected_file is not None else None  # Resolve optional selected file.
    if selected_file is not None:  # Verify exact single-file mode was requested.
        return [selected_path] if selected_path is not None else []  # Return only selected media file.

    supported_files: list[Path] = []  # Store discovered Matroska files.
    for file_path in input_dir.rglob("*"):  # Walk every descendant path.
        if not file_path.is_file():  # Verify path is a file.
            continue  # Skip directories and special entries.
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify Matroska video extension.
            continue  # Skip unsupported containers safely.
        supported_files.append(file_path)  # Store supported file.

    return sorted(supported_files, key=lambda path: path.as_posix().lower())  # Return deterministic file order.


def probe_media(file_path: Path) -> dict[str, Any]:
    """
    Read ffprobe stream and format metadata for one media file.

    :param file_path: Media file path.
    :return: Parsed ffprobe metadata.
    """

    executable = find_executable("ffprobe") or "ffprobe"  # Locate ffprobe executable.
    command = [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file_path)]  # Build ffprobe command.
    try:  # Execute ffprobe safely.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run ffprobe.
    except OSError as error:  # Handle unavailable ffprobe or execution failure.
        print(f"ffprobe unavailable for {file_path}: {error}")  # Report inspection failure.
        return {"streams": [], "format": {}}  # Return empty metadata.

    if result.returncode != 0:  # Verify ffprobe succeeded.
        print(f"ffprobe failed for {file_path}: {result.stderr.strip()}")  # Report ffprobe error.
        return {"streams": [], "format": {}}  # Return empty metadata.

    try:  # Parse ffprobe JSON output.
        parsed_data = json.loads(result.stdout) if result.stdout else {"streams": [], "format": {}}  # Decode JSON metadata.
    except json.JSONDecodeError as error:  # Handle invalid ffprobe JSON.
        print(f"ffprobe returned invalid JSON for {file_path}: {error}")  # Report parse failure.
        return {"streams": [], "format": {}}  # Return empty metadata.

    return parsed_data if isinstance(parsed_data, dict) else {"streams": [], "format": {}}  # Return object metadata.


def probe_mkvmerge(file_path: Path) -> dict[str, Any]:
    """
    Read MKVToolNix track metadata for one Matroska file.

    :param file_path: Matroska file path.
    :return: Parsed mkvmerge metadata.
    """

    executable = find_executable("mkvmerge")  # Locate mkvmerge executable.
    if executable is None:  # Verify mkvmerge is available.
        print(f"mkvmerge unavailable for {file_path}: executable not found")  # Report missing mkvmerge.
        return {"tracks": []}  # Return empty metadata.
    command = [executable, "-J", str(file_path)]  # Build mkvmerge JSON command.
    try:  # Execute mkvmerge safely.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run mkvmerge.
    except OSError as error:  # Handle unavailable mkvmerge or execution failure.
        print(f"mkvmerge unavailable for {file_path}: {error}")  # Report inspection failure.
        return {"tracks": []}  # Return empty metadata.

    if result.returncode != 0:  # Verify mkvmerge inspection succeeded.
        print(f"mkvmerge failed for {file_path}: {result.stderr.strip()}")  # Report mkvmerge error.
        return {"tracks": []}  # Return empty metadata.

    try:  # Parse mkvmerge JSON output.
        parsed_data = json.loads(result.stdout) if result.stdout else {"tracks": []}  # Decode JSON metadata.
    except json.JSONDecodeError as error:  # Handle invalid mkvmerge JSON.
        print(f"mkvmerge returned invalid JSON for {file_path}: {error}")  # Report parse failure.
        return {"tracks": []}  # Return empty metadata.

    return parsed_data if isinstance(parsed_data, dict) else {"tracks": []}  # Return object metadata.


def read_mkvmerge_audio_tracks(media_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Read audio tracks in MKVToolNix track order.

    :param media_data: mkvmerge media metadata.
    :return: Audio track metadata objects.
    """

    raw_tracks = media_data.get("tracks")  # Read raw mkvmerge tracks.
    tracks = raw_tracks if isinstance(raw_tracks, list) else []  # Normalize track list.
    audio_tracks: list[dict[str, Any]] = []  # Store audio track objects.
    for raw_track in tracks:  # Iterate mkvmerge tracks in reported order.
        if not isinstance(raw_track, dict):  # Verify track object shape.
            continue  # Skip invalid track.
        if raw_track.get("type") != "audio":  # Verify track is audio.
            continue  # Skip non-audio track.
        audio_tracks.append(raw_track)  # Store audio track.
    return audio_tracks  # Return audio tracks in MKVToolNix order.


def read_mkvmerge_video_tracks(media_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Read video tracks in MKVToolNix track order.

    :param media_data: mkvmerge media metadata.
    :return: Video track metadata objects.
    """

    raw_tracks = media_data.get("tracks")  # Read raw mkvmerge tracks.
    tracks = raw_tracks if isinstance(raw_tracks, list) else []  # Normalize track list.
    video_tracks: list[dict[str, Any]] = []  # Store video track objects.
    for raw_track in tracks:  # Iterate mkvmerge tracks in reported order.
        if not isinstance(raw_track, dict):  # Verify track object shape.
            continue  # Skip invalid track.
        if raw_track.get("type") != "video":  # Verify track is video.
            continue  # Skip non-video track.
        video_tracks.append(raw_track)  # Store video track.
    return video_tracks  # Return video tracks in MKVToolNix order.


def read_mkvmerge_subtitle_tracks(media_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Read subtitle tracks in MKVToolNix track order.

    :param media_data: mkvmerge media metadata.
    :return: Subtitle track metadata objects.
    """

    raw_tracks = media_data.get("tracks")  # Read raw mkvmerge tracks.
    tracks = raw_tracks if isinstance(raw_tracks, list) else []  # Normalize track list.
    subtitle_tracks: list[dict[str, Any]] = []  # Store subtitle track objects.
    for raw_track in tracks:  # Iterate mkvmerge tracks in reported order.
        if not isinstance(raw_track, dict):  # Verify track object shape.
            continue  # Skip invalid track.
        if raw_track.get("type") != "subtitles":  # Verify track is subtitle.
            continue  # Skip non-subtitle track.
        subtitle_tracks.append(raw_track)  # Store subtitle track.
    return subtitle_tracks  # Return subtitle tracks in MKVToolNix order.


def read_mkvmerge_properties(track: dict[str, Any]) -> dict[str, Any]:
    """
    Read mkvmerge track properties.

    :param track: mkvmerge track metadata.
    :return: Track properties object.
    """

    raw_properties = track.get("properties")  # Read raw properties.
    return raw_properties if isinstance(raw_properties, dict) else {}  # Return object properties.


def read_mkvmerge_track_name(track: dict[str, Any]) -> str:
    """
    Read current track name from MKVToolNix metadata.

    :param track: mkvmerge track metadata.
    :return: Current track name.
    """

    properties = read_mkvmerge_properties(track)  # Read track properties.
    for key in ("track_name", "track_name_escaped"):  # Iterate known MKVToolNix name fields.
        value = properties.get(key)  # Read candidate name.
        if isinstance(value, str) and value.strip() != "":  # Verify candidate name is visible.
            return value.strip()  # Return current track name.
    return ""  # Return empty name when metadata is missing.


def read_mkvmerge_track_id(track: dict[str, Any]) -> int | None:
    """
    Read MKVToolNix track ID from mkvmerge metadata.

    :param track: mkvmerge track metadata.
    :return: Track ID or None.
    """

    raw_id = track.get("id")  # Read mkvmerge track ID.
    return raw_id if isinstance(raw_id, int) else None  # Return integer track ID.


def read_mkvmerge_track_uid(track: dict[str, Any]) -> int | None:
    """
    Read Matroska track UID from mkvmerge metadata.

    :param track: mkvmerge track metadata.
    :return: Track UID or None.
    """

    properties = read_mkvmerge_properties(track)  # Read track properties.
    raw_uid = properties.get("uid")  # Read Matroska track UID.
    return raw_uid if isinstance(raw_uid, int) else None  # Return integer track UID.


def read_mkvmerge_codec_id(track: dict[str, Any]) -> str:
    """
    Read Matroska codec ID from mkvmerge metadata.

    :param track: mkvmerge track metadata.
    :return: Codec ID or empty text.
    """

    properties = read_mkvmerge_properties(track)  # Read track properties.
    raw_codec_id = properties.get("codec_id")  # Read codec ID.
    return raw_codec_id if isinstance(raw_codec_id, str) else ""  # Return string codec ID.


def read_mkvmerge_codec_name(track: dict[str, Any]) -> str:
    """
    Read MKVToolNix codec name from mkvmerge metadata.

    :param track: mkvmerge track metadata.
    :return: Codec name or empty text.
    """

    raw_codec = track.get("codec")  # Read codec display value.
    return raw_codec if isinstance(raw_codec, str) else ""  # Return string codec name.


def build_language_metadata_stream(track: dict[str, Any]) -> dict[str, Any]:
    """
    Build language-detection metadata from mkvmerge track properties.

    :param track: mkvmerge track metadata.
    :return: Metadata object compatible with language detection.
    """

    properties = read_mkvmerge_properties(track)  # Read mkvmerge properties.
    tags = {  # Build ffprobe-like tag mapping.
        "language": properties.get("language"),  # Include Matroska language code.
        "LANGUAGE": properties.get("language_ietf"),  # Include IETF language tag.
        "title": properties.get("track_name"),  # Include track name as fallback.
        "name": properties.get("track_name"),  # Include name alias as fallback.
    }  # Complete metadata tag mapping.
    return {"tags": {key: str(value) for key, value in tags.items() if value is not None}}  # Return detector-compatible metadata.


def read_format_duration(media_data: dict[str, Any]) -> float:
    """
    Read usable media duration from ffprobe format metadata.

    :param media_data: ffprobe media metadata.
    :return: Duration in seconds, or zero.
    """

    raw_format = media_data.get("format")  # Read raw format object.
    if not isinstance(raw_format, dict):  # Verify format object shape.
        return 0.0  # Return unknown duration.
    raw_duration = raw_format.get("duration")  # Read duration field.
    try:  # Convert duration to float.
        return float(raw_duration) if raw_duration is not None else 0.0  # Return parsed duration.
    except (TypeError, ValueError):  # Handle invalid duration values.
        return 0.0  # Return unknown duration.


def read_audio_tracks(file_path: Path, input_dir: Path, detect_language: bool) -> list[AudioTrackRecord]:
    """
    Read audio-track records from one supported media file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param detect_language: Whether sampled fallback detection may run.
    :return: Audio-track records.
    """

    ffprobe_data = probe_media(file_path)  # Read duration metadata from ffprobe.
    mkvmerge_data = probe_mkvmerge(file_path)  # Read track order metadata from MKVToolNix.
    mkvmerge_audio_tracks = read_mkvmerge_audio_tracks(mkvmerge_data)  # Read audio tracks in mkvpropedit selector order.
    format_duration = read_format_duration(ffprobe_data)  # Read format duration.
    audio_tracks: list[AudioTrackRecord] = []  # Store audio records.

    for audio_position, track in enumerate(mkvmerge_audio_tracks):  # Iterate audio tracks in MKVToolNix order.
        current_name = read_mkvmerge_track_name(track)  # Read current track name.
        stream_index = read_mkvmerge_track_id(track)  # Read MKVToolNix track ID.
        track_uid = read_mkvmerge_track_uid(track)  # Read Matroska track UID.
        duration = format_duration  # Use format duration for distributed sample placement.
        metadata_stream = build_language_metadata_stream(track)  # Build language metadata from MKVToolNix properties.
        detected_language = detect_audio_track_language(file_path, metadata_stream, audio_position, duration) if detect_language else ""  # Detect language when requested.
        relative_path = file_path.relative_to(input_dir).as_posix()  # Build deterministic relative path.
        audio_tracks.append(AudioTrackRecord(file_path, relative_path, audio_position, stream_index, track_uid, current_name, detected_language))  # Store track record.

    return audio_tracks  # Return audio records.


def read_video_tracks(file_path: Path, input_dir: Path) -> list[VideoTrackRecord]:
    """
    Read video-track records from one supported media file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :return: Video-track records.
    """

    mkvmerge_data = probe_mkvmerge(file_path)  # Read track order metadata from MKVToolNix.
    mkvmerge_video_tracks = read_mkvmerge_video_tracks(mkvmerge_data)  # Read video tracks in mkvpropedit selector order.
    video_tracks: list[VideoTrackRecord] = []  # Store video records.

    for video_position, track in enumerate(mkvmerge_video_tracks):  # Iterate video tracks in MKVToolNix order.
        current_name = read_mkvmerge_track_name(track)  # Read current track name.
        stream_index = read_mkvmerge_track_id(track)  # Read MKVToolNix track ID.
        track_uid = read_mkvmerge_track_uid(track)  # Read Matroska track UID.
        relative_path = file_path.relative_to(input_dir).as_posix()  # Build deterministic relative path.
        video_tracks.append(VideoTrackRecord(file_path, relative_path, video_position, stream_index, track_uid, current_name))  # Store track record.

    return video_tracks  # Return video records.


def read_subtitle_tracks(file_path: Path, input_dir: Path, detect_language: bool) -> list[SubtitleTrackRecord]:
    """
    Read subtitle-track records from one supported media file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param detect_language: Whether text fallback detection may run.
    :return: Subtitle-track records.
    """

    ffprobe_data = probe_media(file_path)  # Read duration metadata from ffprobe.
    mkvmerge_data = probe_mkvmerge(file_path)  # Read track order metadata from MKVToolNix.
    mkvmerge_subtitle_tracks = read_mkvmerge_subtitle_tracks(mkvmerge_data)  # Read subtitle tracks in mkvpropedit selector order.
    format_duration = read_format_duration(ffprobe_data)  # Read format duration.
    subtitle_tracks: list[SubtitleTrackRecord] = []  # Store subtitle records.

    for subtitle_position, track in enumerate(mkvmerge_subtitle_tracks):  # Iterate subtitle tracks in MKVToolNix order.
        current_name = read_mkvmerge_track_name(track)  # Read current track name.
        stream_index = read_mkvmerge_track_id(track)  # Read MKVToolNix track ID.
        track_uid = read_mkvmerge_track_uid(track)  # Read Matroska track UID.
        codec_id = read_mkvmerge_codec_id(track)  # Read subtitle codec ID.
        codec_name = read_mkvmerge_codec_name(track)  # Read subtitle codec name.
        metadata_stream = build_language_metadata_stream(track)  # Build language metadata from MKVToolNix properties.
        detected_language = detect_subtitle_track_language(file_path, metadata_stream, stream_index, codec_id, codec_name, format_duration) if detect_language else ""  # Detect language when requested.
        relative_path = file_path.relative_to(input_dir).as_posix()  # Build deterministic relative path.
        subtitle_tracks.append(SubtitleTrackRecord(file_path, relative_path, subtitle_position, stream_index, track_uid, current_name, detected_language, codec_id, codec_name))  # Store track record.

    return subtitle_tracks  # Return subtitle records.


def collect_audio_tracks(input_dir: Path, selected_file: str | None = None) -> list[AudioTrackRecord]:
    """
    Collect every audio-track occurrence under the input directory.

    :param input_dir: Input directory path.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Audio-track occurrence records.
    """

    tracks: list[AudioTrackRecord] = []  # Store all discovered audio tracks.
    supported_files = discover_supported_files(input_dir, selected_file)  # Discover supported Matroska files once.
    with tqdm(supported_files, desc="Processing MKV", unit="file") as progress_bar:  # Build cleanup-managed progress bar.
        for file_path in progress_bar:  # Iterate supported Matroska files with progress.
            progress_bar.set_description(f"Processing: {file_path.name}")  # Show current MKV filename.
            try:  # Inspect one file without stopping the full report.
                tracks.extend(read_audio_tracks(file_path, input_dir, True))  # Add audio records with language detection.
            except Exception as error:  # Handle unexpected per-file failures.
                print(f"Skipping {file_path}: {error}")  # Report skipped corrupt or unreadable file.

    return tracks  # Return collected track records.


def collect_subtitle_tracks(input_dir: Path, selected_file: str | None = None) -> list[SubtitleTrackRecord]:
    """
    Collect every subtitle-track occurrence under the input directory.

    :param input_dir: Input directory path.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Subtitle-track occurrence records.
    """

    tracks: list[SubtitleTrackRecord] = []  # Store all discovered subtitle tracks.
    supported_files = discover_supported_files(input_dir, selected_file)  # Discover supported Matroska files once.
    with tqdm(supported_files, desc="Processing subtitle MKV", unit="file") as progress_bar:  # Build cleanup-managed progress bar.
        for file_path in progress_bar:  # Iterate supported Matroska files with progress.
            progress_bar.set_description(f"Processing subtitles: {file_path.name}")  # Show current MKV filename.
            try:  # Inspect one file without stopping the full report.
                tracks.extend(read_subtitle_tracks(file_path, input_dir, True))  # Add subtitle records with language detection.
            except Exception as error:  # Handle unexpected per-file failures.
                print(f"Skipping subtitle scan for {file_path}: {error}")  # Report skipped corrupt or unreadable file.

    return tracks  # Return collected track records.


def resolve_default_desired_name(tracks: list[Any], existing_value: str | None) -> str:
    """
    Resolve desired_new_name for one current-name group.

    :param tracks: Tracks in the group.
    :param existing_value: Existing desired value from a prior report.
    :return: Desired new name.
    """

    if existing_value is not None and existing_value != "":  # Preserve existing manual value when present.
        return existing_value  # Return manual desired name.

    detected_languages = [track.detected_language for track in tracks]  # Collect detected languages for every occurrence.
    unique_languages = sorted({language for language in detected_languages if language != ""})  # Collect non-empty detected languages.
    if len(detected_languages) > 0 and all(language != "" for language in detected_languages) and len(unique_languages) == 1:  # Verify every occurrence has the same confident language.
        return unique_languages[0]  # Return automatic desired name.
    return existing_value if existing_value is not None else ""  # Return existing empty value or fresh empty value.


def build_audio_report_data(tracks: list[AudioTrackRecord], existing_desired_names: dict[str, str]) -> dict[str, dict[str, str]]:
    """
    Build deterministic human-editable report data.

    :param tracks: Audio-track occurrence records.
    :param existing_desired_names: Preserved desired names keyed by display track name.
    :return: Report JSON data.
    """

    grouped_tracks: dict[str, list[AudioTrackRecord]] = {}  # Store tracks by current display name.
    for track in tracks:  # Iterate collected tracks.
        grouped_tracks.setdefault(display_track_name(track.current_name), []).append(track)  # Add track to current-name group.

    ordered_group_names = sorted(grouped_tracks, key=lambda name: (-len(grouped_tracks[name]), name.casefold()))  # Order groups by count then name.
    report_data: dict[str, dict[str, str]] = {}  # Store final report object.

    for display_name in ordered_group_names:  # Iterate ordered groups.
        group_tracks = sorted(grouped_tracks[display_name], key=lambda track: (track.relative_path.casefold(), track.audio_position))  # Order occurrences deterministically.
        group_key = f"{display_name} ({len(group_tracks)})"  # Build count-bearing group key.
        existing_value = existing_desired_names.get(display_name)  # Read preserved desired value.
        group_data: dict[str, str] = {"desired_new_name": resolve_default_desired_name(group_tracks, existing_value)}  # Initialize editable group data.
        for track in group_tracks:  # Iterate group occurrences.
            group_data[build_occurrence_key(track)] = track.detected_language  # Store occurrence detected language.
        report_data[group_key] = group_data  # Store completed group.

    return report_data  # Return deterministic report data.


def build_subtitle_report_data(tracks: list[SubtitleTrackRecord], existing_desired_names: dict[str, str]) -> dict[str, dict[str, str]]:
    """
    Build deterministic human-editable subtitle report data.

    :param tracks: Subtitle-track occurrence records.
    :param existing_desired_names: Preserved desired names keyed by display track name.
    :return: Subtitle report JSON data.
    """

    grouped_tracks: dict[str, list[SubtitleTrackRecord]] = {}  # Store tracks by current display name.
    for track in tracks:  # Iterate collected tracks.
        grouped_tracks.setdefault(display_subtitle_track_name(track.current_name), []).append(track)  # Add track to current-name group.

    ordered_group_names = sorted(grouped_tracks, key=lambda name: (-len(grouped_tracks[name]), name.casefold()))  # Order groups by count then name.
    report_data: dict[str, dict[str, str]] = {}  # Store final report object.

    for display_name in ordered_group_names:  # Iterate ordered groups.
        group_tracks = sorted(grouped_tracks[display_name], key=lambda track: (track.relative_path.casefold(), track.subtitle_position))  # Order occurrences deterministically.
        group_key = f"{display_name} ({len(group_tracks)})"  # Build count-bearing group key.
        existing_value = existing_desired_names.get(display_name)  # Read preserved desired value.
        group_data: dict[str, str] = {"desired_new_name": resolve_default_desired_name(group_tracks, existing_value)}  # Initialize editable group data.
        for track in group_tracks:  # Iterate group occurrences.
            group_data[build_subtitle_occurrence_key(track)] = track.detected_language  # Store occurrence detected language.
        report_data[group_key] = group_data  # Store completed group.

    return report_data  # Return deterministic report data.


def write_report(report_path: Path, report_data: dict[str, dict[str, str]]) -> None:
    """
    Write report JSON safely and atomically.

    :param report_path: Destination report path.
    :param report_data: Report JSON data.
    :return: None.
    """

    report_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists.
    serialized_report = json.dumps(report_data, ensure_ascii=False, indent=4) + "\n"  # Serialize readable UTF-8 JSON.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=report_path.parent, delete=False, newline="\n") as temp_file:  # Create temporary report file.
        temp_file.write(serialized_report)  # Write complete JSON payload.
        temp_name = temp_file.name  # Store temporary file path.
    os.replace(temp_name, report_path)  # Atomically replace final report.


def generate_audio_report(input_dir: str = INPUT_DIR, report_path: Path = AUDIO_REPORT_PATH, selected_file: str | None = None) -> dict[str, dict[str, str]]:
    """
    Generate audio_report.json from current audio-track metadata.

    :param input_dir: Input directory path string.
    :param report_path: Output report path.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Generated report data.
    """

    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory path.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        return {}  # Return empty report data without writing stale content.

    existing_desired_names = read_existing_desired_names(report_path)  # Preserve safe manual desired names.
    tracks = collect_audio_tracks(root_path, selected_file)  # Collect all audio tracks.
    report_data = build_audio_report_data(tracks, existing_desired_names)  # Build report JSON object.
    write_report(report_path, report_data)  # Write report safely.
    print(f"Report written: {report_path}")  # Report output path.
    return report_data  # Return generated data.


def generate_subtitle_report(input_dir: str = INPUT_DIR, report_path: Path = SUBTITLE_REPORT_PATH, selected_file: str | None = None) -> dict[str, dict[str, str]]:
    """
    Generate subtitles_report.json from current embedded subtitle-track metadata.

    :param input_dir: Input directory path string.
    :param report_path: Output subtitle report path.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Generated subtitle report data.
    """

    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory path.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        return {}  # Return empty report data without writing stale content.

    existing_desired_names = read_existing_desired_names(report_path)  # Preserve safe manual desired names.
    tracks = collect_subtitle_tracks(root_path, selected_file)  # Collect all embedded subtitle tracks.
    report_data = build_subtitle_report_data(tracks, existing_desired_names)  # Build subtitle report JSON object.
    write_report(report_path, report_data)  # Write subtitle report safely.
    print(f"Subtitle report written: {report_path}")  # Report output path.
    return report_data  # Return generated data.


def build_report_argument_parser() -> argparse.ArgumentParser:
    """
    Build the report-generation argument parser.

    :return: Argument parser.
    """

    parser = argparse.ArgumentParser(description="Generate audio and embedded subtitle track-name reports.")  # Create CLI parser.
    parser.add_argument("--video", action="store_true", help="Accept video selection; video has no report and creates no file.")  # Add video no-report flag.
    parser.add_argument("--audio", action="store_true", help="Generate the audio track-name report.")  # Add audio report flag.
    parser.add_argument("--subtitles", action="store_true", help="Generate the embedded subtitle track-name report.")  # Add subtitle report flag.
    parser.add_argument("--input-dir", default=INPUT_DIR, help="Input directory containing Matroska files.")  # Add input directory option.
    parser.add_argument("--audio-report", default=str(AUDIO_REPORT_PATH), help="Audio report output path.")  # Add audio report path option.
    parser.add_argument("--subtitle-report", default=str(SUBTITLE_REPORT_PATH), help="Subtitle report output path.")  # Add subtitle report path option.
    parser.add_argument("--file", default=None, help="Exact relative or absolute MKV file under input directory.")  # Add single-file option.
    return parser  # Return configured parser.


def run_report_cli(arguments: list[str] | None = None) -> int:
    """
    Run the report-generation CLI.

    :param arguments: Optional argument list.
    :return: Process exit status.
    """

    parser = build_report_argument_parser()  # Build CLI parser.
    parsed_args = parser.parse_args(arguments)  # Parse CLI arguments.
    if not parsed_args.video and not parsed_args.audio and not parsed_args.subtitles:  # Verify at least one track type was selected.
        parser.error("Select at least one of --video, --audio, or --subtitles.")  # Exit with argument error.

    input_path = Path(parsed_args.input_dir).resolve(strict=False)  # Resolve input directory argument.
    if not input_path.exists() or not input_path.is_dir():  # Verify input directory exists before reporting.
        print(f"Input directory not found: {input_path}")  # Report missing input directory.
        return 1  # Return failure status.

    if parsed_args.video:  # Verify video selection was provided.
        print("Video track names are deterministic and do not need a report.")  # Report no video report file.
    if parsed_args.audio:  # Verify audio report was requested.
        generate_audio_report(parsed_args.input_dir, Path(parsed_args.audio_report), parsed_args.file)  # Generate audio report.
    if parsed_args.subtitles:  # Verify subtitle report was requested.
        generate_subtitle_report(parsed_args.input_dir, Path(parsed_args.subtitle_report), parsed_args.file)  # Generate subtitle report.

    return 0  # Return success status.


def main() -> None:
    """
    Generate selected track-name reports.

    :return: None.
    """

    sys.exit(run_report_cli())  # Run CLI and return process status.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate report from default configuration.
