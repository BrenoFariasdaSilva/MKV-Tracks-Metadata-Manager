from __future__ import annotations  # Enable modern annotations on supported Python versions.

import argparse  # Parse shared completion-sound CLI flags.
import atexit  # Register process-exit callbacks without import side effects.
import os  # Run platform sound commands with stable quoting.
from pathlib import Path  # Resolve repository-local sound asset paths.
import platform  # Detect current operating system for playback selection.

from utils.utils import BackgroundColors  # Reuse project terminal color constants.


SOUND_COMMANDS = {  # Store supported playback commands by operating system name.
    "Darwin": "afplay",  # Play WAV files on macOS.
    "Linux": "aplay",  # Play WAV files on Linux.
    "Windows": "start",  # Preserve template mapping even though playback is skipped on Windows.
}  # Keep command mapping aligned with main-template.py.
SOUND_FILE = Path(__file__).resolve().parent.parent / ".assets" / "Sounds" / "NotificationSound.wav"  # Resolve sound asset safely from repository root.
COMPLETION_SOUND_REGISTERED = False  # Prevent duplicate atexit registrations inside one process.


def add_completion_sound_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add shared completion-sound CLI flags.

    :param parser: Argument parser receiving shared sound flags.
    :return: None.
    """

    parser.add_argument("--enable-completion-sound", dest="completion_sound", action="store_true", default=None, help="Play the completion sound when this script exits.")  # Add explicit enable flag without changing standalone default behavior.
    parser.add_argument("--disable-completion-sound", dest="completion_sound", action="store_false", help="Skip the completion sound when this script exits.")  # Add explicit disable flag for intermediate Makefile stages.


def resolve_completion_sound_enabled(parsed_value: bool | None, default_enabled: bool = True) -> bool:
    """
    Resolve final completion-sound state from a parsed CLI value.

    :param parsed_value: Parsed CLI value or None when omitted.
    :param default_enabled: Fallback state when no CLI override exists.
    :return: Final completion-sound enabled state.
    """

    return default_enabled if parsed_value is None else bool(parsed_value)  # Return standalone default unless CLI explicitly overrides it.


def read_completion_sound_argument(arguments: list[str], default_enabled: bool = True) -> bool:
    """
    Read shared completion-sound flags from raw CLI arguments.

    :param arguments: Raw CLI argument values.
    :param default_enabled: Fallback state when no CLI override exists.
    :return: Final completion-sound enabled state.
    """

    completion_sound_enabled = default_enabled  # Start from standalone default behavior.
    for argument in arguments:  # Iterate CLI arguments in caller order.
        if argument == "--enable-completion-sound":  # Verify explicit enable override.
            completion_sound_enabled = True  # Enable completion sound for this process.
        elif argument == "--disable-completion-sound":  # Verify explicit disable override.
            completion_sound_enabled = False  # Disable completion sound for this process.
    return completion_sound_enabled  # Return final last-flag-wins completion-sound state.


def play_sound() -> None:
    """
    Play configured completion sound when platform supports it.

    :return: None.
    """

    current_os = platform.system()  # Detect current operating system name.
    if current_os == "Windows":  # Preserve template behavior that skips playback on Windows.
        return  # Leave Windows silent even though template keeps mapping entry.
    if not SOUND_FILE.is_file():  # Verify repository-local sound asset exists.
        print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{BackgroundColors.RESET_ALL}")  # Report missing sound asset with project color style.
        return  # Stop when asset is unavailable.
    if current_os not in SOUND_COMMANDS:  # Verify platform command mapping exists.
        print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{BackgroundColors.RESET_ALL}")  # Report unsupported platform with template-style wording.
        return  # Stop when platform is unsupported.
    os.system(f'{SOUND_COMMANDS[current_os]} "{SOUND_FILE}"')  # Run mapped sound command with quoted asset path.


def register_completion_sound(completion_sound_enabled: bool) -> None:
    """
    Register completion-sound playback once for current process.

    :param completion_sound_enabled: Whether current entrypoint owns completion playback.
    :return: None.
    """

    global COMPLETION_SOUND_REGISTERED  # Update process-local registration guard.
    if not completion_sound_enabled or COMPLETION_SOUND_REGISTERED:  # Verify registration is both enabled and still absent.
        return  # Skip disabled or duplicate registration attempts.
    atexit.register(play_sound)  # Register shared playback callback for normal interpreter exit.
    COMPLETION_SOUND_REGISTERED = True  # Mark process-local registration as complete.
