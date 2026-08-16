"""
Rename Matroska video, audio, and embedded subtitle track name metadata safely.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import argparse  # Parse command-line arguments.
from dataclasses import dataclass, field  # Define typed workflow records.
from pathlib import Path  # Represent filesystem paths.
from typing import Any  # Type dynamic JSON data.
import json  # Read report JSON.
import sys  # Return meaningful CLI exit statuses.

from mkvpropedit_wrapper import MkvpropeditResult, TrackNameEdit, apply_track_name_edits, build_track_selector, valid_target_name  # Apply mkvpropedit edits.
from report import AUDIO_REPORT_PATH, INPUT_DIR, SUBTITLE_REPORT_PATH, SUPPORTED_EXTENSIONS, discover_supported_files, generate_audio_report, generate_subtitle_report, parse_group_key, parse_occurrence_key, parse_subtitle_occurrence_key, raw_subtitle_track_name, raw_track_name, read_audio_tracks, read_subtitle_tracks, read_video_tracks, resolve_selected_file  # Reuse report parsing and metadata inspection.


@dataclass
class RenameSummary:
    """
    Stores overall rename workflow counts.
    """

    planned: int = 0  # Store planned rename count.
    changed: int = 0  # Store successful changed track count.
    warnings: int = 0  # Store warning count from completed mkvpropedit edits.
    skipped: int = 0  # Store skipped track count.
    failed: int = 0  # Store failed file or track count.
    messages: list[str] = field(default_factory=list)  # Store workflow messages.


@dataclass(frozen=True)
class TrackSelection:
    """
    Stores selected track-type workflow flags.
    """

    video: bool  # Store whether video track names are selected.
    audio: bool  # Store whether audio track names are selected.
    subtitles: bool  # Store whether embedded subtitle track names are selected.


@dataclass(frozen=True)
class PlannedRename:
    """
    Stores one validated report-driven rename request.
    """

    file_path: Path  # Store absolute file path.
    relative_path: str  # Store report relative path.
    audio_position: int  # Store zero-based audio position.
    track_id: int | None  # Store MKVToolNix track ID from report.
    track_uid: int | None  # Store Matroska track UID from report.
    current_name: str  # Store current track name from report group.
    target_name: str  # Store desired target name.


@dataclass(frozen=True)
class PlannedSubtitleRename:
    """
    Stores one validated subtitle report-driven rename request.
    """

    file_path: Path  # Store absolute file path.
    relative_path: str  # Store report relative path.
    subtitle_position: int  # Store zero-based subtitle position.
    track_id: int | None  # Store MKVToolNix track ID from report.
    track_uid: int | None  # Store Matroska track UID from report.
    current_name: str  # Store current track name from report group.
    target_name: str  # Store desired target name.


def load_report_data(report_path: Path) -> dict[str, Any] | None:
    """
    Load report JSON data safely.

    :param report_path: Report JSON path.
    :return: Report data object or None.
    """

    if not report_path.exists():  # Verify report file exists.
        print(f"Report not found: {report_path}")  # Report missing report.
        return None  # Return no report data.

    try:  # Read and parse report JSON.
        report_data = json.loads(report_path.read_text(encoding="utf-8"))  # Load report JSON.
    except (OSError, json.JSONDecodeError) as error:  # Handle unreadable or malformed report.
        print(f"Report could not be read: {error}")  # Report load failure.
        return None  # Return no report data.

    if not isinstance(report_data, dict):  # Verify top-level report shape.
        print("Report top-level JSON value must be an object.")  # Report malformed shape.
        return None  # Return no report data.

    return report_data  # Return parsed report data.


def load_optional_report_data(report_path: Path) -> dict[str, Any]:
    """
    Load optional report JSON data safely.

    :param report_path: Report JSON path.
    :return: Report data object or empty object.
    """

    if not report_path.exists():  # Verify optional report file exists.
        print(f"Optional report not found, skipping: {report_path}")  # Report missing optional report.
        return {}  # Return empty report data.

    report_data = load_report_data(report_path)  # Load report through strict parser.
    return report_data if report_data is not None else {}  # Return parsed report or empty object.


def resolve_target_name(desired_value: object, detected_value: object) -> str:
    """
    Resolve target name from desired report value or detected occurrence language.

    :param desired_value: Group desired_new_name value.
    :param detected_value: Occurrence detected language value.
    :return: Target name or empty text.
    """

    desired_name = valid_target_name(desired_value) if isinstance(desired_value, str) else ""  # Normalize desired value.
    if desired_name != "":  # Verify desired name is configured.
        return desired_name  # Return manual desired name.
    return valid_target_name(detected_value) if isinstance(detected_value, str) else ""  # Return detected language fallback.


def collect_planned_renames(report_data: dict[str, Any], input_dir: Path, summary: RenameSummary) -> list[PlannedRename]:
    """
    Collect report-driven rename requests before filesystem validation.

    :param report_data: Parsed report JSON data.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: Planned rename requests.
    """

    planned_renames: list[PlannedRename] = []  # Store rename requests.

    for group_key, group_value in report_data.items():  # Iterate current-name groups.
        if not isinstance(group_key, str) or not isinstance(group_value, dict):  # Verify group shape.
            summary.skipped += 1  # Count malformed group skip.
            summary.messages.append(f"Skipped malformed group: {group_key}")  # Store skip reason.
            continue  # Skip malformed group.

        display_name, parsed_count = parse_group_key(group_key)  # Parse current-name group key.
        current_name = raw_track_name(display_name)  # Convert display marker to raw track name.
        desired_value = group_value.get("desired_new_name")  # Read group desired name.
        occurrence_keys = [key for key in group_value if key != "desired_new_name"]  # Collect occurrence entries.
        if parsed_count is not None and parsed_count != len(occurrence_keys):  # Verify group count is still self-consistent.
            summary.messages.append(f"Group count mismatch in report: {group_key}")  # Store mismatch warning.

        for occurrence_key in occurrence_keys:  # Iterate occurrence entries.
            detected_value = group_value.get(occurrence_key)  # Read occurrence detected language.
            target_name = resolve_target_name(desired_value, detected_value)  # Resolve target name.
            parsed_occurrence = parse_occurrence_key(str(occurrence_key))  # Parse occurrence key.
            if parsed_occurrence is None:  # Verify occurrence key has targetable metadata.
                summary.skipped += 1  # Count skipped occurrence.
                summary.messages.append(f"Skipped malformed occurrence key: {occurrence_key}")  # Store skip reason.
                continue  # Skip malformed occurrence.
            if target_name == "":  # Verify a target name exists.
                summary.skipped += 1  # Count skipped occurrence.
                summary.messages.append(f"Skipped unknown target for: {occurrence_key}")  # Store skip reason.
                continue  # Skip unresolved target.

            relative_path, audio_position, track_id, track_uid = parsed_occurrence  # Unpack occurrence target.
            file_path = input_dir / Path(relative_path)  # Build absolute file path.
            planned_renames.append(PlannedRename(file_path, relative_path, audio_position, track_id, track_uid, current_name, target_name))  # Store planned rename.

    return planned_renames  # Return planned renames.


def collect_planned_subtitle_renames(report_data: dict[str, Any], input_dir: Path, summary: RenameSummary) -> list[PlannedSubtitleRename]:
    """
    Collect subtitle report-driven rename requests before filesystem validation.

    :param report_data: Parsed subtitle report JSON data.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: Planned subtitle rename requests.
    """

    planned_renames: list[PlannedSubtitleRename] = []  # Store subtitle rename requests.

    for group_key, group_value in report_data.items():  # Iterate current-name groups.
        if not isinstance(group_key, str) or not isinstance(group_value, dict):  # Verify group shape.
            summary.skipped += 1  # Count malformed group skip.
            summary.messages.append(f"Skipped malformed subtitle group: {group_key}")  # Store skip reason.
            continue  # Skip malformed group.

        display_name, parsed_count = parse_group_key(group_key)  # Parse current-name group key.
        current_name = raw_subtitle_track_name(display_name)  # Convert display marker to raw track name.
        desired_value = group_value.get("desired_new_name")  # Read group desired name.
        occurrence_keys = [key for key in group_value if key != "desired_new_name"]  # Collect occurrence entries.
        if parsed_count is not None and parsed_count != len(occurrence_keys):  # Verify group count is still self-consistent.
            summary.messages.append(f"Subtitle group count mismatch in report: {group_key}")  # Store mismatch warning.

        for occurrence_key in occurrence_keys:  # Iterate occurrence entries.
            detected_value = group_value.get(occurrence_key)  # Read occurrence detected language.
            target_name = resolve_target_name(desired_value, detected_value)  # Resolve target name.
            parsed_occurrence = parse_subtitle_occurrence_key(str(occurrence_key))  # Parse occurrence key.
            if parsed_occurrence is None:  # Verify occurrence key has targetable metadata.
                summary.skipped += 1  # Count skipped occurrence.
                summary.messages.append(f"Skipped malformed subtitle occurrence key: {occurrence_key}")  # Store skip reason.
                continue  # Skip malformed occurrence.
            if target_name == "":  # Verify a target name exists.
                summary.skipped += 1  # Count skipped occurrence.
                summary.messages.append(f"Skipped unknown subtitle target for: {occurrence_key}")  # Store skip reason.
                continue  # Skip unresolved target.

            relative_path, subtitle_position, track_id, track_uid = parsed_occurrence  # Unpack occurrence target.
            file_path = input_dir / Path(relative_path)  # Build absolute file path.
            planned_renames.append(PlannedSubtitleRename(file_path, relative_path, subtitle_position, track_id, track_uid, current_name, target_name))  # Store planned rename.

    return planned_renames  # Return planned subtitle renames.


def group_plans_by_file(plans: list[PlannedRename]) -> dict[Path, list[PlannedRename]]:
    """
    Group planned renames by media file.

    :param plans: Planned rename requests.
    :return: Plans keyed by file path.
    """

    grouped_plans: dict[Path, list[PlannedRename]] = {}  # Store plans by file path.
    for plan in plans:  # Iterate plans.
        grouped_plans.setdefault(plan.file_path, []).append(plan)  # Add plan to file group.
    return grouped_plans  # Return grouped plans.


def group_subtitle_plans_by_file(plans: list[PlannedSubtitleRename]) -> dict[Path, list[PlannedSubtitleRename]]:
    """
    Group planned subtitle renames by media file.

    :param plans: Planned subtitle rename requests.
    :return: Plans keyed by file path.
    """

    grouped_plans: dict[Path, list[PlannedSubtitleRename]] = {}  # Store plans by file path.
    for plan in plans:  # Iterate plans.
        grouped_plans.setdefault(plan.file_path, []).append(plan)  # Add plan to file group.
    return grouped_plans  # Return grouped plans.


def validate_video_plan_for_file(file_path: Path, input_dir: Path, summary: RenameSummary) -> TrackNameEdit | None:
    """
    Validate deterministic video-track naming against current file metadata.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: mkvpropedit video name operation or None.
    """

    if not file_path.exists():  # Verify media file still exists.
        summary.messages.append(f"Missing file for video name: {file_path}")  # Store failure reason.
        return None  # Return no operation.
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify file remains Matroska video.
        summary.messages.append(f"Unsupported container skipped for video name: {file_path}")  # Store skip reason.
        return None  # Return no operation.

    try:  # Read current video metadata.
        current_tracks = read_video_tracks(file_path, input_dir)  # Inspect current video metadata.
    except Exception as error:  # Handle corrupt or unreadable file.
        summary.failed += 1  # Count inspection failure.
        summary.messages.append(f"Video metadata read failed for {file_path}: {error}")  # Store failure reason.
        return None  # Return no operation.

    if len(current_tracks) == 0:  # Verify a targetable video track exists.
        summary.skipped += 1  # Count no-video skip.
        summary.messages.append(f"No video track found: {file_path}")  # Store skip reason.
        return None  # Return no operation.
    if len(current_tracks) > 1:  # Verify ordinary single-video layout.
        summary.skipped += 1  # Count ambiguous-video skip.
        summary.messages.append(f"Multiple video tracks skipped: {file_path}")  # Store skip reason.
        return None  # Return no operation.

    current_track = current_tracks[0]  # Read the single video track.
    target_name = valid_target_name(file_path.stem)  # Resolve filename stem target.
    if target_name == "":  # Verify filename stem can become a track name.
        summary.skipped += 1  # Count empty-target skip.
        summary.messages.append(f"Empty video target skipped: {file_path}")  # Store skip reason.
        return None  # Return no operation.
    if current_track.current_name == target_name:  # Verify target already applied.
        summary.skipped += 1  # Count no-op skip.
        summary.messages.append(f"Already named {target_name}: {current_track.relative_path} video 1")  # Store skip reason.
        return None  # Return no operation.

    track_selector = build_track_selector("v", current_track.video_position, current_track.track_uid)  # Prefer Matroska Track UID selector when available.
    summary.planned += 1  # Count validated video edit.
    return TrackNameEdit(track_selector, current_track.current_name, target_name)  # Return validated operation.


def validate_audio_plans_for_file(file_path: Path, plans: list[PlannedRename], input_dir: Path, summary: RenameSummary) -> list[TrackNameEdit]:
    """
    Validate planned audio renames against current file metadata.

    :param file_path: Media file path.
    :param plans: Planned renames for the file.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: mkvpropedit rename operations.
    """

    if not file_path.exists():  # Verify media file still exists.
        summary.failed += len(plans)  # Count missing-file failures.
        summary.messages.append(f"Missing file: {file_path}")  # Store failure reason.
        return []  # Return no operations.
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify file remains Matroska video.
        summary.skipped += len(plans)  # Count unsupported skips.
        summary.messages.append(f"Unsupported container skipped: {file_path}")  # Store skip reason.
        return []  # Return no operations.

    try:  # Read current metadata without sampled detection.
        current_tracks = read_audio_tracks(file_path, input_dir, False)  # Inspect current audio metadata.
    except Exception as error:  # Handle corrupt or unreadable file.
        summary.failed += len(plans)  # Count inspection failures.
        summary.messages.append(f"Metadata read failed for {file_path}: {error}")  # Store failure reason.
        return []  # Return no operations.

    operations: list[TrackNameEdit] = []  # Store validated mkvpropedit operations.
    for plan in sorted(plans, key=lambda item: item.audio_position):  # Iterate plans by audio position.
        if plan.audio_position >= len(current_tracks):  # Verify track ordinal still exists.
            summary.failed += 1  # Count missing-track failure.
            summary.messages.append(f"Audio track missing in {plan.relative_path}: audio {plan.audio_position + 1}")  # Store failure reason.
            continue  # Skip missing track.

        current_track = current_tracks[plan.audio_position]  # Read current track by audio ordinal.
        if plan.track_uid is not None and current_track.track_uid != plan.track_uid:  # Verify Matroska track UID still matches the report.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Track UID mismatch in {plan.relative_path} audio {plan.audio_position + 1}: report={plan.track_uid!r}, file={current_track.track_uid!r}")  # Store failure reason.
            continue  # Skip stale occurrence.
        if plan.track_id is not None and current_track.stream_index != plan.track_id:  # Verify MKVToolNix track ID still matches the report.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Track ID mismatch in {plan.relative_path} audio {plan.audio_position + 1}: report={plan.track_id!r}, file={current_track.stream_index!r}")  # Store failure reason.
            continue  # Skip stale occurrence.
        if current_track.current_name == plan.target_name:  # Verify target already applied.
            summary.skipped += 1  # Count no-op skip.
            summary.messages.append(f"Already named {plan.target_name}: {plan.relative_path} audio {plan.audio_position + 1}")  # Store skip reason.
            continue  # Skip no-op edit.
        if current_track.current_name != plan.current_name:  # Verify report is not stale for this exact track.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Current name mismatch in {plan.relative_path} audio {plan.audio_position + 1}: report={plan.current_name!r}, file={current_track.current_name!r}")  # Store failure reason.
            continue  # Skip stale occurrence.

        track_selector = build_track_selector("a", plan.audio_position, current_track.track_uid)  # Prefer Matroska Track UID selector when available.
        operations.append(TrackNameEdit(track_selector, current_track.current_name, plan.target_name))  # Store validated operation.
        summary.planned += 1  # Count validated edit.

    return operations  # Return validated operations.


def validate_subtitle_plans_for_file(file_path: Path, plans: list[PlannedSubtitleRename], input_dir: Path, summary: RenameSummary) -> list[TrackNameEdit]:
    """
    Validate planned subtitle renames against current file metadata.

    :param file_path: Media file path.
    :param plans: Planned subtitle renames for the file.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: mkvpropedit rename operations.
    """

    if not file_path.exists():  # Verify media file still exists.
        summary.failed += len(plans)  # Count missing-file failures.
        summary.messages.append(f"Missing subtitle file: {file_path}")  # Store failure reason.
        return []  # Return no operations.
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify file remains Matroska video.
        summary.skipped += len(plans)  # Count unsupported skips.
        summary.messages.append(f"Unsupported subtitle container skipped: {file_path}")  # Store skip reason.
        return []  # Return no operations.

    try:  # Read current metadata without text fallback detection.
        current_tracks = read_subtitle_tracks(file_path, input_dir, False)  # Inspect current subtitle metadata.
    except Exception as error:  # Handle corrupt or unreadable file.
        summary.failed += len(plans)  # Count inspection failures.
        summary.messages.append(f"Subtitle metadata read failed for {file_path}: {error}")  # Store failure reason.
        return []  # Return no operations.

    operations: list[TrackNameEdit] = []  # Store validated mkvpropedit operations.
    for plan in sorted(plans, key=lambda item: item.subtitle_position):  # Iterate plans by subtitle position.
        if plan.subtitle_position >= len(current_tracks):  # Verify track ordinal still exists.
            summary.failed += 1  # Count missing-track failure.
            summary.messages.append(f"Subtitle track missing in {plan.relative_path}: subtitle {plan.subtitle_position + 1}")  # Store failure reason.
            continue  # Skip missing track.

        current_track = current_tracks[plan.subtitle_position]  # Read current track by subtitle ordinal.
        if plan.track_uid is not None and current_track.track_uid != plan.track_uid:  # Verify Matroska track UID still matches the report.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Subtitle Track UID mismatch in {plan.relative_path} subtitle {plan.subtitle_position + 1}: report={plan.track_uid!r}, file={current_track.track_uid!r}")  # Store failure reason.
            continue  # Skip stale occurrence.
        if plan.track_id is not None and current_track.stream_index != plan.track_id:  # Verify MKVToolNix track ID still matches the report.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Subtitle Track ID mismatch in {plan.relative_path} subtitle {plan.subtitle_position + 1}: report={plan.track_id!r}, file={current_track.stream_index!r}")  # Store failure reason.
            continue  # Skip stale occurrence.
        if current_track.current_name == plan.target_name:  # Verify target already applied.
            summary.skipped += 1  # Count no-op skip.
            summary.messages.append(f"Already named {plan.target_name}: {plan.relative_path} subtitle {plan.subtitle_position + 1}")  # Store skip reason.
            continue  # Skip no-op edit.
        if current_track.current_name != plan.current_name:  # Verify report is not stale for this exact track.
            summary.failed += 1  # Count stale-report failure.
            summary.messages.append(f"Subtitle current name mismatch in {plan.relative_path} subtitle {plan.subtitle_position + 1}: report={plan.current_name!r}, file={current_track.current_name!r}")  # Store failure reason.
            continue  # Skip stale occurrence.

        track_selector = build_track_selector("s", plan.subtitle_position, current_track.track_uid)  # Prefer Matroska Track UID selector when available.
        operations.append(TrackNameEdit(track_selector, current_track.current_name, plan.target_name))  # Store validated operation.
        summary.planned += 1  # Count validated edit.

    return operations  # Return validated operations.


def collect_candidate_files(grouped_plans: dict[Path, list[PlannedRename]], grouped_subtitle_plans: dict[Path, list[PlannedSubtitleRename]], input_dir: Path, include_video: bool, selected_file: str | None = None) -> list[Path]:
    """
    Collect files eligible for video, audio, or subtitle name edits.

    :param grouped_plans: Planned audio renames keyed by file path.
    :param grouped_subtitle_plans: Planned subtitle renames keyed by file path.
    :param input_dir: Input directory path.
    :param include_video: Whether deterministic video names should be planned.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Candidate file paths.
    """

    candidate_paths = set(discover_supported_files(input_dir, selected_file)) if include_video else set()  # Collect current Matroska files for deterministic video naming.
    candidate_paths.update(grouped_plans)  # Include report files that may need audio validation.
    candidate_paths.update(grouped_subtitle_plans)  # Include subtitle report files that may need validation.
    if selected_file is not None:  # Verify whether exact single-file mode is active.
        selected_path = resolve_selected_file(input_dir, selected_file)  # Resolve selected media file.
        candidate_paths = {path for path in candidate_paths if selected_path is not None and path.resolve(strict=False) == selected_path.resolve(strict=False)}  # Keep only selected file.
    return sorted(candidate_paths, key=lambda path: path.as_posix().lower())  # Return deterministic file order.


def apply_grouped_renames(grouped_plans: dict[Path, list[PlannedRename]], grouped_subtitle_plans: dict[Path, list[PlannedSubtitleRename]], input_dir: Path, summary: RenameSummary, include_video: bool = True, selected_file: str | None = None) -> list[MkvpropeditResult]:
    """
    Apply validated renames one mkvpropedit invocation per file.

    :param grouped_plans: Planned renames keyed by file path.
    :param grouped_subtitle_plans: Planned subtitle renames keyed by file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :param include_video: Whether deterministic video names should be applied.
    :param selected_file: Optional exact selected file under the input directory.
    :return: mkvpropedit results.
    """

    results: list[MkvpropeditResult] = []  # Store mkvpropedit results.
    candidate_files = collect_candidate_files(grouped_plans, grouped_subtitle_plans, input_dir, include_video, selected_file)  # Collect selected video, audio, and subtitle candidate files.
    current_supported_files = {path for path in candidate_files if path.exists() and path.suffix.lower() in SUPPORTED_EXTENSIONS}  # Collect current files for video naming eligibility.
    for file_path in candidate_files:  # Iterate files deterministically.
        operations: list[TrackNameEdit] = []  # Store combined file operations.
        video_operation = validate_video_plan_for_file(file_path, input_dir, summary) if include_video and file_path in current_supported_files else None  # Validate deterministic video operation.
        if video_operation is not None:  # Verify video operation exists.
            operations.append(video_operation)  # Add video operation first.
        if file_path in grouped_plans:  # Verify report has audio plans for this file.
            operations.extend(validate_audio_plans_for_file(file_path, grouped_plans[file_path], input_dir, summary))  # Add validated audio operations.
        if file_path in grouped_subtitle_plans:  # Verify subtitle report has plans for this file.
            operations.extend(validate_subtitle_plans_for_file(file_path, grouped_subtitle_plans[file_path], input_dir, summary))  # Add validated subtitle operations.
        if not operations:  # Verify file has operations after validation.
            continue  # Skip files without edits.

        result = apply_track_name_edits(file_path, operations)  # Apply mkvpropedit edits.
        results.append(result)  # Store command result.
        if result.success and result.warning:  # Verify mkvpropedit completed with warnings.
            summary.changed += result.changed_count  # Count changes because MKVToolNix continued after warnings.
            summary.warnings += 1  # Count warning-bearing file.
            warning_text = (result.stderr or result.stdout).strip()  # Resolve warning output text.
            summary.messages.append(f"mkvpropedit warning for {file_path}: {warning_text}")  # Store warning reason.
            print(f"Renamed {result.changed_count} track name(s) with warning: {file_path}")  # Report warning completion.
        elif result.success:  # Verify mkvpropedit succeeded cleanly.
            summary.changed += result.changed_count  # Count successful changes.
            print(f"Renamed {result.changed_count} track name(s): {file_path}")  # Report file success.
        else:  # Handle mkvpropedit failure.
            summary.failed += result.changed_count  # Count failed changes.
            summary.messages.append(f"mkvpropedit failed for {file_path}: {result.stderr.strip()}")  # Store failure reason.
            print(f"mkvpropedit failed for {file_path}: {result.stderr.strip()}")  # Report file failure.

    return results  # Return command results.


def collect_detected_plans_for_file(file_path: Path, input_dir: Path, summary: RenameSummary) -> tuple[list[PlannedRename], list[PlannedSubtitleRename]]:
    """
    Collect automatic detected-language rename plans for one file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: Audio and subtitle rename plans.
    """

    audio_plans: list[PlannedRename] = []  # Store automatic audio plans.
    subtitle_plans: list[PlannedSubtitleRename] = []  # Store automatic subtitle plans.

    try:  # Read detected audio metadata.
        audio_tracks = read_audio_tracks(file_path, input_dir, True)  # Inspect audio tracks with language detection.
    except Exception as error:  # Handle corrupt or unreadable audio metadata.
        summary.failed += 1  # Count audio inspection failure.
        summary.messages.append(f"Automatic audio detection failed for {file_path}: {error}")  # Store failure reason.
        audio_tracks = []  # Continue with subtitle detection.

    for track in audio_tracks:  # Iterate detected audio tracks.
        target_name = valid_target_name(track.detected_language)  # Resolve detected audio target.
        if target_name == "":  # Verify confident audio language exists.
            summary.skipped += 1  # Count unknown-language skip.
            summary.messages.append(f"Skipped unknown automatic audio target for: {track.relative_path} audio {track.audio_position + 1}")  # Store skip reason.
            continue  # Skip unresolved target.
        audio_plans.append(PlannedRename(track.file_path, track.relative_path, track.audio_position, track.stream_index, track.track_uid, track.current_name, target_name))  # Store detected audio plan.

    try:  # Read detected subtitle metadata.
        subtitle_tracks = read_subtitle_tracks(file_path, input_dir, True)  # Inspect embedded subtitle tracks with language detection.
    except Exception as error:  # Handle corrupt or unreadable subtitle metadata.
        summary.failed += 1  # Count subtitle inspection failure.
        summary.messages.append(f"Automatic subtitle detection failed for {file_path}: {error}")  # Store failure reason.
        subtitle_tracks = []  # Continue with other files.

    for track in subtitle_tracks:  # Iterate detected subtitle tracks.
        target_name = valid_target_name(track.detected_language)  # Resolve detected subtitle target.
        if target_name == "":  # Verify confident subtitle language exists.
            summary.skipped += 1  # Count unknown-language skip.
            summary.messages.append(f"Skipped unknown automatic subtitle target for: {track.relative_path} subtitle {track.subtitle_position + 1}")  # Store skip reason.
            continue  # Skip unresolved target.
        subtitle_plans.append(PlannedSubtitleRename(track.file_path, track.relative_path, track.subtitle_position, track.stream_index, track.track_uid, track.current_name, target_name))  # Store detected subtitle plan.

    return audio_plans, subtitle_plans  # Return detected plans.


def collect_detected_plans(input_dir: Path, summary: RenameSummary, include_audio: bool = True, include_subtitles: bool = True, selected_file: str | None = None) -> tuple[dict[Path, list[PlannedRename]], dict[Path, list[PlannedSubtitleRename]]]:
    """
    Collect automatic detected-language rename plans under the input directory.

    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :param include_audio: Whether audio tracks should be detected.
    :param include_subtitles: Whether embedded subtitle tracks should be detected.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Audio and subtitle plans keyed by file path.
    """

    audio_plans: list[PlannedRename] = []  # Store all automatic audio plans.
    subtitle_plans: list[PlannedSubtitleRename] = []  # Store all automatic subtitle plans.

    for file_path in discover_supported_files(input_dir, selected_file):  # Iterate supported Matroska files.
        file_audio_plans, file_subtitle_plans = collect_detected_plans_for_file(file_path, input_dir, summary) if include_audio and include_subtitles else ([], [])  # Collect detected plans for one file when both language tracks are selected.
        if include_audio and not include_subtitles:  # Verify only audio language tracks are selected.
            file_audio_plans, file_subtitle_plans = collect_detected_audio_plans_for_file(file_path, input_dir, summary), []  # Collect only detected audio plans.
        if include_subtitles and not include_audio:  # Verify only subtitle language tracks are selected.
            file_audio_plans, file_subtitle_plans = [], collect_detected_subtitle_plans_for_file(file_path, input_dir, summary)  # Collect only detected subtitle plans.
        audio_plans.extend(file_audio_plans)  # Add file audio plans.
        subtitle_plans.extend(file_subtitle_plans)  # Add file subtitle plans.

    return group_plans_by_file(audio_plans), group_subtitle_plans_by_file(subtitle_plans)  # Return grouped detected plans.


def collect_detected_audio_plans_for_file(file_path: Path, input_dir: Path, summary: RenameSummary) -> list[PlannedRename]:
    """
    Collect automatic detected-language audio rename plans for one file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: Audio rename plans.
    """

    audio_plans: list[PlannedRename] = []  # Store automatic audio plans.
    try:  # Read detected audio metadata.
        audio_tracks = read_audio_tracks(file_path, input_dir, True)  # Inspect audio tracks with language detection.
    except Exception as error:  # Handle corrupt or unreadable audio metadata.
        summary.failed += 1  # Count audio inspection failure.
        summary.messages.append(f"Automatic audio detection failed for {file_path}: {error}")  # Store failure reason.
        return audio_plans  # Return no audio plans.

    for track in audio_tracks:  # Iterate detected audio tracks.
        target_name = valid_target_name(track.detected_language)  # Resolve detected audio target.
        if target_name == "":  # Verify confident audio language exists.
            summary.skipped += 1  # Count unknown-language skip.
            summary.messages.append(f"Skipped unknown automatic audio target for: {track.relative_path} audio {track.audio_position + 1}")  # Store skip reason.
            continue  # Skip unresolved target.
        audio_plans.append(PlannedRename(track.file_path, track.relative_path, track.audio_position, track.stream_index, track.track_uid, track.current_name, target_name))  # Store detected audio plan.

    return audio_plans  # Return audio plans.


def collect_detected_subtitle_plans_for_file(file_path: Path, input_dir: Path, summary: RenameSummary) -> list[PlannedSubtitleRename]:
    """
    Collect automatic detected-language subtitle rename plans for one file.

    :param file_path: Media file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: Subtitle rename plans.
    """

    subtitle_plans: list[PlannedSubtitleRename] = []  # Store automatic subtitle plans.
    try:  # Read detected subtitle metadata.
        subtitle_tracks = read_subtitle_tracks(file_path, input_dir, True)  # Inspect embedded subtitle tracks with language detection.
    except Exception as error:  # Handle corrupt or unreadable subtitle metadata.
        summary.failed += 1  # Count subtitle inspection failure.
        summary.messages.append(f"Automatic subtitle detection failed for {file_path}: {error}")  # Store failure reason.
        return subtitle_plans  # Return no subtitle plans.

    for track in subtitle_tracks:  # Iterate detected subtitle tracks.
        target_name = valid_target_name(track.detected_language)  # Resolve detected subtitle target.
        if target_name == "":  # Verify confident subtitle language exists.
            summary.skipped += 1  # Count unknown-language skip.
            summary.messages.append(f"Skipped unknown automatic subtitle target for: {track.relative_path} subtitle {track.subtitle_position + 1}")  # Store skip reason.
            continue  # Skip unresolved target.
        subtitle_plans.append(PlannedSubtitleRename(track.file_path, track.relative_path, track.subtitle_position, track.stream_index, track.track_uid, track.current_name, target_name))  # Store detected subtitle plan.

    return subtitle_plans  # Return subtitle plans.


def rename_detected_track_metadata(input_dir: str = INPUT_DIR, include_video: bool = True, include_audio: bool = True, include_subtitles: bool = True, selected_file: str | None = None) -> RenameSummary:
    """
    Automatically detect languages and rename video, audio, and subtitle track names.

    :param input_dir: Input directory path string.
    :param include_video: Whether video track names should be processed.
    :param include_audio: Whether audio track names should be processed.
    :param include_subtitles: Whether embedded subtitle track names should be processed.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Rename workflow summary.
    """

    summary = RenameSummary()  # Initialize workflow summary.
    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        summary.failed += 1  # Count missing input as failure.
        return summary  # Return summary.

    grouped_plans, grouped_subtitle_plans = collect_detected_plans(root_path, summary, include_audio, include_subtitles, selected_file)  # Collect automatic detected plans.
    apply_grouped_renames(grouped_plans, grouped_subtitle_plans, root_path, summary, include_video, selected_file)  # Apply validated rename operations.

    print(f"Summary: planned={summary.planned}, changed={summary.changed}, warnings={summary.warnings}, skipped={summary.skipped}, failed={summary.failed}")  # Report summary counts.
    for message in summary.messages:  # Iterate accumulated messages.
        print(message)  # Report detailed message.

    return summary  # Return workflow summary.


def rename_track_metadata(input_dir: str = INPUT_DIR, report_path: Path = AUDIO_REPORT_PATH, subtitle_report_path: Path = SUBTITLE_REPORT_PATH, include_video: bool = True, include_audio: bool = True, include_subtitles: bool = True, selected_file: str | None = None) -> RenameSummary:
    """
    Rename deterministic video names plus report-driven audio and subtitle names.

    :param input_dir: Input directory path string.
    :param report_path: Audio report JSON path.
    :param subtitle_report_path: Subtitle report JSON path.
    :param include_video: Whether video track names should be processed.
    :param include_audio: Whether audio track names should be processed.
    :param include_subtitles: Whether embedded subtitle track names should be processed.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Rename workflow summary.
    """

    summary = RenameSummary()  # Initialize workflow summary.
    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        summary.failed += 1  # Count missing input as failure.
        return summary  # Return summary.

    report_data = load_report_data(report_path) if include_audio else {}  # Load audio report only when selected.
    if report_data is None:  # Verify required audio report loaded.
        summary.failed += 1  # Count missing or malformed report.
        return summary  # Return summary.

    planned_renames = collect_planned_renames(report_data, root_path, summary) if include_audio else []  # Collect selected audio rename requests.
    grouped_plans = group_plans_by_file(planned_renames)  # Group plans by media file.
    subtitle_report_data = load_report_data(subtitle_report_path) if include_subtitles else {}  # Load subtitle report only when selected.
    if subtitle_report_data is None:  # Verify required subtitle report loaded.
        summary.failed += 1  # Count missing or malformed report.
        return summary  # Return summary.
    planned_subtitle_renames = collect_planned_subtitle_renames(subtitle_report_data, root_path, summary) if include_subtitles else []  # Collect selected subtitle rename requests.
    grouped_subtitle_plans = group_subtitle_plans_by_file(planned_subtitle_renames)  # Group subtitle plans by media file.
    apply_grouped_renames(grouped_plans, grouped_subtitle_plans, root_path, summary, include_video, selected_file)  # Apply validated rename operations.

    print(f"Summary: planned={summary.planned}, changed={summary.changed}, warnings={summary.warnings}, skipped={summary.skipped}, failed={summary.failed}")  # Report summary counts.
    for message in summary.messages:  # Iterate accumulated messages.
        print(message)  # Report detailed message.

    return summary  # Return workflow summary.


def process_track_metadata(input_dir: str = INPUT_DIR, report_path: Path = AUDIO_REPORT_PATH, subtitle_report_path: Path = SUBTITLE_REPORT_PATH, include_video: bool = True, include_audio: bool = True, include_subtitles: bool = True, selected_file: str | None = None) -> RenameSummary:
    """
    Generate selected reports and apply selected track-name metadata changes.

    :param input_dir: Input directory path string.
    :param report_path: Audio report JSON path.
    :param subtitle_report_path: Subtitle report JSON path.
    :param include_video: Whether video track names should be processed.
    :param include_audio: Whether audio track names should be processed.
    :param include_subtitles: Whether embedded subtitle track names should be processed.
    :param selected_file: Optional exact selected file under the input directory.
    :return: Rename workflow summary.
    """

    summary = RenameSummary()  # Initialize workflow summary.
    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        summary.failed += 1  # Count missing input as failure.
        return summary  # Return summary.
    if selected_file is not None and resolve_selected_file(root_path, selected_file) is None:  # Verify exact selected file can be processed.
        summary.failed += 1  # Count invalid file selection.
        return summary  # Return summary.

    if include_audio:  # Verify audio processing was selected.
        generate_audio_report(input_dir, report_path, selected_file)  # Generate selected audio report.
    if include_subtitles:  # Verify subtitle processing was selected.
        generate_subtitle_report(input_dir, subtitle_report_path, selected_file)  # Generate selected subtitle report.

    return rename_track_metadata(input_dir, report_path, subtitle_report_path, include_video, include_audio, include_subtitles, selected_file)  # Apply selected metadata changes.


def add_track_type_arguments(parser: argparse.ArgumentParser, include_video: bool) -> None:
    """
    Add track-type selection arguments to a parser.

    :param parser: Argument parser.
    :param include_video: Whether video selection should be accepted.
    :return: None.
    """

    if include_video:  # Verify video flag belongs to this command.
        parser.add_argument("--video", action="store_true", help="Process video track names from MKV filename stems.")  # Add video selection flag.
    parser.add_argument("--audio", action="store_true", help="Process audio track names from detected or reviewed languages.")  # Add audio selection flag.
    parser.add_argument("--subtitles", action="store_true", help="Process embedded subtitle track names from detected or reviewed languages.")  # Add subtitle selection flag.


def add_path_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add shared path arguments to a parser.

    :param parser: Argument parser.
    :return: None.
    """

    parser.add_argument("--input-dir", default=INPUT_DIR, help="Input directory containing Matroska files.")  # Add input directory option.
    parser.add_argument("--audio-report", default=str(AUDIO_REPORT_PATH), help="Audio report JSON path.")  # Add audio report path option.
    parser.add_argument("--subtitle-report", default=str(SUBTITLE_REPORT_PATH), help="Subtitle report JSON path.")  # Add subtitle report path option.
    parser.add_argument("--file", default=None, help="Exact relative or absolute MKV file under input directory.")  # Add single-file option.


def read_track_selection(parsed_args: argparse.Namespace, include_video: bool) -> TrackSelection:
    """
    Read track selection from parsed arguments.

    :param parsed_args: Parsed CLI arguments.
    :param include_video: Whether parsed arguments include video selection.
    :return: Track selection.
    """

    video_selected = bool(getattr(parsed_args, "video", False)) if include_video else False  # Read video flag when present.
    return TrackSelection(video_selected, bool(parsed_args.audio), bool(parsed_args.subtitles))  # Return selected track flags.


def require_track_selection(parser: argparse.ArgumentParser, selection: TrackSelection) -> None:
    """
    Require at least one selected track type.

    :param parser: Argument parser.
    :param selection: Track selection.
    :return: None.
    """

    if not selection.video and not selection.audio and not selection.subtitles:  # Verify at least one track type was selected.
        parser.error("Select at least one of --video, --audio, or --subtitles.")  # Exit with argument error.


def build_rename_argument_parser() -> argparse.ArgumentParser:
    """
    Build the reviewed-report rename argument parser.

    :return: Argument parser.
    """

    parser = argparse.ArgumentParser(description="Rename selected MKV track names from reviewed reports.")  # Create CLI parser.
    add_track_type_arguments(parser, True)  # Add video, audio, and subtitle selection flags.
    add_path_arguments(parser)  # Add shared path options.
    return parser  # Return configured parser.


def build_process_argument_parser() -> argparse.ArgumentParser:
    """
    Build the integrated process argument parser.

    :return: Argument parser.
    """

    parser = argparse.ArgumentParser(description="Generate selected reports and rename selected MKV track names.")  # Create CLI parser.
    add_track_type_arguments(parser, True)  # Add video, audio, and subtitle selection flags.
    add_path_arguments(parser)  # Add shared path options.
    return parser  # Return configured parser.


def run_rename_cli(arguments: list[str] | None = None) -> int:
    """
    Run the reviewed-report rename CLI.

    :param arguments: Optional argument list.
    :return: Process exit status.
    """

    parser = build_rename_argument_parser()  # Build CLI parser.
    parsed_args = parser.parse_args(arguments)  # Parse CLI arguments.
    selection = read_track_selection(parsed_args, True)  # Read selected track types.
    require_track_selection(parser, selection)  # Require explicit selection.
    summary = rename_track_metadata(parsed_args.input_dir, Path(parsed_args.audio_report), Path(parsed_args.subtitle_report), selection.video, selection.audio, selection.subtitles, parsed_args.file)  # Run selected rename workflow.
    return 1 if summary.failed > 0 else 0  # Return nonzero when workflow failed.


def run_process_cli(arguments: list[str] | None = None) -> int:
    """
    Run the integrated report-and-rename CLI.

    :param arguments: Optional argument list.
    :return: Process exit status.
    """

    parser = build_process_argument_parser()  # Build CLI parser.
    parsed_args = parser.parse_args(arguments)  # Parse CLI arguments.
    selection = read_track_selection(parsed_args, True)  # Read selected track types.
    require_track_selection(parser, selection)  # Require explicit selection.
    summary = process_track_metadata(parsed_args.input_dir, Path(parsed_args.audio_report), Path(parsed_args.subtitle_report), selection.video, selection.audio, selection.subtitles, parsed_args.file)  # Run integrated workflow.
    return 1 if summary.failed > 0 else 0  # Return nonzero when workflow failed.


def rename_subtitle_tracks(input_dir: str = INPUT_DIR, subtitle_report_path: Path = SUBTITLE_REPORT_PATH) -> RenameSummary:
    """
    Rename embedded subtitle-track metadata according to subtitles_report.json.

    :param input_dir: Input directory path string.
    :param subtitle_report_path: Subtitle report JSON path.
    :return: Rename workflow summary.
    """

    summary = RenameSummary()  # Initialize workflow summary.
    root_path = Path(input_dir).resolve(strict=False)  # Resolve configured input directory.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        summary.failed += 1  # Count missing input as failure.
        return summary  # Return summary.

    report_data = load_report_data(subtitle_report_path)  # Load subtitle report JSON.
    if report_data is None:  # Verify report loaded.
        summary.failed += 1  # Count missing or malformed report.
        return summary  # Return summary.

    planned_renames = collect_planned_subtitle_renames(report_data, root_path, summary)  # Collect subtitle report rename requests.
    grouped_plans = group_subtitle_plans_by_file(planned_renames)  # Group subtitle plans by media file.
    apply_grouped_renames({}, grouped_plans, root_path, summary, False)  # Apply subtitle-only rename operations.

    print(f"Summary: planned={summary.planned}, changed={summary.changed}, warnings={summary.warnings}, skipped={summary.skipped}, failed={summary.failed}")  # Report summary counts.
    for message in summary.messages:  # Iterate accumulated messages.
        print(message)  # Report detailed message.

    return summary  # Return workflow summary.


def main() -> None:
    """
    Run track-name metadata renaming from audio_report.json and subtitles_report.json.

    :return: None.
    """

    sys.exit(run_rename_cli())  # Run CLI and return process status.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default rename workflow.
