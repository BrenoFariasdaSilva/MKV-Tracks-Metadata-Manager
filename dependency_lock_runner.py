"""
================================================================================
Dependency Lock Runner
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-20
Description :
    Runs shared dependency setup commands behind a repository-local lock so
    concurrent Makefile targets do not create or mutate the same virtual
    environment at the same time.

    Key features include:
        - Atomic cross-process locking with standard library only
        - Optional skip path for virtual environment creation
        - Crash-safe release through operating-system handle cleanup
        - Direct subprocess execution without shell interpolation

Usage:
    1. Invoke from Makefile before commands that mutate the shared venv.
    2. Pass an optional skip path before the command separator.
        $ python dependency_lock_runner.py --skip-existing venv/bin/python -- python -m venv venv
    3. Pass the command after `--`.

Outputs:
    - The wrapped command output
    - A matching process exit status

TODOs:
    - None.

Dependencies:
    - Python >= 3.8

Assumptions & Notes:
    - The command after `--` is already tokenized by Make.
    - The lock only protects dependency setup, not media processing.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import os  # Read process id for diagnostic lock ownership.
from pathlib import Path  # Represent lock and skip paths.
import subprocess  # Run wrapped setup commands without shell interpolation.
import sys  # Read CLI arguments and return wrapped status.

from file_lock import FileLock, acquire_file_lock, release_file_lock  # Reuse handle-owned cross-process locks.


LOCK_DIR = Path(__file__).with_name(".make_locks")  # Store repository-local Makefile lock files.
DEPENDENCY_LOCK_NAME = "dependencies.lock"  # Store the shared dependency lock filename.


def build_dependency_lock_path() -> Path:
    """
    Build the repository-local dependency lock path.

    :return: Dependency lock path.
    """

    return LOCK_DIR / DEPENDENCY_LOCK_NAME  # Return the single dependency setup lock path.


def acquire_dependency_lock() -> FileLock:
    """
    Acquire the shared dependency setup lock.

    :return: Acquired dependency lock handle.
    """

    lock_path = build_dependency_lock_path()  # Build dependency lock path.
    lock_payload = f"pid={os.getpid()}\n"  # Build diagnostic lock payload.
    return acquire_file_lock(lock_path, lock_payload)  # Return handle-owned dependency lock.


def release_dependency_lock(file_lock: FileLock) -> None:
    """
    Release the shared dependency setup lock.

    :param file_lock: Acquired dependency lock handle.
    :return: None.
    """

    release_file_lock(file_lock)  # Release handle-owned dependency lock.


def parse_locked_command(arguments: list[str]) -> tuple[Path | None, list[str]]:
    """
    Parse optional skip path and wrapped command arguments.

    :param arguments: Raw CLI arguments.
    :return: Optional skip path and wrapped command.
    """

    skip_path: Path | None = None  # Store optional skip path.
    remaining_arguments = list(arguments)  # Copy argument values for parsing.
    if len(remaining_arguments) >= 2 and remaining_arguments[0] == "--skip-existing":  # Verify optional skip path syntax.
        skip_path = Path(remaining_arguments[1])  # Store skip path.
        remaining_arguments = remaining_arguments[2:]  # Remove skip option from command arguments.
    if remaining_arguments and remaining_arguments[0] == "--":  # Verify explicit command separator.
        remaining_arguments = remaining_arguments[1:]  # Remove command separator.
    return skip_path, remaining_arguments  # Return parsed skip path and command.


def run_locked_command(skip_path: Path | None, command: list[str]) -> int:
    """
    Run one command while holding the dependency setup lock.

    :param skip_path: Optional path that skips the command when present.
    :param command: Command arguments to execute.
    :return: Wrapped command exit status.
    """

    if not command:  # Verify a wrapped command was provided.
        print("No dependency command provided.")  # Report invalid invocation.
        return 2  # Return usage failure.
    lock_handle = acquire_dependency_lock()  # Acquire shared dependency lock.
    try:  # Run command while setup lock is held.
        if skip_path is not None and skip_path.exists():  # Verify another process already created the requested path.
            return 0  # Return success without repeating setup.
        result = subprocess.run(command, check=False)  # Run wrapped command without shell interpolation.
        return int(result.returncode)  # Return wrapped command status.
    finally:  # Ensure dependency lock release.
        release_dependency_lock(lock_handle)  # Release shared dependency lock.


def main() -> None:
    """
    Run the dependency setup command from CLI arguments.

    :return: None.
    """

    skip_path, command = parse_locked_command(sys.argv[1:])  # Parse CLI wrapper arguments.
    status = run_locked_command(skip_path, command)  # Run command under dependency lock.
    sys.exit(status)  # Return wrapped command status.


if __name__ == "__main__":  # Run script entry point when executed directly.
    main()  # Execute dependency lock runner.
