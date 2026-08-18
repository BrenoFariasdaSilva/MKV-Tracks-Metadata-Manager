"""
Run integrated MKV track metadata-name reporting and renaming.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Track execution start and finish times.
import sys  # Return meaningful CLI exit statuses.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from track_metadata_renamer import run_process_cli  # Reuse integrated process CLI.
from utils.utils import calculate_execution_time, BackgroundColors  # Track and display execution time.


def main() -> None:
    """
    Run integrated selected track-name reporting and renaming.

    :return: None.
    """

    logger = Logger(str(Path(__file__).with_name("Logs") / f"{Path(__file__).stem}.log"), clean=True)  # Create project-local log mirror.
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

