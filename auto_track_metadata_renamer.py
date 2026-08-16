"""
Run integrated MKV track metadata-name reporting and renaming.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import sys  # Return meaningful CLI exit statuses.

from track_metadata_renamer import run_process_cli  # Reuse integrated process CLI.


def main() -> None:
    """
    Run integrated selected track-name reporting and renaming.

    :return: None.
    """

    sys.exit(run_process_cli())  # Run process CLI and return status.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute automatic workflow.
