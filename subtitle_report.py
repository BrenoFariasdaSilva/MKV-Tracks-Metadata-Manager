"""
Generate the embedded subtitle-track rename report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Track execution start and finish times.
import sys  # Read forwarded CLI arguments.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from report import run_report_cli  # Reuse report generation CLI.
from utils.utils import calculate_execution_time, BackgroundColors, Style  # Track and display execution time.


def main() -> None:
    """
    Generate the embedded subtitle-track rename report.

    :return: None.
    """

    logger = Logger(str(Path(__file__).with_name("Logs") / f"{Path(__file__).stem}.log"), clean=True)  # Create project-local log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Report Generator{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    status = run_report_cli(["--subtitles", *sys.argv[1:]])  # Run subtitle report workflow
    
    finish_time = datetime.datetime.now()  # Get the finish time of the program
    
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message
    
    sys.exit(status)  # Run subtitle report workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate subtitle report from default configuration.

