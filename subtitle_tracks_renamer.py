"""
Rename embedded subtitle-track name metadata from subtitles_report.json.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import sys  # Read forwarded CLI arguments.

from track_metadata_renamer import run_rename_cli  # Reuse selected rename CLI.


def main() -> None:
    """
    Run embedded subtitle-track metadata renaming from subtitles_report.json.

    :return: None.
    """

    sys.exit(run_rename_cli(["--subtitles", *sys.argv[1:]]))  # Run subtitle rename workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default subtitle rename workflow.
