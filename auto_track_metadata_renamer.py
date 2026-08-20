"""
================================================================================
Automatic Track Metadata Renamer
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-15
Description :
    Integrated CLI tool that combines audio and subtitle track reporting with
    automatic metadata renaming in a single workflow. Scans Matroska files for
    embedded tracks, generates detailed reports, and applies safe metadata edits.

    Key features include:
        - Unified report generation for video, audio, and subtitle tracks
        - Automatic language detection for unnamed tracks
        - Safe mkvpropedit-based metadata application
        - Default audio and subtitle track assignment
        - Detailed execution summary with timing information
        - Progress bar feedback during long operations

Usage:
    1. Configure input directory and track selection flags
    2. Run the automatic workflow via Makefile or direct invocation
        $ make process  or  $ python auto_track_metadata_renamer.py
    3. Review generated reports in Reports/ directory
    4. Automatic renaming applies edits from most recent reports

Outputs:
    - Reports/D-Sem*-audio_report.json (audio track report)
    - Reports/D-Sem*-subtitles_report.json (subtitle track report)
    - Logs/auto_track_metadata_renamer.log (execution log)
    - Renamed Matroska files with updated track metadata

TODOs:
    - Implement dry-run mode to preview changes without applying edits
    - Add rollback capability for failed rename operations
    - Support for external report import from other tools
    - Parallel file processing for faster large-batch operations

Dependencies:
    - Python >= 3.8
    - MKVToolNix >= 70 (mkvpropedit, mkvmerge)
    - ffmpeg (ffprobe for metadata inspection)
    - tqdm >= 4.70.0 (progress bar display)
    - colorama >= 0.4.6 (terminal colors)

Assumptions & Notes:
    - Input directory contains Matroska files (.mkv, .mk3d)
    - Reports are synchronized with files before each rename operation
    - Default language selection prioritizes most common track
    - Failed renames do not halt the workflow; see log for details
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Track execution start and finish times.
import sys  # Return meaningful CLI exit statuses.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from report import INPUT_DIR, build_log_path, read_input_dir_argument, read_run_id_argument  # Reuse input-specific log naming.
from track_metadata_renamer import run_process_cli  # Reuse integrated process CLI.
from utils.utils import calculate_execution_time, BackgroundColors  # Track and display execution time.


def main() -> None:
    """
    Run integrated selected track-name reporting and renaming.

    :return: None.
    """

    logger = Logger(str(build_log_path(Path(__file__), read_input_dir_argument(sys.argv[1:], INPUT_DIR), read_run_id_argument(sys.argv[1:]))), clean=True)  # Create input-specific log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Automatic Track Metadata Renamer{BackgroundColors.GREEN} program!{BackgroundColors.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    status = run_process_cli()  # Run process CLI and capture status
    
    finish_time = datetime.datetime.now()  # Get the finish time of the program
    
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{BackgroundColors.RESET_ALL}"
    )  # Output the start and finish times
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{BackgroundColors.RESET_ALL}"
    )  # Output the end of the program message
    
    sys.exit(status)  # Run process CLI and return status.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute automatic workflow.

