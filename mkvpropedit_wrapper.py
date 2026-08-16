"""
Isolated mkvpropedit interface for audio-track name metadata edits.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from dataclasses import dataclass  # Define typed records.
import os  # Read platform-specific installation directories.
from pathlib import Path  # Represent media file paths.
import shutil  # Locate external executables.
import subprocess  # Run mkvpropedit safely with argument lists.


@dataclass(frozen=True)
class AudioTrackRename:
    """
    Stores one intended audio-track rename operation.
    """

    audio_position: int  # Store zero-based audio stream position.
    current_name: str  # Store current track name before editing.
    new_name: str  # Store target track name.
    track_uid: int | None = None  # Store Matroska track UID when available.


@dataclass(frozen=True)
class MkvpropeditResult:
    """
    Stores one mkvpropedit execution result.
    """

    file_path: Path  # Store edited file path.
    command: list[str]  # Store executed command arguments.
    returncode: int  # Store process return code.
    stdout: str  # Store captured standard output.
    stderr: str  # Store captured standard error.
    changed_count: int  # Store number of requested changes.
    success: bool  # Store whether mkvpropedit succeeded.
    warning: bool = False  # Store whether mkvpropedit completed with warnings.


def find_executable(command_name: str) -> str | None:
    """
    Find an executable on PATH.

    :param command_name: Executable name.
    :return: Executable path or None.
    """

    path_result = shutil.which(command_name)  # Search PATH first.
    if path_result is not None:  # Verify PATH lookup found an executable.
        return path_result  # Return PATH executable.

    if os.name == "nt" and command_name.lower() in {"mkvpropedit", "mkvmerge", "mkvinfo", "mkvextract"}:  # Verify MKVToolNix command on Windows.
        executable_name = f"{command_name}.exe"  # Build Windows executable name.
        program_dirs = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]  # Read standard install roots.
        for program_dir in program_dirs:  # Iterate standard install roots.
            if not program_dir:  # Verify install root exists.
                continue  # Skip missing install root.
            candidate = Path(program_dir) / "MKVToolNix" / executable_name  # Build MKVToolNix executable path.
            if candidate.exists():  # Verify executable exists.
                return str(candidate)  # Return discovered executable.

    return None  # Return missing executable.


def valid_target_name(value: str) -> str:
    """
    Normalize a requested track name for mkvpropedit.

    :param value: Raw requested track name.
    :return: Stripped target track name.
    """

    return value.strip()  # Return stripped metadata name.


def build_mkvpropedit_arguments(file_path: Path, renames: list[AudioTrackRename], executable: str = "mkvpropedit") -> list[str]:
    """
    Build a safe mkvpropedit argument list for audio-track names only.

    :param file_path: Matroska file path.
    :param renames: Track rename operations.
    :param executable: mkvpropedit executable path or command name.
    :return: mkvpropedit command arguments.
    """

    command = [executable, str(file_path)]  # Start mkvpropedit command.
    for rename in renames:  # Iterate requested renames.
        target_name = valid_target_name(rename.new_name)  # Normalize target name.
        if rename.audio_position < 0 or target_name == "" or target_name == rename.current_name:  # Verify this operation should be skipped.
            continue  # Skip invalid or unnecessary operation.
        track_selector = f"track:={rename.track_uid}" if rename.track_uid is not None else f"track:a{rename.audio_position + 1}"  # Prefer Matroska track UID selector when available.
        command.extend(["--edit", track_selector, "--set", f"name={target_name}"])  # Add name-only track edit.
    return command  # Return complete argument list.


def command_sets_only_track_names(command: list[str]) -> bool:
    """
    Verify a generated mkvpropedit command edits only track-name metadata.

    :param command: Generated command arguments.
    :return: True when command contains only file, edit selectors, and name setters.
    """

    if len(command) < 2:  # Verify command has executable and file path.
        return False  # Return invalid command result.

    index = 2  # Start after executable and file path.
    while index < len(command):  # Iterate edit argument groups.
        if index + 3 >= len(command):  # Verify complete edit group exists.
            return False  # Return invalid command result.
        if command[index] != "--edit":  # Verify edit flag.
            return False  # Return invalid command result.
        track_selector = command[index + 1]  # Read track selector.
        if track_selector.startswith("track:a") and not track_selector[7:].isdigit():  # Verify audio ordinal selector.
            return False  # Return invalid command result.
        if track_selector.startswith("track:=") and not track_selector[7:].isdigit():  # Verify Track UID selector.
            return False  # Return invalid command result.
        if not (track_selector.startswith("track:a") or track_selector.startswith("track:=")):  # Verify track selector prefix.
            return False  # Return invalid command result.
        if command[index + 2] != "--set":  # Verify property setter flag.
            return False  # Return invalid command result.
        if not command[index + 3].startswith("name="):  # Verify only track name is set.
            return False  # Return invalid command result.
        index += 4  # Advance to next edit group.

    return True  # Return valid name-only command result.


def apply_audio_track_renames(file_path: Path, renames: list[AudioTrackRename]) -> MkvpropeditResult:
    """
    Apply audio-track name edits through mkvpropedit.

    :param file_path: Matroska file path.
    :param renames: Track rename operations.
    :return: mkvpropedit execution result.
    """

    executable = find_executable("mkvpropedit")  # Locate mkvpropedit executable.
    if executable is None:  # Verify mkvpropedit is available.
        return MkvpropeditResult(file_path, ["mkvpropedit", str(file_path)], 127, "", "mkvpropedit not found", 0, False, False)  # Return missing-tool failure.

    command = build_mkvpropedit_arguments(file_path, renames, executable)  # Build safe argument list.
    changed_count = (len(command) - 2) // 4 if len(command) > 2 else 0  # Count edit groups.
    if changed_count == 0:  # Verify any actual edit remains.
        return MkvpropeditResult(file_path, command, 0, "", "no track-name edits needed", 0, True, False)  # Return no-op success.
    if not command_sets_only_track_names(command):  # Verify generated command scope.
        return MkvpropeditResult(file_path, command, 2, "", "unsafe mkvpropedit command rejected", 0, False, False)  # Return rejected-command failure.

    try:  # Execute mkvpropedit.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run command safely.
    except OSError as error:  # Handle execution failure.
        return MkvpropeditResult(file_path, command, 126, "", str(error), changed_count, False, False)  # Return execution failure.

    warning = result.returncode == 1  # Resolve MKVToolNix warning exit status.
    success = result.returncode in {0, 1}  # Resolve completion status from MKVToolNix exit codes.
    return MkvpropeditResult(file_path, command, result.returncode, result.stdout or "", result.stderr or "", changed_count, success, warning)  # Return command result.
