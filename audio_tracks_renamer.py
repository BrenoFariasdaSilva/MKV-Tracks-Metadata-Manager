"""
Rename Matroska audio-track name metadata from an editable report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from dataclasses import dataclass, field  # Define typed workflow records.
from pathlib import Path  # Represent filesystem paths.
from typing import Any  # Type dynamic JSON data.
import json  # Read report JSON.

from mkvpropedit_wrapper import AudioTrackRename, MkvpropeditResult, apply_audio_track_renames, valid_target_name  # Apply mkvpropedit edits.
from report import INPUT_DIR, REPORT_PATH, SUPPORTED_EXTENSIONS, parse_group_key, parse_occurrence_key, raw_track_name, read_audio_tracks  # Reuse report parsing and metadata inspection.


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


def validate_plans_for_file(file_path: Path, plans: list[PlannedRename], input_dir: Path, summary: RenameSummary) -> list[AudioTrackRename]:
    """
    Validate planned renames against current file metadata.

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

    operations: list[AudioTrackRename] = []  # Store validated mkvpropedit operations.
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

        operations.append(AudioTrackRename(plan.audio_position, current_track.current_name, plan.target_name, current_track.track_uid))  # Store validated operation.
        summary.planned += 1  # Count validated edit.

    return operations  # Return validated operations.


def apply_grouped_renames(grouped_plans: dict[Path, list[PlannedRename]], input_dir: Path, summary: RenameSummary) -> list[MkvpropeditResult]:
    """
    Apply validated renames one mkvpropedit invocation per file.

    :param grouped_plans: Planned renames keyed by file path.
    :param input_dir: Input directory path.
    :param summary: Mutable workflow summary.
    :return: mkvpropedit results.
    """

    results: list[MkvpropeditResult] = []  # Store mkvpropedit results.
    for file_path in sorted(grouped_plans, key=lambda path: path.as_posix().lower()):  # Iterate files deterministically.
        operations = validate_plans_for_file(file_path, grouped_plans[file_path], input_dir, summary)  # Validate operations against current metadata.
        if not operations:  # Verify file has operations after validation.
            continue  # Skip files without edits.

        result = apply_audio_track_renames(file_path, operations)  # Apply mkvpropedit edits.
        results.append(result)  # Store command result.
        if result.success and result.warning:  # Verify mkvpropedit completed with warnings.
            summary.changed += result.changed_count  # Count changes because MKVToolNix continued after warnings.
            summary.warnings += 1  # Count warning-bearing file.
            warning_text = (result.stderr or result.stdout).strip()  # Resolve warning output text.
            summary.messages.append(f"mkvpropedit warning for {file_path}: {warning_text}")  # Store warning reason.
            print(f"Renamed {result.changed_count} audio track(s) with warning: {file_path}")  # Report warning completion.
        elif result.success:  # Verify mkvpropedit succeeded cleanly.
            summary.changed += result.changed_count  # Count successful changes.
            print(f"Renamed {result.changed_count} audio track(s): {file_path}")  # Report file success.
        else:  # Handle mkvpropedit failure.
            summary.failed += result.changed_count  # Count failed changes.
            summary.messages.append(f"mkvpropedit failed for {file_path}: {result.stderr.strip()}")  # Store failure reason.
            print(f"mkvpropedit failed for {file_path}: {result.stderr.strip()}")  # Report file failure.

    return results  # Return command results.


def rename_audio_tracks(input_dir: str = INPUT_DIR, report_path: Path = REPORT_PATH) -> RenameSummary:
    """
    Rename audio-track metadata according to report.json.

    :param input_dir: Input directory path string.
    :param report_path: Report JSON path.
    :return: Rename workflow summary.
    """

    summary = RenameSummary()  # Initialize workflow summary.
    root_path = Path(input_dir)  # Resolve configured input directory.
    if not root_path.exists() or not root_path.is_dir():  # Verify input directory exists.
        print(f"Input directory not found: {root_path}")  # Report missing input directory.
        summary.failed += 1  # Count missing input as failure.
        return summary  # Return summary.

    report_data = load_report_data(report_path)  # Load report JSON.
    if report_data is None:  # Verify report loaded.
        summary.failed += 1  # Count missing or malformed report.
        return summary  # Return summary.

    planned_renames = collect_planned_renames(report_data, root_path, summary)  # Collect report rename requests.
    grouped_plans = group_plans_by_file(planned_renames)  # Group plans by media file.
    apply_grouped_renames(grouped_plans, root_path, summary)  # Apply validated rename operations.

    print(f"Summary: planned={summary.planned}, changed={summary.changed}, warnings={summary.warnings}, skipped={summary.skipped}, failed={summary.failed}")  # Report summary counts.
    for message in summary.messages:  # Iterate accumulated messages.
        print(message)  # Report detailed message.

    return summary  # Return workflow summary.


def main() -> None:
    """
    Run audio-track metadata renaming from report.json.

    :return: None.
    """

    rename_audio_tracks()  # Rename tracks using default configuration.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default rename workflow.
