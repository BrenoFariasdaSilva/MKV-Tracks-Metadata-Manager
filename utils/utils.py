"""
================================================================================
Execution Timing Utilities
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-18
Description :
    Utility module providing execution timing functions and terminal formatting
    helpers for comprehensive program performance reporting. Converts various
    time representations to human-readable duration strings.

    Key features include:
        - Flexible time-to-seconds conversion (datetime, timedelta, numeric)
        - Human-readable execution time formatting (days, hours, minutes, seconds)
        - ANSI terminal color constants for consistent styling
        - ISO 639-2 language code normalization
        - Numeric millisecond to human-readable conversion

Usage:
    1. Import timing functions and call with start and finish datetimes
        from utils.utils import calculate_execution_time
        result = calculate_execution_time(start_time, finish_time)
    2. Use BackgroundColors class for consistent terminal output coloring
        from utils.utils import BackgroundColors
        print(f"{BackgroundColors.GREEN}Success{BackgroundColors.RESET_ALL}")
    3. Returns formatted strings suitable for terminal display

Outputs:
    - Human-readable execution time strings (e.g., "1h 2m 3s")
    - ANSI-formatted colored terminal output
    - Properly reset terminal colors after output

TODOs:
    - Add millisecond precision to timing output
    - Implement performance profiling decorators
    - Support for timer context managers
    - Add benchmark comparison utilities

Dependencies:
    - Python >= 3.8
    - datetime (standard library)

Assumptions & Notes:
    - Time inputs can be datetime, timedelta, or numeric (seconds)
    - Output format is fixed at largest unit (days, hours, minutes, seconds)
    - ANSI color codes may not work on all terminal emulators
    - Negative durations are automatically converted to positive (absolute value)
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

import datetime  # Handle datetime objects for timing.


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    RESET_ALL = "\033[0m"  # Reset all formatting


def to_seconds(obj):
    """
    Converts various time-like objects to seconds.
    
    :param obj: The object to convert (can be int, float, timedelta, datetime, etc.)
    :return: The equivalent time in seconds as a float, or None if conversion fails
    """
    
    if obj is None:  # None can't be converted
        return None  # Signal failure to convert
    if isinstance(obj, (int, float)):  # Already numeric (seconds or timestamp)
        return float(obj)  # Return as float seconds
    if hasattr(obj, "total_seconds"):  # Timedelta-like objects
        try:  # Attempt to call total_seconds()
            return float(obj.total_seconds())  # Use the total_seconds() method
        except Exception:
            pass  # Fallthrough on error
    if hasattr(obj, "timestamp"):  # Datetime-like objects
        try:  # Attempt to call timestamp()
            return float(obj.timestamp())  # Use timestamp() to get seconds since epoch
        except Exception:
            pass  # Fallthrough on error
    return None  # Couldn't convert


def calculate_execution_time(start_time, finish_time=None):
    """
    Calculates the execution time and returns a human-readable string.

    Accepts either:
    - Two datetimes/timedeltas: `calculate_execution_time(start, finish)`
    - A single timedelta or numeric seconds: `calculate_execution_time(delta)`
    - Two numeric timestamps (seconds): `calculate_execution_time(start_s, finish_s)`

    Returns a string like "1h 2m 3s".
    
    :param start_time: Start time as datetime, timedelta, or numeric seconds
    :param finish_time: Finish time as datetime, timedelta, or numeric seconds (optional)
    :return: Human-readable execution time string
    """

    if finish_time is None:  # Single-argument mode: start_time already represents duration or seconds
        total_seconds = to_seconds(start_time)  # Try to convert provided value to seconds
        if total_seconds is None:  # Conversion failed
            try:  # Attempt numeric coercion
                total_seconds = float(start_time)  # Attempt numeric coercion
            except Exception:
                total_seconds = 0.0  # Fallback to zero
    else:  # Two-argument mode: Compute difference finish_time - start_time
        st = to_seconds(start_time)  # Convert start to seconds if possible
        ft = to_seconds(finish_time)  # Convert finish to seconds if possible
        if st is not None and ft is not None:  # Both converted successfully
            total_seconds = ft - st  # Direct numeric subtraction
        else:  # Fallback to other methods
            try:  # Attempt to subtract (works for datetimes/timedeltas)
                delta = finish_time - start_time  # Try subtracting (works for datetimes/timedeltas)
                total_seconds = float(delta.total_seconds())  # Get seconds from the resulting timedelta
            except Exception:  # Subtraction failed
                try:  # Final attempt: Numeric coercion
                    total_seconds = float(finish_time) - float(start_time)  # Final numeric coercion attempt
                except Exception:  # Numeric coercion failed
                    total_seconds = 0.0  # Fallback to zero on failure

    if total_seconds is None:  # Ensure a numeric value
        total_seconds = 0.0  # Default to zero
    if total_seconds < 0:  # Normalize negative durations
        total_seconds = abs(total_seconds)  # Use absolute value

    days = int(total_seconds // 86400)  # Compute full days
    hours = int((total_seconds % 86400) // 3600)  # Compute remaining hours
    minutes = int((total_seconds % 3600) // 60)  # Compute remaining minutes
    seconds = int(total_seconds % 60)  # Compute remaining seconds

    if days > 0:  # Include days when present
        return f"{days}d {hours}h {minutes}m {seconds}s"  # Return formatted days+hours+minutes+seconds
    if hours > 0:  # Include hours when present
        return f"{hours}h {minutes}m {seconds}s"  # Return formatted hours+minutes+seconds
    if minutes > 0:  # Include minutes when present
        return f"{minutes}m {seconds}s"  # Return formatted minutes+seconds
    return f"{seconds}s"  # Fallback: only seconds
