"""
================================================================================
Cross-Process File Lock
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-20
Description :
    Provides small standard-library cross-process file locks for shared runtime
    resources. Locks are held by open file handles and released by the operating
    system when the owning process exits.

    Key features include:
        - Cross-platform exclusive lock acquisition
        - Handle-owned release without deleting lock files
        - Crash-safe release through operating-system handle cleanup
        - Diagnostic owner text stored after acquisition

Usage:
    1. Build a deterministic lock path for the shared resource.
    2. Acquire the lock before mutating the shared resource.
    3. Release the returned handle in a finally block.

Outputs:
    - Persistent diagnostic lock files containing the last acquired owner text

TODOs:
    - None.

Dependencies:
    - Python >= 3.8

Assumptions & Notes:
    - Lock files are coordination artifacts and are not deleted on release.
    - Windows locks are retried because msvcrt exposes non-blocking byte locks.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from dataclasses import dataclass  # Define the lock handle record.
import os  # Select platform-specific lock behavior.
from pathlib import Path  # Represent lock paths.
import time  # Wait briefly between Windows lock acquisition attempts.
from typing import TextIO  # Type open text streams.


LOCK_BYTE_COUNT = 1  # Lock one byte consistently on every supported platform.
LOCK_RETRY_SECONDS = 0.1  # Retry interval for non-blocking Windows byte locks.


@dataclass(frozen=True)
class FileLock:
    """
    Stores one acquired cross-process file lock.
    """

    path: Path  # Store lock file path.
    stream: TextIO  # Store open stream that owns the operating-system lock.


def prepare_lock_stream(stream: TextIO) -> None:
    """
    Prepare a lock file stream for one-byte locking.

    :param stream: Open lock file stream.
    :return: None.
    """

    stream.seek(0)  # Return to the locked byte position.


def lock_stream(stream: TextIO) -> None:
    """
    Acquire an exclusive operating-system lock for one stream.

    :param stream: Prepared lock file stream.
    :return: None.
    """

    if os.name == "nt":  # Use Windows byte-range locking when running on Windows.
        import msvcrt  # Import Windows lock support only on Windows.
        while True:  # Wait until the byte lock becomes available.
            try:  # Attempt non-blocking byte lock acquisition.
                stream.seek(0)  # Position at the byte selected for locking.
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, LOCK_BYTE_COUNT)  # Acquire one-byte exclusive lock.
                return  # Return after acquiring the lock.
            except OSError:  # Handle another process owning the byte lock.
                time.sleep(LOCK_RETRY_SECONDS)  # Wait briefly before retrying.

    import fcntl  # Import POSIX lock support only on POSIX platforms.
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)  # Acquire a blocking exclusive file lock.


def unlock_stream(stream: TextIO) -> None:
    """
    Release an operating-system lock for one stream.

    :param stream: Locked stream.
    :return: None.
    """

    if os.name == "nt":  # Use Windows byte-range unlocking when running on Windows.
        import msvcrt  # Import Windows lock support only on Windows.
        stream.seek(0)  # Position at the byte selected for locking.
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, LOCK_BYTE_COUNT)  # Release one-byte exclusive lock.
        return  # Return after releasing the Windows lock.

    import fcntl  # Import POSIX lock support only on POSIX platforms.
    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)  # Release POSIX file lock.


def acquire_file_lock(lock_path: Path, owner_text: str) -> FileLock:
    """
    Acquire one exclusive file lock and return its owner handle.

    :param lock_path: Lock file path.
    :param owner_text: Diagnostic owner text to store after acquisition.
    :return: Acquired file lock handle.
    """

    lock_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the lock directory exists.
    stream = lock_path.open("a+", encoding="utf-8")  # Open or create the coordination file.
    try:  # Acquire the operating-system lock before writing owner data.
        prepare_lock_stream(stream)  # Ensure the file can be byte locked.
        lock_stream(stream)  # Acquire exclusive ownership.
        stream.seek(0)  # Move to the start before rewriting diagnostics.
        stream.truncate(0)  # Remove previous diagnostic content while owning the lock.
        stream.write(f"{owner_text.rstrip()}\n")  # Write current owner diagnostics.
        stream.flush()  # Flush owner diagnostics for observability.
        return FileLock(lock_path, stream)  # Return handle-owned lock.
    except Exception:  # Close the stream if acquisition or diagnostic writing fails.
        stream.close()  # Close the stream to release any partial operating-system state.
        raise  # Propagate acquisition failure.


def release_file_lock(file_lock: FileLock) -> None:
    """
    Release one acquired file lock handle.

    :param file_lock: Acquired file lock handle.
    :return: None.
    """

    try:  # Release the operating-system lock owned by this handle.
        unlock_stream(file_lock.stream)  # Release exclusive ownership.
    except OSError:  # Ignore release attempts for handles that do not own a lock.
        pass  # Keep release idempotent for cleanup paths.
    finally:  # Always close the stream after release.
        file_lock.stream.close()  # Close the owning stream.
