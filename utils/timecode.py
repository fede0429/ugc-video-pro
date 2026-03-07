"""
utils/timecode.py
=================
Timecode utilities for subtitle and timeline operations.
"""

from __future__ import annotations


def seconds_to_srt_timestamp(seconds: float) -> str:
    """
    Convert a float seconds value to an SRT timestamp string.

    Example:
        >>> seconds_to_srt_timestamp(63.5)
        '00:01:03,500'
    """
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))

    # Handle millisecond rounding overflow
    if millis >= 1000:
        millis -= 1000
        secs += 1
    if secs >= 60:
        secs -= 60
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def seconds_to_vtt_timestamp(seconds: float) -> str:
    """
    Convert seconds to WebVTT timestamp format.

    Example:
        >>> seconds_to_vtt_timestamp(63.5)
        '00:01:03.500'
    """
    srt = seconds_to_srt_timestamp(seconds)
    return srt.replace(",", ".")


def srt_timestamp_to_seconds(ts: str) -> float:
    """
    Parse an SRT timestamp string to float seconds.

    Example:
        >>> srt_timestamp_to_seconds('00:01:03,500')
        63.5
    """
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid SRT timestamp: {ts!r}")
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s
