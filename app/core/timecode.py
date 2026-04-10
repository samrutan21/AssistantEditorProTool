"""Frame ↔ SMPTE timecode (non-drop assumed; extend for 29.97 DF if needed)."""

from __future__ import annotations

import re

_TC_RE = re.compile(
    r"(\d{1,2})[;:](\d{2})[;:](\d{2})[;:](\d{2})"
)


def frames_to_smpte(frame_count: int, fps: float) -> str:
    """Convert a frame index to HH:MM:SS:FF at the given nominal fps."""
    if fps <= 0:
        fps = 23.976
    fps_int = max(1, int(round(fps)))
    total = max(0, frame_count)
    ff = total % fps_int
    total //= fps_int
    ss = total % 60
    total //= 60
    mm = total % 60
    hh = total // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def smpte_to_frames(tc: str, fps: float) -> int:
    """Parse ``HH:MM:SS:FF`` (or semicolon-separated DF) into a frame count."""
    m = _TC_RE.match(tc.strip())
    if not m:
        return 0
    hh, mm, ss, ff = (int(g) for g in m.groups())
    fps_int = max(1, int(round(fps)))
    return ((hh * 3600 + mm * 60 + ss) * fps_int) + ff
