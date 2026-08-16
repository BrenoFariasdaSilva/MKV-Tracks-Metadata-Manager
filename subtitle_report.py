"""
Generate the embedded subtitle-track rename report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import sys  # Read forwarded CLI arguments.

from report import run_report_cli  # Reuse report generation CLI.


def main() -> None:
    """
    Generate the embedded subtitle-track rename report.

    :return: None.
    """

    sys.exit(run_report_cli(["--subtitles", *sys.argv[1:]]))  # Run subtitle report workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate subtitle report from default configuration.
