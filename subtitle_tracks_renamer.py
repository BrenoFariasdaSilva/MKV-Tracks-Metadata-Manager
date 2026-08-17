"""
Rename embedded subtitle-track name metadata from a subtitle report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import sys  # Read forwarded CLI arguments.
from pathlib import Path  # Build project-local log paths.

from Logger import Logger  # Mirror terminal output to a log file.
from track_metadata_renamer import run_rename_cli  # Reuse selected rename CLI.


def main() -> None:
    """
    Run embedded subtitle-track metadata renaming from a subtitle report.

    :return: None.
    """

    logger = Logger(str(Path(__file__).with_name("Logs") / f"{Path(__file__).stem}.log"), clean=True)  # Create project-local log mirror.
    sys.stdout = logger  # Mirror standard output to terminal and log file.
    sys.stderr = logger  # Mirror standard error to terminal and log file.
    sys.exit(run_rename_cli(["--subtitles", *sys.argv[1:]]))  # Run subtitle rename workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default subtitle rename workflow.
