"""
Generate the embedded subtitle-track rename report.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from report import generate_subtitle_report  # Reuse subtitle report generation workflow.


def main() -> None:
    """
    Generate the embedded subtitle-track rename report.

    :return: None.
    """

    generate_subtitle_report()  # Generate default subtitle report.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Generate subtitle report from default configuration.
