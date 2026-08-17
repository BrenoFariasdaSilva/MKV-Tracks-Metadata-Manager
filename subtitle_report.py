"""
Generate the embedded subtitle-track rename report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import sys  # Read forwarded CLI arguments.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from report import run_report_cli  # Reuse report generation CLI.


def main() -> None:
    """
    Generate the embedded subtitle-track rename report.

    :return: None.
    """

    logger = Logger(str(Path(__file__).with_name("Logs") / f"{Path(__file__).stem}.log"), clean=True)  # Create project-local log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    sys.exit(run_report_cli(["--subtitles", *sys.argv[1:]]))  # Run subtitle report workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate subtitle report from default configuration.
