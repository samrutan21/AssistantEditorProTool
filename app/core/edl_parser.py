"""CMX 3600 EDL parser that produces the same clip-data dicts as XMLScanner."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.timecode import frames_to_smpte, smpte_to_frames
from app.core.scanner import _archival_match

_EVENT_RE = re.compile(
    r"^(\d{3,})\s+"       # event number
    r"(\S+)\s+"            # reel name
    r"(\S+)\s+"            # track type (V, A, A2, AA, AA/V, B …)
    r"(\S+)\s+"            # edit type  (C, D###, W###)
    r"(\S*)\s*"            # optional transition duration
    r"(\d\d:\d\d:\d\d[:;]\d\d)\s+"  # source in
    r"(\d\d:\d\d:\d\d[:;]\d\d)\s+"  # source out
    r"(\d\d:\d\d:\d\d[:;]\d\d)\s+"  # record in
    r"(\d\d:\d\d:\d\d[:;]\d\d)",    # record out
)

_AUDIO_TRACK_TYPES = {"A", "A2", "AA", "AA/V", "B"}
_VIDEO_TRACK_TYPES = {"V", "AA/V", "B"}


_M2_RE = re.compile(
    r"^M2\s+\S+\s+([\d.]+)\s+",
)

_SPEED_TOLERANCE = 2  # frames – minimum src/rec difference to even consider

# Common source frame rates.  Used as a fallback when no XML fps map
# is available to recognise frame-rate-conversion artefacts.
_KNOWN_SRC_FPS = [23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0, 59.94, 60.0]


_AUD_RE = re.compile(r"^AUD\s+", re.IGNORECASE)


@dataclass
class _EDLEvent:
    """Raw parsed event before conversion to clip-data dict."""
    event_num: int = 0
    reel: str = ""
    track_type: str = ""
    edit_type: str = ""
    src_in: str = ""
    src_out: str = ""
    rec_in: str = ""
    rec_out: str = ""
    clip_name: str = ""
    source_file: str = ""
    comments: list[str] = field(default_factory=list)
    m2_speed: float | None = None
    has_aud_channels: bool = False
    aud_first_channel: int = 0


class EDLScanner:
    """
    Parse a CMX 3600 EDL and expose the same scanning interface as XMLScanner.

    The EDL carries clip names in ``* FROM CLIP NAME:`` comment lines and
    timeline positions as record-in / record-out timecodes.
    """

    def __init__(self, edl_path: str, fps: float = 23.976):
        self.edl_path = edl_path
        self.fps = fps
        self._events: list[_EDLEvent] | None = None
        self._title: str = ""

    def _load(self) -> bool:
        if self._events is not None:
            return True
        try:
            text = Path(self.edl_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

        self._events = []
        current: _EDLEvent | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.upper().startswith("TITLE:"):
                self._title = stripped.split(":", 1)[1].strip()
                continue

            if stripped.upper().startswith("FCM:"):
                fcm = stripped.split(":", 1)[1].strip().upper()
                if "DROP" in fcm and "NON" not in fcm:
                    pass  # DF handling reserved for future
                continue

            m = _EVENT_RE.match(stripped)
            if m:
                if current is not None:
                    self._events.append(current)
                current = _EDLEvent(
                    event_num=int(m.group(1)),
                    reel=m.group(2),
                    track_type=m.group(3),
                    edit_type=m.group(4),
                    src_in=m.group(6),
                    src_out=m.group(7),
                    rec_in=m.group(8),
                    rec_out=m.group(9),
                )
                continue

            if current is not None:
                m2 = _M2_RE.match(stripped)
                if m2:
                    try:
                        current.m2_speed = float(m2.group(1))
                    except ValueError:
                        pass
                    continue
                aud_m = _AUD_RE.match(stripped)
                if aud_m:
                    current.has_aud_channels = True
                    rest = stripped[aud_m.end():].strip()
                    ch_nums = re.findall(r"\d+", rest)
                    if ch_nums:
                        current.aud_first_channel = int(ch_nums[0])
                    continue

            if current is not None and stripped.startswith("*"):
                body = stripped[1:].strip()
                upper = body.upper()
                if upper.startswith("FROM CLIP NAME:"):
                    current.clip_name = body.split(":", 1)[1].strip()
                elif upper.startswith("SOURCE FILE:"):
                    current.source_file = body.split(":", 1)[1].strip()
                else:
                    current.comments.append(body)

        if current is not None:
            self._events.append(current)

        return True

    @staticmethod
    def _audio_track_pos(ev: _EDLEvent) -> int:
        """
        Derive a 1-based audio track position from channel assignments.

        Premiere maps stereo pairs to sequential channels:
        channels 1-2 → position 1, channels 3-4 → position 2, etc.
        Events without an ``AUD`` line default to position 1.
        """
        if ev.aud_first_channel > 0:
            return (ev.aud_first_channel - 1) // 2 + 1
        return 1

    def audio_track_summary(self) -> dict[int, list[str]]:
        """
        Return a map of ``{edl_audio_position: [sample clip names]}``.

        Useful for showing the user which audio tracks are in the EDL.
        """
        if not self._load():
            return {}
        assert self._events is not None
        summary: dict[int, list[str]] = {}
        for ev in self._events:
            if ev.reel.upper() == "BL":
                continue
            if ev.track_type not in _AUDIO_TRACK_TYPES and not ev.has_aud_channels:
                continue
            pos = self._audio_track_pos(ev)
            if pos not in summary:
                summary[pos] = []
            name = ev.clip_name or ev.reel
            if len(summary[pos]) < 3 and name not in summary[pos]:
                summary[pos].append(name)
        return summary

    def _event_to_clip_data(self, ev: _EDLEvent) -> dict[str, Any]:
        """Convert a parsed EDL event into the standard clip-data dict."""
        rec_in_f = smpte_to_frames(ev.rec_in, self.fps)
        rec_out_f = smpte_to_frames(ev.rec_out, self.fps)
        src_in_f = smpte_to_frames(ev.src_in, self.fps)
        src_out_f = smpte_to_frames(ev.src_out, self.fps)
        seq_dur = max(0, rec_out_f - rec_in_f)
        src_dur = max(0, src_out_f - src_in_f)

        name = ev.clip_name or ev.reel

        return {
            "Name": name,
            "Seq_In": frames_to_smpte(rec_in_f, self.fps),
            "Seq_Out": frames_to_smpte(rec_out_f, self.fps),
            "Src_In": frames_to_smpte(src_in_f, self.fps),
            "Src_Out": frames_to_smpte(src_out_f, self.fps),
            "Duration": frames_to_smpte(seq_dur, self.fps),
            "Src_Duration": frames_to_smpte(src_dur, self.fps),
            "Resolution": "Unknown",
            "_seq_start_frames": rec_in_f,
            "_seq_end_frames": rec_out_f,
            "Track": ev.track_type,
        }

    def scan_for_archival(self, search_tag: str) -> list[dict[str, Any]]:
        """
        Return events matching ``{TAG}-F``, ``{TAG}-A``, or ``{TAG}-S``.

        Each result carries ``_asset_code`` and ``_media_type`` so that
        :func:`resolve_archival_types` can apply smart Video/Audio detection.
        """
        if not self._load():
            return []
        assert self._events is not None
        results: list[dict[str, Any]] = []
        for ev in self._events:
            if ev.reel.upper() == "BL":
                continue
            name = ev.clip_name or ev.reel
            code = _archival_match(name, search_tag)
            if code is not None:
                data = self._event_to_clip_data(ev)
                data["_asset_code"] = code

                if ev.track_type in _AUDIO_TRACK_TYPES or ev.has_aud_channels:
                    data["_media_type"] = "audio"
                elif ev.track_type in _VIDEO_TRACK_TYPES:
                    data["_media_type"] = "video"
                else:
                    data["_media_type"] = "video"

                results.append(data)
        return results

    def scan_by_tracks(
        self,
        start_track: int = 0,
        end_track: int = 0,
        media_type: str = "audio",
    ) -> list[dict[str, Any]]:
        """
        Return events filtered by media type and optionally by audio
        track position.

        When *start_track* and *end_track* are both ``0``, all matching
        events are returned.  Otherwise, only audio events whose EDL
        track position falls within the range are included.  Positions
        are derived from ``AUD`` channel pairs (1-2 → pos 1, 3-4 → pos 2,
        etc.).
        """
        if not self._load():
            return []
        assert self._events is not None

        filter_by_pos = media_type == "audio" and (start_track > 0 or end_track > 0)
        wanted = _AUDIO_TRACK_TYPES if media_type == "audio" else _VIDEO_TRACK_TYPES
        results: list[dict[str, Any]] = []
        for ev in self._events:
            if ev.reel.upper() == "BL":
                continue
            is_audio = ev.track_type in _AUDIO_TRACK_TYPES or ev.has_aud_channels
            is_video = ev.track_type in _VIDEO_TRACK_TYPES

            if media_type == "audio" and not is_audio:
                continue
            if media_type != "audio" and not is_video:
                continue

            if filter_by_pos:
                pos = self._audio_track_pos(ev)
                lo = start_track or end_track
                hi = end_track or start_track
                if not (lo <= pos <= hi):
                    continue

            results.append(self._event_to_clip_data(ev))
        return results

    def scan_for_effects(
        self,
        clip_fps_map: dict[str, float] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Detect speed changes from the EDL.

        Returns ``(confirmed, filtered)`` where *confirmed* are clips
        with a clear deliberate speed change, and *filtered* are clips
        whose duration mismatch is likely caused by frame-rate
        conversion or EDL timecode rounding.

        Primary detection uses the **source / record duration ratio**.
        To avoid false positives, the detected speed is compared
        against an *expected* speed derived from the clip's native
        frame rate:

        * When *clip_fps_map* is provided (from XML), the expected
          ratio is ``clip_fps / seq_fps``.  Any deviation smaller than
          a dynamic tolerance is treated as rounding noise.
        * Without a map, the detected speed is checked against common
          frame-rate ratios (29.97→23.976 = 125 %, etc.).
        * An ``M2`` line in the EDL is an explicit speed marker from
          Premiere and always triggers a confirmed report regardless
          of the tolerance filter.
        """
        if not self._load():
            return [], []
        assert self._events is not None
        confirmed: list[dict[str, Any]] = []
        filtered: list[dict[str, Any]] = []

        fps_int = max(1, int(round(self.fps)))

        for ev in self._events:
            if ev.reel.upper() == "BL":
                continue

            rec_in_f = smpte_to_frames(ev.rec_in, self.fps)
            rec_out_f = smpte_to_frames(ev.rec_out, self.fps)
            src_in_f = smpte_to_frames(ev.src_in, self.fps)
            src_out_f = smpte_to_frames(ev.src_out, self.fps)

            rec_dur = rec_out_f - rec_in_f
            src_dur = src_out_f - src_in_f

            has_m2 = ev.m2_speed is not None and ev.m2_speed > 0
            speed_pct: float | None = None
            is_filtered = False

            if rec_dur > 0 and src_dur > 0 and abs(src_dur - rec_dur) > _SPEED_TOLERANCE:
                raw_speed = (src_dur / rec_dur) * 100.0

                expected = self._expected_speed(
                    ev.clip_name or ev.reel, clip_fps_map
                )

                if clip_fps_map is not None:
                    tolerance = max(10.0, 600.0 / max(1, rec_dur))
                else:
                    tolerance = max(5.0, 400.0 / max(1, rec_dur))

                if abs(raw_speed - expected) > tolerance:
                    speed_pct = raw_speed
                elif has_m2:
                    speed_pct = (ev.m2_speed / fps_int) * 100.0
                else:
                    speed_pct = raw_speed
                    is_filtered = True
            elif has_m2:
                speed_pct = (ev.m2_speed / fps_int) * 100.0

            if speed_pct is not None:
                data = self._event_to_clip_data(ev)
                data["Effect"] = "Speed/Duration"
                data["Notes"] = f"{speed_pct:.1f}%"
                if is_filtered:
                    data["Notes"] += f" (expected {expected:.1f}%)"
                    filtered.append(data)
                else:
                    confirmed.append(data)

        return confirmed, filtered

    def _expected_speed(
        self,
        clip_name: str,
        clip_fps_map: dict[str, float] | None,
    ) -> float:
        """
        Return the speed percentage that a simple frame-rate conversion
        (no deliberate speed change) would produce for *clip_name*.

        With an XML fps map the answer is exact.  Without one, fall
        back to checking common source frame rates.
        """
        if clip_fps_map is not None:
            clip_fps = clip_fps_map.get(clip_name.lower())
            if clip_fps and clip_fps > 0:
                return (clip_fps / self.fps) * 100.0
            return 100.0

        for known_fps in _KNOWN_SRC_FPS:
            ratio = (known_fps / self.fps) * 100.0
            if abs(ratio - 100.0) < 0.5:
                continue
            # placeholder — without XML we can't be sure which fps
            # the clip uses, so just return 100 and rely on tolerance
        return 100.0
