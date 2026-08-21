"""
================================================================================
Subtitle Track Report Generator
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-15
Description :
    Entry point for generating subtitle track metadata reports from Matroska
    video files. Provides CLI interface for creating editable JSON reports that
    document subtitle track names, languages, and metadata to support the
    subtitle rename workflow.

    Key features include:
        - Integrated CLI for report generation
        - Automatic language detection for unnamed subtitles
        - ISO 639-2 language code standardization
        - JSON report format compatible with subtitle_tracks_renamer
        - Execution timing and progress feedback
        - Detailed logging to file and terminal

Usage:
    1. Run as standalone entry point with directory argument
        $ python subtitle_report.py /path/to/videos
    2. Or invoke via Makefile task
        $ make subtitle_report
    3. Or use as callable from other tools
        from subtitle_report import run_report_cli
        run_report_cli(input_directory)

Outputs:
    - Reports/D-Sem*-subtitles_report.json (subtitle track metadata)
    - Logs/subtitle_report.log (execution details)
    - Console output with welcome message and timing information

TODOs:
    - Add filtering options for subtitle codec types
    - Implement report diff view before applying changes
    - Support for selective report generation by track
    - Batch report generation for large video libraries

Dependencies:
    - Python >= 3.8
    - report module (track metadata reporting infrastructure)
    - Logger module (dual-channel console/file logging)
    - utils.utils module (timing and color utilities)

Assumptions & Notes:
    - Input directory must be accessible and contain Matroska files
    - Report output directory (Reports/) is created automatically
    - All subtitles are assumed to be text-based unless stated otherwise
    - Language detection requires internet connectivity for langdetect
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Track execution start and finish times.
import sys  # Read forwarded CLI arguments.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from report import INPUT_DIR, build_log_path, read_input_dir_argument, read_run_id_argument, run_report_cli  # Reuse report generation CLI and log naming.
from utils.completion_sound import read_completion_sound_argument, register_completion_sound  # Reuse shared completion-sound flag reading and late registration.
from utils.utils import calculate_execution_time, BackgroundColors  # Track and display execution time.


def main() -> None:
    """
    Generate the embedded subtitle-track rename report.

    :return: None.
    """

    completion_sound_enabled = read_completion_sound_argument(sys.argv[1:])  # Resolve late completion-sound ownership from raw CLI flags.
    logger = Logger(str(build_log_path(Path(__file__), read_input_dir_argument(sys.argv[1:], INPUT_DIR), read_run_id_argument(sys.argv[1:]))), clean=True)  # Create input-specific log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Report Generator{BackgroundColors.GREEN} program!{BackgroundColors.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    status = run_report_cli(["--subtitles", *sys.argv[1:]])  # Run subtitle report workflow
    
    finish_time = datetime.datetime.now()  # Get the finish time of the program
    
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{BackgroundColors.RESET_ALL}"
    )  # Output the start and finish times
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{BackgroundColors.RESET_ALL}"
    )  # Output the end of the program message

    register_completion_sound(completion_sound_enabled)  # Register shared completion sound only after CLI resolution and normal workflow finish.
    
    sys.exit(status)  # Run subtitle report workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate subtitle report from default configuration.

