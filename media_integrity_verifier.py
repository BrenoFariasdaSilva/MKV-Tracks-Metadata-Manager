"""
================================================================================
Media Integrity Verifier
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-20
Description :
    Verifies Matroska media-file integrity after metadata-only edits finish.
    Runs read-only ffprobe inspection and FFmpeg decoding against files modified
    by mkvpropedit and reports container or stream errors without remuxing,
    re-encoding, deleting, replacing, or otherwise modifying media files.

    Key features include:
        - Post-metadata read-only media verification
        - ffprobe container inspection and FFmpeg decoding with strict returns
        - Safe executable discovery through the existing MKVToolNix wrapper
        - Colored in-place progress display for batch verification
        - Final verification summary with failed file details

Usage:
    1. Run the normal metadata workflow via Makefile or Python.
    2. Integrity verification runs after successful metadata edits.
        $ make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio"
    3. Review terminal output and Logs/track_metadata_renamer.log for failures.

Outputs:
    - Console summary showing successful and failed media verification results
    - Logs/track_metadata_renamer.log entries through the calling workflow
    - Nonzero workflow status when any modified file fails verification

TODOs:
    - Add optional user-controlled sampling mode if full-file decoding becomes too slow.

Dependencies:
    - Python >= 3.8
    - FFmpeg (ffmpeg and ffprobe executables)
    - tqdm >= 4.70.0 (progress bar display)
    - colorama >= 0.4.6 (terminal colors)

Assumptions & Notes:
    - Input files are Matroska containers already supported by this project.
    - Verification is read-only and never creates replacement media files.
    - ffprobe or FFmpeg failures mean verification failure, not successful media validation.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import argparse  # Parse standalone media-verification CLI flags.
from dataclasses import dataclass, field  # Define typed verification records.
from pathlib import Path  # Represent media file paths.
import subprocess  # Run FFmpeg safely with argument lists.
from tqdm import tqdm  # Display verification progress without flooding the terminal.

from mkvpropedit_wrapper import MkvpropeditResult, find_executable  # Reuse project executable discovery and edit results.
from report import PROGRESS_BAR_FORMAT, SUPPORTED_EXTENSIONS, BackgroundColors  # Reuse media scope and terminal colors.
from utils.completion_sound import add_completion_sound_arguments, resolve_completion_sound_enabled, register_completion_sound  # Reuse shared completion-sound CLI and late registration.


# Constants:

FFMPEG_ERROR_FLAGS = ("-v", "error", "-xerror")  # Make FFmpeg fail on reported decode or container errors.
FFMPEG_NULL_OUTPUT = ("-map", "0:v?", "-map", "0:a?", "-f", "null", "-")  # Decode audio and video streams and discard output without writing media.
FFPROBE_OUTPUT_FLAGS = ("-v", "error", "-show_streams", "-show_format", "-of", "json")  # Read container and stream metadata without writing media.


@dataclass(frozen=True)
class MediaIntegrityResult:
    """
    Stores one media integrity verification result.
    """

    file_path: Path  # Store verified media file path.
    command: list[str]  # Store executed FFmpeg command arguments.
    returncode: int  # Store FFmpeg return code or synthetic failure code.
    stdout: str  # Store captured standard output.
    stderr: str  # Store captured standard error.
    success: bool  # Store whether media verification succeeded.
    message: str = ""  # Store concise failure reason.


@dataclass
class MediaIntegritySummary:
    """
    Stores media integrity verification counters and results.
    """

    planned: int = 0  # Store number of files selected for verification.
    verified: int = 0  # Store number of files successfully verified.
    failed: int = 0  # Store number of files that failed verification.
    results: list[MediaIntegrityResult] = field(default_factory=list)  # Store per-file verification results.


def collect_modified_media_files(edit_results: list[MkvpropeditResult]) -> list[Path]:
    """
    Collect unique media files modified by successful metadata edits.

    :param edit_results: mkvpropedit execution results from the rename workflow.
    :return: Unique modified media file paths in workflow order.
    """

    modified_files: list[Path] = []  # Store unique successfully modified media paths.
    seen_files: set[Path] = set()  # Store normalized paths already selected for verification.
    for edit_result in edit_results:  # Iterate mkvpropedit results in workflow order.
        normalized_path = edit_result.file_path.resolve(strict=False)  # Normalize path for stable uniqueness.
        if not edit_result.success or edit_result.changed_count <= 0:  # Verify only successful modifying commands are selected.
            continue  # Skip failed or no-op edit results.
        if normalized_path in seen_files:  # Verify duplicate edit result path is not repeated.
            continue  # Skip duplicate path.
        modified_files.append(edit_result.file_path)  # Preserve original path object for display and subprocess use.
        seen_files.add(normalized_path)  # Mark normalized path as selected.
    return modified_files  # Return files that were actually modified.


def build_ffprobe_verify_command(file_path: Path, executable: str) -> list[str]:
    """
    Build the read-only ffprobe verification command for one media file.

    :param file_path: Media file path.
    :param executable: ffprobe executable path or command name.
    :return: ffprobe command arguments.
    """

    return [executable, *FFPROBE_OUTPUT_FLAGS, str(file_path)]  # Return safe read-only probe command.


def build_ffmpeg_verify_command(file_path: Path, executable: str) -> list[str]:
    """
    Build the read-only FFmpeg verification command for one media file.

    :param file_path: Media file path.
    :param executable: FFmpeg executable path or command name.
    :return: FFmpeg command arguments.
    """

    return [executable, *FFMPEG_ERROR_FLAGS, "-i", str(file_path), *FFMPEG_NULL_OUTPUT]  # Return safe read-only decode command.


def verify_media_file(file_path: Path, executable: str | None = None) -> MediaIntegrityResult:
    """
    Verify one media file through read-only FFmpeg decoding.

    :param file_path: Media file path.
    :param executable: Optional FFmpeg executable path.
    :return: Media integrity verification result.
    """

    command_executable = executable or find_executable("ffmpeg")  # Locate FFmpeg using project executable discovery.
    probe_executable = find_executable("ffprobe") if executable is None else "ffprobe"  # Locate ffprobe unless caller injected a test executable.
    if command_executable is None:  # Verify FFmpeg is available.
        return MediaIntegrityResult(file_path, ["ffmpeg", str(file_path)], 127, "", "ffmpeg not found", False, "ffmpeg not found")  # Return explicit missing-tool failure.
    if probe_executable is None:  # Verify ffprobe is available.
        return MediaIntegrityResult(file_path, ["ffprobe", str(file_path)], 127, "", "ffprobe not found", False, "ffprobe not found")  # Return explicit missing-tool failure.
    if not file_path.exists():  # Verify media file still exists.
        return MediaIntegrityResult(file_path, [command_executable, str(file_path)], 2, "", "media file not found", False, "media file not found")  # Return explicit missing-file failure.
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:  # Verify project-supported Matroska extension.
        return MediaIntegrityResult(file_path, [command_executable, str(file_path)], 2, "", "unsupported media extension", False, "unsupported media extension")  # Return explicit unsupported-file failure.

    try:  # Read file size before invoking FFmpeg.
        if file_path.stat().st_size == 0:  # Verify media file is not empty.
            return MediaIntegrityResult(file_path, [command_executable, str(file_path)], 2, "", "empty media file (0 bytes)", False, "empty media file (0 bytes)")  # Return explicit empty-file failure.
    except OSError as error:  # Handle unreadable filesystem metadata.
        return MediaIntegrityResult(file_path, [command_executable, str(file_path)], 2, "", str(error), False, str(error))  # Return explicit stat failure.

    probe_command = build_ffprobe_verify_command(file_path, probe_executable)  # Build read-only ffprobe command.
    try:  # Execute ffprobe verification.
        probe_result = subprocess.run(probe_command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run ffprobe without shell expansion.
    except OSError as error:  # Handle probe execution failure.
        return MediaIntegrityResult(file_path, probe_command, 126, "", str(error), False, str(error))  # Return probe execution failure.

    if probe_result.returncode != 0:  # Verify ffprobe succeeded.
        probe_failure_text = (probe_result.stderr or probe_result.stdout).strip()  # Capture ffprobe diagnostic text.
        return MediaIntegrityResult(file_path, probe_command, probe_result.returncode, probe_result.stdout or "", probe_result.stderr or "", False, probe_failure_text)  # Return probe failure.

    command = build_ffmpeg_verify_command(file_path, command_executable)  # Build read-only FFmpeg command.
    try:  # Execute FFmpeg verification.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run FFmpeg without shell expansion.
    except OSError as error:  # Handle command execution failure.
        return MediaIntegrityResult(file_path, command, 126, "", str(error), False, str(error))  # Return execution failure.

    failure_text = (result.stderr or result.stdout).strip()  # Capture FFmpeg diagnostic text.
    success = result.returncode == 0  # Resolve success only from zero return code.
    return MediaIntegrityResult(file_path, command, result.returncode, result.stdout or "", result.stderr or "", success, failure_text)  # Return verification result.


def build_integrity_progress_status(file_path: Path, result: MediaIntegrityResult | None) -> str:
    """
    Build one concise in-place status for the current verified file.

    :param file_path: Current media file path.
    :param result: Verification result when available.
    :return: Short status text for the progress bar.
    """

    cyan_name = f"{BackgroundColors.CYAN}{file_path.name}{BackgroundColors.GREEN}"  # Keep the current file name cyan inside the green progress bar message.
    if result is None:  # Verify no command result is available yet.
        return f"Verifying: {cyan_name}"  # Return active verification status.
    if result.success:  # Verify FFmpeg completed successfully.
        return f"Verified: {cyan_name}"  # Return success status.
    return f"Verification failed: {cyan_name}"  # Return failure status.


def print_integrity_summary(summary: MediaIntegritySummary) -> None:
    """
    Print final media integrity verification summary.

    :param summary: Media integrity verification summary.
    :return: None.
    """

    summary_text = f"planned={summary.planned}, verified={summary.verified}, failed={summary.failed}"  # Build summary values.
    summary_color = BackgroundColors.GREEN if summary.failed == 0 else BackgroundColors.RED  # Pick severity color for summary label.
    print(f"\n{summary_color}Integrity verification summary:{BackgroundColors.CYAN} {summary_text}{BackgroundColors.RESET_ALL}")  # Print colored summary.
    for result in summary.results:  # Iterate verification results.
        if result.success:  # Verify only failures need standalone detail lines.
            continue  # Skip successful files in final detail output.
        detail = result.message if result.message != "" else f"ffmpeg returned {result.returncode}"  # Build concise failure detail.
        print(f"{BackgroundColors.RED}Integrity verification failed for{BackgroundColors.RESET_ALL}: {BackgroundColors.CYAN}{result.file_path}: {detail}{BackgroundColors.RESET_ALL}")  # Print failure detail after progress bar closes.


def verify_media_files(file_paths: list[Path]) -> MediaIntegritySummary:
    """
    Verify media files and report colored progress.

    :param file_paths: Media files to verify.
    :return: Media integrity verification summary.
    """

    summary = MediaIntegritySummary(planned=len(file_paths))  # Initialize verification summary.
    executable = find_executable("ffmpeg")  # Locate FFmpeg once for the whole batch.
    with tqdm(file_paths, desc=f"{BackgroundColors.GREEN}Verifying media integrity", unit="file", colour="green", bar_format=PROGRESS_BAR_FORMAT) as progress_bar:  # Build cleanup-managed progress bar.
        for file_path in progress_bar:  # Iterate selected media files.
            progress_bar.set_description(f"{BackgroundColors.GREEN}{build_integrity_progress_status(file_path, None)}{BackgroundColors.GREEN}")  # Render active status.
            result = verify_media_file(file_path, executable)  # Verify one media file.
            summary.results.append(result)  # Store per-file result.
            if result.success:  # Verify media integrity succeeded.
                summary.verified += 1  # Count successful verification.
            else:  # Handle media integrity failure.
                summary.failed += 1  # Count failed verification.
            progress_bar.set_description(f"{BackgroundColors.GREEN}{build_integrity_progress_status(file_path, result)}{BackgroundColors.GREEN}")  # Render final per-file status.

    print_integrity_summary(summary)  # Print final verification summary after progress bar closes.
    return summary  # Return verification summary.


def verify_mkvpropedit_results(edit_results: list[MkvpropeditResult]) -> MediaIntegritySummary:
    """
    Verify media files changed by successful mkvpropedit operations.

    :param edit_results: mkvpropedit execution results from the rename workflow.
    :return: Media integrity verification summary.
    """

    modified_files = collect_modified_media_files(edit_results)  # Collect exactly modified files from successful edit results.
    if not modified_files:  # Verify whether any modified files require verification.
        summary = MediaIntegritySummary()  # Build empty verification summary.
        print_integrity_summary(summary)  # Report explicit empty verification summary.
        return summary  # Return empty verification summary.
    return verify_media_files(modified_files)  # Verify modified media files.


def build_verify_argument_parser() -> argparse.ArgumentParser:
    """
    Build standalone media-verification argument parser.

    :return: Argument parser.
    """

    parser = argparse.ArgumentParser(description="Verify Matroska media integrity for one or more files.")  # Create standalone media-verification parser.
    parser.add_argument("files", nargs="*", help="Matroska file paths to verify.")  # Add positional media-file arguments.
    add_completion_sound_arguments(parser)  # Add shared completion-sound override flags.
    return parser  # Return configured parser.


def main() -> None:
    """
    Run standalone media integrity verification for paths passed on the command line.

    :return: None.
    """

    import sys  # Import CLI arguments only for standalone execution.

    parser = build_verify_argument_parser()  # Build standalone media-verification parser for sound ownership resolution.
    parsed_args = parser.parse_args(sys.argv[1:])  # Parse standalone media-verification arguments once in main.
    summary = verify_media_files([Path(file_path) for file_path in parsed_args.files])  # Verify requested media files from parsed positional paths.
    status = 1 if summary.failed > 0 else 0  # Resolve standalone media-verification exit status from summary.
    register_completion_sound(resolve_completion_sound_enabled(parsed_args.completion_sound))  # Register shared completion sound only after CLI resolution and normal workflow finish.
    sys.exit(status)  # Return nonzero when verification fails.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute standalone verification workflow.
