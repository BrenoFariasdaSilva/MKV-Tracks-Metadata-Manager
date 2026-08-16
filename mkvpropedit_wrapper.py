"""
Isolated mkvpropedit interface for safe track metadata edits.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from dataclasses import dataclass  # Define typed records.
import os  # Read platform-specific installation directories.
from pathlib import Path  # Represent media file paths.
import shutil  # Locate external executables.
import subprocess  # Run mkvpropedit safely with argument lists.


@dataclass(frozen=True)
class TrackMetadataEdit:
    """
    Stores one intended track metadata edit operation.
    """

    track_selector: str  # Store mkvpropedit track selector.
    current_name: str  # Store current track name before editing.
    new_name: str | None = None  # Store target track name when selected.
    default_flag: bool | None = None  # Store target default flag when selected.


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


def build_track_selector(track_type: str, track_position: int, track_uid: int | None) -> str:
    """
    Build a mkvpropedit selector for one target track.

    :param track_type: MKVToolNix selector type letter.
    :param track_position: Zero-based type-specific track position.
    :param track_uid: Matroska track UID when available.
    :return: mkvpropedit track selector.
    """

    if track_uid is not None:  # Verify whether a stable Matroska Track UID is available.
        return f"track:={track_uid}"  # Return UID selector.
    return f"track:{track_type}{track_position + 1}"  # Return type ordinal selector.


def valid_track_selector(track_selector: str) -> bool:
    """
    Verify whether a track selector is limited to supported target tracks.

    :param track_selector: mkvpropedit track selector.
    :return: True when selector is supported.
    """

    if track_selector.startswith("track:="):  # Verify UID selector prefix.
        return track_selector[7:].isdigit()  # Return UID numeric validation.
    if track_selector.startswith("track:a"):  # Verify audio ordinal selector prefix.
        return track_selector[7:].isdigit()  # Return audio ordinal numeric validation.
    if track_selector.startswith("track:v"):  # Verify video ordinal selector prefix.
        return track_selector[7:].isdigit()  # Return video ordinal numeric validation.
    if track_selector.startswith("track:s"):  # Verify subtitle ordinal selector prefix.
        return track_selector[7:].isdigit()  # Return subtitle ordinal numeric validation.
    return False  # Return unsupported selector result.


def merge_track_metadata_edits(edits: list[TrackMetadataEdit]) -> list[TrackMetadataEdit]:
    """
    Merge compatible edits for the same track selector.

    :param edits: Track metadata edit operations.
    :return: Merged track metadata edit operations.
    """

    merged_edits: dict[str, TrackMetadataEdit] = {}  # Store merged operations by track selector.
    for edit in edits:  # Iterate requested edits.
        existing_edit = merged_edits.get(edit.track_selector)  # Read existing selector operation.
        if existing_edit is None:  # Verify selector has no operation yet.
            merged_edits[edit.track_selector] = edit  # Store first operation for selector.
            continue  # Continue to next operation.

        new_name = edit.new_name if edit.new_name is not None else existing_edit.new_name  # Prefer latest explicit name.
        default_flag = edit.default_flag if edit.default_flag is not None else existing_edit.default_flag  # Prefer latest explicit default flag.
        merged_edits[edit.track_selector] = TrackMetadataEdit(edit.track_selector, existing_edit.current_name, new_name, default_flag)  # Store merged selector operation.

    return list(merged_edits.values())  # Return merged operations in insertion order.


def append_name_setter(command: list[str], edit: TrackMetadataEdit) -> int:
    """
    Append one safe track-name setter when needed.

    :param command: Mutable mkvpropedit command arguments.
    :param edit: Track metadata edit operation.
    :return: Number of appended setters.
    """

    target_name = valid_target_name(edit.new_name or "")  # Normalize target name.
    if target_name == "" or target_name == edit.current_name:  # Verify name setter is necessary.
        return 0  # Return no appended setter.
    command.extend(["--set", f"name={target_name}"])  # Add name setter.
    return 1  # Return appended setter count.


def append_default_flag_setter(command: list[str], edit: TrackMetadataEdit) -> int:
    """
    Append one safe audio default-flag setter when needed.

    :param command: Mutable mkvpropedit command arguments.
    :param edit: Track metadata edit operation.
    :return: Number of appended setters.
    """

    if edit.default_flag is None:  # Verify default flag setter was requested.
        return 0  # Return no appended setter.
    flag_value = "1" if edit.default_flag else "0"  # Convert boolean flag to mkvpropedit value.
    command.extend(["--set", f"flag-default={flag_value}"])  # Add default-flag setter.
    return 1  # Return appended setter count.


def build_mkvpropedit_arguments(file_path: Path, edits: list[TrackMetadataEdit], executable: str = "mkvpropedit") -> list[str]:
    """
    Build a safe mkvpropedit argument list for permitted track metadata.

    :param file_path: Matroska file path.
    :param edits: Track metadata edit operations.
    :param executable: mkvpropedit executable path or command name.
    :return: mkvpropedit command arguments.
    """

    command = [executable, str(file_path)]  # Start mkvpropedit command.
    for edit in merge_track_metadata_edits(edits):  # Iterate merged requested edits.
        if not valid_track_selector(edit.track_selector):  # Verify selector is safe.
            continue  # Skip invalid or unnecessary operation.
        edit_group = ["--edit", edit.track_selector]  # Start one track edit group.
        setter_count = append_name_setter(edit_group, edit)  # Add name setter when needed.
        setter_count += append_default_flag_setter(edit_group, edit)  # Add default-flag setter when needed.
        if setter_count == 0:  # Verify group has at least one setter.
            continue  # Skip no-op edit group.
        command.extend(edit_group)  # Add complete track edit group.
    return command  # Return complete argument list.


def valid_setter_argument(track_selector: str, setter_value: str) -> bool:
    """
    Verify whether one setter argument is explicitly permitted.

    :param track_selector: mkvpropedit track selector.
    :param setter_value: mkvpropedit setter value.
    :return: True when setter is permitted.
    """

    if setter_value.startswith("name="):  # Verify track-name setter.
        return True  # Accept track-name setter.
    if setter_value in {"flag-default=0", "flag-default=1"} and (track_selector.startswith("track:a") or track_selector.startswith("track:=")):  # Verify audio default flag setter.
        return True  # Accept default flag setter.
    return False  # Reject every other property.


def command_sets_only_permitted_track_metadata(command: list[str]) -> bool:
    """
    Verify a generated mkvpropedit command edits only permitted track metadata.

    :param command: Generated command arguments.
    :return: True when command contains only file, edit selectors, and permitted setters.
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
        if not valid_track_selector(track_selector):  # Verify supported track selector.
            return False  # Return invalid command result.
        index += 2  # Advance to first setter in this edit group.
        setter_count = 0  # Count setters for this edit group.
        while index < len(command) and command[index] == "--set":  # Iterate setters for current track.
            if index + 1 >= len(command):  # Verify setter value exists.
                return False  # Return invalid command result.
            if not valid_setter_argument(track_selector, command[index + 1]):  # Verify setter property is permitted.
                return False  # Return invalid command result.
            setter_count += 1  # Count accepted setter.
            index += 2  # Advance to next argument.
        if setter_count == 0:  # Verify edit group changed something.
            return False  # Return invalid command result.

    return True  # Return valid permitted-command result.


def count_requested_setters(command: list[str]) -> int:
    """
    Count requested setter operations in one mkvpropedit command.

    :param command: Generated command arguments.
    :return: Number of setter operations.
    """

    return sum(1 for argument in command if argument == "--set")  # Count explicit setter flags.


def apply_track_metadata_edits(file_path: Path, edits: list[TrackMetadataEdit]) -> MkvpropeditResult:
    """
    Apply permitted track metadata edits through mkvpropedit.

    :param file_path: Matroska file path.
    :param edits: Track metadata edit operations.
    :return: mkvpropedit execution result.
    """

    executable = find_executable("mkvpropedit")  # Locate mkvpropedit executable.
    if executable is None:  # Verify mkvpropedit is available.
        return MkvpropeditResult(file_path, ["mkvpropedit", str(file_path)], 127, "", "mkvpropedit not found", 0, False, False)  # Return missing-tool failure.

    command = build_mkvpropedit_arguments(file_path, edits, executable)  # Build safe argument list.
    changed_count = count_requested_setters(command)  # Count requested metadata setters.
    if changed_count == 0:  # Verify any actual edit remains.
        return MkvpropeditResult(file_path, command, 0, "", "no track metadata edits needed", 0, True, False)  # Return no-op success.
    if not command_sets_only_permitted_track_metadata(command):  # Verify generated command scope.
        return MkvpropeditResult(file_path, command, 2, "", "unsafe mkvpropedit command rejected", 0, False, False)  # Return rejected-command failure.

    try:  # Execute mkvpropedit.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run command safely.
    except OSError as error:  # Handle execution failure.
        return MkvpropeditResult(file_path, command, 126, "", str(error), changed_count, False, False)  # Return execution failure.

    warning = result.returncode == 1  # Resolve MKVToolNix warning exit status.
    success = result.returncode in {0, 1}  # Resolve completion status from MKVToolNix exit codes.
    return MkvpropeditResult(file_path, command, result.returncode, result.stdout or "", result.stderr or "", changed_count, success, warning)  # Return command result.
