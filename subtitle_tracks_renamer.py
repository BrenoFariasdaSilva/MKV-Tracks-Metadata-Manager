"""
Rename embedded subtitle-track name metadata from subtitles_report.json.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from audio_tracks_renamer import rename_subtitle_tracks  # Reuse subtitle rename workflow.


def main() -> None:
    """
    Run embedded subtitle-track metadata renaming from subtitles_report.json.

    :return: None.
    """

    rename_subtitle_tracks()  # Rename subtitle tracks using default configuration.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute default subtitle rename workflow.
