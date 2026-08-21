"""
================================================================================
Subtitle Tracks Renamer
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-15
Description :
    Entry point for applying subtitle track metadata edits from generated reports
    to Matroska video files. Reads subtitle rename reports and safely applies
    metadata changes using mkvpropedit.

    Key features include:
        - CLI interface for subtitle rename operations
        - Report-driven metadata application
        - Safe mkvpropedit-based file modification
        - Rollback and error recovery mechanisms
        - Execution timing and progress feedback
        - Detailed logging of all modifications

Usage:
    1. First generate subtitle reports using subtitle_report.py
    2. Run renamer with generated reports
        $ python subtitle_tracks_renamer.py /path/to/videos
    3. Or invoke via Makefile
        $ make rename_subtitles
    4. Or call programmatically
        from subtitle_tracks_renamer import run_rename_cli
        run_rename_cli(input_directory, report_path)

Outputs:
    - Updated Matroska files with renamed subtitle tracks
    - Logs/subtitle_tracks_renamer.log (detailed rename log)
    - Console output with welcome message and timing information
    - Backup copies of modified files (optional)

TODOs:
    - Implement automatic backup before applying edits
    - Add transaction-like semantics for batch renames
    - Support for undo/rollback operations
    - Dry-run mode to preview changes before applying

Dependencies:
    - Python >= 3.8
    - track_metadata_renamer module (core rename infrastructure)
    - report module (report parsing and data structures)
    - Logger module (dual-channel console/file logging)
    - utils.utils module (timing and color utilities)

Assumptions & Notes:
    - Subtitle reports must exist and be recent
    - Matroska files referenced in reports must still exist
    - mkvpropedit must be installed and available in PATH
    - File permissions allow modification of target Matroska files
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Track execution start and finish times.
import sys  # Read forwarded CLI arguments.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from report import INPUT_DIR, build_log_path, read_input_dir_argument, read_run_id_argument  # Reuse input-specific log naming.
from track_metadata_renamer import run_rename_cli  # Reuse selected rename CLI.
from utils.completion_sound import read_completion_sound_argument, register_completion_sound  # Reuse shared completion-sound flag reading and late registration.
from utils.utils import calculate_execution_time, BackgroundColors  # Track and display execution time.


def main() -> None:
    """
    Run embedded subtitle-track metadata renaming from a subtitle report.

    :return: None.
    """

    completion_sound_enabled = read_completion_sound_argument(sys.argv[1:])  # Resolve late completion-sound ownership from raw CLI flags.
    logger = Logger(str(build_log_path(Path(__file__), read_input_dir_argument(sys.argv[1:], INPUT_DIR), read_run_id_argument(sys.argv[1:]))), clean=True)  # Create input-specific log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Tracks Renamer{BackgroundColors.GREEN} program!{BackgroundColors.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    status = run_rename_cli(["--subtitles", *sys.argv[1:]])  # Run subtitle rename workflow
    
    finish_time = datetime.datetime.now()  # Get the finish time of the program
    
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{BackgroundColors.RESET_ALL}"
    )  # Output the start and finish times
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{BackgroundColors.RESET_ALL}"
    )  # Output the end of the program message

    register_completion_sound(completion_sound_enabled)  # Register shared completion sound only after CLI resolution and normal workflow finish.
    
    sys.exit(status)  # Run subtitle rename workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default subtitle rename workflow.
