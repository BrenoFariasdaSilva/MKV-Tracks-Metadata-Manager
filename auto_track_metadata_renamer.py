"""
Run automatic MKV track metadata-name detection and renaming.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from track_metadata_renamer import rename_detected_track_metadata  # Reuse automatic integrated workflow.


def main() -> None:
    """
    Run automatic video, audio, and embedded subtitle track-name renaming.

    :return: None.
    """

    rename_detected_track_metadata()  # Run default automatic workflow.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute automatic workflow.
