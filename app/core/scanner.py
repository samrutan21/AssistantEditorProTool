"""Premiere/FCP-style XML scanning plus optional ElementTree helpers for tests."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.core.timecode import frames_to_smpte

_ASSET_LABELS = {"F": "Footage", "A": "Audio", "S": "Still"}


def _archival_match(name: str, project_tag: str) -> str | None:
    """
    Return the raw asset-code letter (``F``, ``A``, or ``S``) if *name*
    matches ``{TAG}-F…``, ``{TAG}-A…``, or ``{TAG}-S…``
    (case-insensitive).  Returns ``None`` on no match.
    """
    tag = re.escape(project_tag.strip())
    m = re.search(rf"(?i){tag}-([FAS])", name)
    if not m:
        return None
    return m.group(1).upper()


_MERGE_TOLERANCE = 48  # frames — ~2 sec at 24fps


def _frames_close(a: int, b: int) -> bool:
    return abs(a - b) <= _MERGE_TOLERANCE


def _dedup_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove stereo-pair / linked-clip duplicates.

    Two entries are duplicates if they share the same name, media type,
    and sequence start+end frames.
    """
    seen: set[tuple[str, str, int, int]] = set()
    out: list[dict[str, Any]] = []
    for c in clips:
        key = (
            c["Name"],
            c.get("_media_type", ""),
            c["_seq_start_frames"],
            c["_seq_end_frames"],
        )
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def resolve_archival_types(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Post-process archival clips to determine smart Asset_Type.

    1. **Deduplicates** stereo-pair / linked-clip copies (same name,
       media type, and timecodes).
    2. Assigns type:
       * ``-A`` assets → always **Audio**.
       * ``-S`` assets → always **Still**.
       * ``-F`` assets → paired by **name + matching timecodes**:
           - A video event and an audio event with the same name *and*
             overlapping sequence timecodes → **Video/Audio** (merged into
             one row using the video event's data).
           - Unpaired audio-only events → **Audio** (audio pulled from footage).
           - Unpaired video-only events → **Video**.

    Each cut of the same clip at a different timecode remains a separate
    row — only true duplicates and V+A pairs are collapsed.

    The ``_media_type`` key (``"audio"`` / ``"video"``) must be set on each
    clip by the scanner before calling this function.
    """
    from collections import defaultdict

    deduped = _dedup_clips(clips)

    code_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in deduped:
        code_map[c["Name"]].append(c)

    results: list[dict[str, Any]] = []

    for name, group in code_map.items():
        asset_code = group[0].get("_asset_code", "F")

        if asset_code == "A":
            for c in group:
                c["Asset_Type"] = "Audio"
            results.extend(group)
            continue

        if asset_code == "S":
            for c in group:
                c["Asset_Type"] = "Still"
            results.extend(group)
            continue

        video_clips = [c for c in group if c.get("_media_type") == "video"]
        audio_clips = [c for c in group if c.get("_media_type") == "audio"]

        paired_audio: set[int] = set()

        for vc in video_clips:
            v_start = vc["_seq_start_frames"]
            v_end = vc["_seq_end_frames"]
            matched = False
            for i, ac in enumerate(audio_clips):
                if i in paired_audio:
                    continue
                if _frames_close(v_start, ac["_seq_start_frames"]) and \
                   _frames_close(v_end, ac["_seq_end_frames"]):
                    paired_audio.add(i)
                    matched = True
                    break
            vc["Asset_Type"] = "Video/Audio" if matched else "Video"
            results.append(vc)

        for i, ac in enumerate(audio_clips):
            if i not in paired_audio:
                ac["Asset_Type"] = "Audio"
                results.append(ac)

    return results

PPRO_TICKS_PER_SECOND = 254016000000


@dataclass(frozen=True)
class ParseResult:
    root: ET.Element
    source_path: Path


def parse_xml_file(path: Path | str) -> ParseResult:
    p = Path(path)
    tree = ET.parse(p)
    return ParseResult(root=tree.getroot(), source_path=p.resolve())


def element_tag_local(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


class XMLScanner:
    def __init__(self, xml_path: str, fps: float = 23.976):
        self.xml_path = xml_path
        self.fps = fps
        self.soup: BeautifulSoup | None = None
        self._seq_offset_frames: int = 0

    def _load_xml(self) -> bool:
        try:
            with open(self.xml_path, encoding="utf-8") as f:
                self.soup = BeautifulSoup(f.read(), "xml")
            self._read_seq_offset()
            return True
        except OSError:
            return False

    def _read_seq_offset(self) -> None:
        """
        Compute the timeline start offset from the sequence's MZ.ZeroPoint.

        Premiere stores the timeline ruler's zero-point in ppro ticks.
        E.g. a standard 01:00:00:00 start at 23.976fps → 86208 frame offset.
        """
        assert self.soup is not None
        seq = self.soup.find("sequence")
        if not seq or not isinstance(seq, Tag):
            return

        zp_str = seq.get("MZ.ZeroPoint", "0")
        try:
            zero_ticks = int(zp_str)
        except (ValueError, TypeError):
            return
        if zero_ticks <= 0:
            return

        rate_el = seq.find("rate", recursive=False)
        timebase = 24
        ntsc = True
        if rate_el and isinstance(rate_el, Tag):
            tb = rate_el.find("timebase")
            if tb and tb.text:
                timebase = int(tb.text)
            ntsc_el = rate_el.find("ntsc")
            if ntsc_el and ntsc_el.text:
                ntsc = ntsc_el.text.strip().upper() == "TRUE"

        if ntsc:
            ticks_per_frame = PPRO_TICKS_PER_SECOND * 1001 // (timebase * 1000)
            self.fps = timebase * 1000.0 / 1001.0
        else:
            ticks_per_frame = PPRO_TICKS_PER_SECOND // timebase
            self.fps = float(timebase)

        if ticks_per_frame > 0:
            self._seq_offset_frames = zero_ticks // ticks_per_frame

    def _seq_media_container(self, media_type: str) -> Tag | None:
        """
        Return the sequence-level <video> or <audio> container,
        NOT a clip-level one buried inside <file><media>.
        """
        assert self.soup is not None
        seq = self.soup.find("sequence")
        if not seq or not isinstance(seq, Tag):
            return None
        media = seq.find("media", recursive=False)
        if not media or not isinstance(media, Tag):
            return None
        target = media.find(media_type, recursive=False)
        if not target or not isinstance(target, Tag):
            return None
        return target

    def scan_for_archival(self, search_tag: str) -> list[dict[str, Any]]:
        """
        Scan for archival clips matching ``{TAG}-F``, ``{TAG}-A``, or
        ``{TAG}-S`` naming convention.

        Each result carries ``_asset_code`` (``F``/``A``/``S``) and
        ``_media_type`` (``audio``/``video``) so that
        :func:`resolve_archival_types` can apply smart type detection.
        """
        if not self.soup and not self._load_xml():
            return []
        assert self.soup is not None
        results: list[dict[str, Any]] = []
        for clip in self.soup.find_all("clipitem"):
            if not isinstance(clip, Tag):
                continue
            name_el = clip.find("name")
            name = name_el.text if name_el and name_el.text else ""
            code = _archival_match(name, search_tag)
            if code is not None:
                data = self._extract_clip_data(clip)
                data["_asset_code"] = code

                st = clip.find("sourcetrack")
                mt_el = st.find("mediatype") if st else None
                data["_media_type"] = (
                    mt_el.text.strip().lower() if mt_el and mt_el.text else "video"
                )
                results.append(data)
        return results

    def scan_by_tracks(
        self, start_track: int, end_track: int, media_type: str = "audio"
    ) -> list[dict[str, Any]]:
        """
        Scan Premiere tracks by their *timeline* number (A1, A2, ...).

        Only collects clips from the primary stereo sub-track
        (currentExplodedTrackIndex="0") to avoid duplicates.

        Walks all direct children of the ``<track>`` in document order
        (``<clipitem>`` **and** ``<transitionitem>``).  ``<transitionitem>``
        elements carry the timeline position that bridges gaps between clips,
        so the ``<start>`` of the most-recent transition is used to resolve
        any ``<clipitem>`` whose own ``<start>`` is ``-1``.
        """
        if not self.soup and not self._load_xml():
            return []
        assert self.soup is not None
        results: list[dict[str, Any]] = []
        container = self._seq_media_container(media_type)
        if not container:
            return []

        premiere_track_num = 0
        for track in container.find_all("track"):
            if not isinstance(track, Tag):
                continue

            exploded_idx = track.get("currentExplodedTrackIndex")
            if exploded_idx is not None:
                if exploded_idx == "0":
                    premiere_track_num += 1
                else:
                    continue
            else:
                premiere_track_num += 1

            if start_track <= premiere_track_num <= end_track:
                cursor = 0
                last_trans_start: int | None = None

                for child in track.children:
                    if not isinstance(child, Tag):
                        continue

                    if child.name == "transitionitem":
                        s = child.find("start", recursive=False)
                        if s and s.text:
                            try:
                                last_trans_start = int(s.text)
                            except ValueError:
                                pass
                        continue

                    if child.name != "clipitem":
                        continue

                    raw_start = self._clip_start_raw(child)
                    if raw_start >= 0:
                        resolved = raw_start
                    elif last_trans_start is not None:
                        resolved = last_trans_start
                    else:
                        resolved = cursor

                    data = self._extract_clip_data(child, resolved)
                    cursor = data["_seq_end_frames"] - self._seq_offset_frames
                    data["Track"] = (
                        f"{media_type.capitalize()} {premiere_track_num}"
                    )
                    results.append(data)
        return results

    # Effect IDs that indicate real finishing-relevant effects
    _EFFECT_IDS: dict[str, str] = {
        "timeremap": "Speed Ramp",
    }

    # Effect IDs to silently ignore (defaults / non-finishing).
    # Note: Warp Stabilizer is NOT exported in simplified FCP XML, so
    # it cannot be detected from XML alone.  ``deformation`` (Distort)
    # is just Premiere's pixel-aspect-ratio correction.
    _IGNORE_IDS: set[str] = {
        "basic",           # Basic Motion — default on every clip
        "deformation",     # Distort / pixel aspect ratio — default
        "audiolevels",     # Audio Levels
        "opacity",         # Opacity
        "GraphicAndType",  # Title / lower third text
        "GraphicGroup",    # Vector Motion for graphics
        "Lumetri",         # Color correction
    }

    def scan_for_effects(self) -> list[dict[str, Any]]:
        """
        Walk all video tracks and report clips with finishing-relevant
        effects (speed ramps, warp stabilizer, etc.).

        Uses the same track-walking logic as :meth:`scan_by_tracks` so
        that sequence timecodes are correctly resolved.  Ignores
        Premiere defaults like Basic Motion, Audio Levels, and graphics.
        """
        if not self.soup and not self._load_xml():
            return []
        assert self.soup is not None
        results: list[dict[str, Any]] = []
        container = self._seq_media_container("video")
        if not container:
            return []

        for track in container.find_all("track"):
            if not isinstance(track, Tag):
                continue
            exploded_idx = track.get("currentExplodedTrackIndex")
            if exploded_idx is not None and exploded_idx != "0":
                continue

            cursor = 0
            last_trans_start: int | None = None

            for child in track.children:
                if not isinstance(child, Tag):
                    continue
                if child.name == "transitionitem":
                    s = child.find("start", recursive=False)
                    if s and s.text:
                        try:
                            last_trans_start = int(s.text)
                        except ValueError:
                            pass
                    continue
                if child.name != "clipitem":
                    continue

                raw_start = self._clip_start_raw(child)
                if raw_start >= 0:
                    resolved = raw_start
                elif last_trans_start is not None:
                    resolved = last_trans_start
                else:
                    resolved = cursor

                detected: list[str] = []
                speed_note = ""

                for flt in child.find_all("filter"):
                    eff = flt.find("effect")
                    if not eff or not isinstance(eff, Tag):
                        continue
                    eid_el = eff.find("effectid")
                    eid = eid_el.text.strip() if eid_el and eid_el.text else ""

                    if eid in self._IGNORE_IDS:
                        continue

                    label = self._EFFECT_IDS.get(eid)
                    if label:
                        detected.append(label)
                        if eid == "timeremap":
                            speed_note = self._read_speed_ramp(eff)
                    elif eid:
                        name_el = eff.find("name")
                        name = (
                            name_el.text.strip()
                            if name_el and name_el.text
                            else eid
                        )
                        if name:
                            detected.append(name)

                data = self._extract_clip_data(child, resolved)
                cursor = data["_seq_end_frames"] - self._seq_offset_frames

                if detected:
                    data["Effect"] = ", ".join(detected)
                    data["Notes"] = speed_note
                    results.append(data)

        return results

    def clip_fps_map(self) -> dict[str, float]:
        """
        Build a lookup of clip name → native frame rate for every clip
        in the XML.  Used by the EDL scanner to distinguish real speed
        changes from frame-rate-conversion artefacts.

        Keys are stored **lower-cased** so EDL look-ups (which may differ
        in case) match reliably.
        """
        if not self.soup and not self._load_xml():
            return {}
        assert self.soup is not None
        result: dict[str, float] = {}
        for clip in self.soup.find_all("clipitem"):
            if not isinstance(clip, Tag):
                continue
            name_el = clip.find("name")
            if not name_el or not name_el.text:
                continue
            key = name_el.text.strip().lower()
            if key in result:
                continue
            clip_fps = self._clip_fps(clip)
            result[key] = clip_fps if clip_fps is not None else self.fps
        return result

    @staticmethod
    def _read_speed_ramp(effect_tag: Tag) -> str:
        """Extract the speed value from a Time Remap effect's parameters."""
        for param in effect_tag.find_all("parameter"):
            pid = param.find("parameterid")
            if pid and pid.text and pid.text.strip() == "speed":
                val = param.find("value")
                if val and val.text:
                    try:
                        return f"{float(val.text):.1f}%"
                    except ValueError:
                        pass
        return ""

    @staticmethod
    def _clip_start_raw(clip: Tag) -> int:
        """Read the raw <start> value (-1 means unplaced/linked clip)."""
        el = clip.find("start", recursive=False)
        if el and el.text:
            try:
                return int(el.text)
            except ValueError:
                pass
        return 0

    @staticmethod
    def _clip_fps(clip: Tag) -> float | None:
        """
        Read the clip's own ``<rate>`` block and return its native FPS,
        or ``None`` if the clip uses the sequence rate.
        """
        rate_el = clip.find("rate", recursive=False)
        if not rate_el or not isinstance(rate_el, Tag):
            return None
        tb_el = rate_el.find("timebase")
        if not tb_el or not tb_el.text:
            return None
        try:
            timebase = int(tb_el.text)
        except ValueError:
            return None
        ntsc_el = rate_el.find("ntsc")
        ntsc = (
            ntsc_el.text.strip().upper() == "TRUE"
            if ntsc_el and ntsc_el.text
            else False
        )
        if ntsc:
            return timebase * 1000.0 / 1001.0
        return float(timebase)

    def _extract_clip_data(
        self, clip: Tag, resolved_start: int = 0
    ) -> dict[str, Any]:
        """
        Extract timing and metadata from a ``<clipitem>``.

        *resolved_start* is the pre-computed sequence-frame position for
        this clip (already resolved from explicit ``<start>``, a preceding
        ``<transitionitem>``, or a running cursor).

        Source ``<in>``/``<out>`` are converted using the **clip's own**
        frame rate (from its ``<rate>`` block) so that source timecodes
        are accurate even when the footage was shot at a different rate
        than the sequence.
        """
        name_el = clip.find("name")
        name = name_el.text if name_el and name_el.text else "Unknown"

        def _int_child(tag: str) -> int:
            child = clip.find(tag, recursive=False)
            if child and child.text:
                try:
                    return int(child.text)
                except ValueError:
                    pass
            return 0

        src_fps = self._clip_fps(clip) or self.fps

        seq_start = resolved_start
        seq_end = _int_child("end")
        src_in = _int_child("in")
        src_out = _int_child("out")

        if src_fps != self.fps:
            clip_dur_sec = (src_out - src_in) / src_fps if src_fps > 0 else 0
            clip_dur_seq = int(round(clip_dur_sec * self.fps))
        else:
            clip_dur_seq = max(0, src_out - src_in)

        if seq_end < 0:
            seq_end = seq_start + clip_dur_seq

        seq_start += self._seq_offset_frames
        seq_end += self._seq_offset_frames

        duration_frames = max(0, seq_end - seq_start)

        file_ref = clip.find("file")
        resolution = "Unknown"
        if file_ref and isinstance(file_ref, Tag):
            w_el = file_ref.find("width")
            h_el = file_ref.find("height")
            if w_el and w_el.text and h_el and h_el.text:
                resolution = f"{w_el.text}x{h_el.text}"

        src_dur_frames = max(0, src_out - src_in)

        return {
            "Name": name,
            "Seq_In": frames_to_smpte(seq_start, self.fps),
            "Seq_Out": frames_to_smpte(seq_end, self.fps),
            "Src_In": frames_to_smpte(src_in, src_fps),
            "Src_Out": frames_to_smpte(src_out, src_fps),
            "Duration": frames_to_smpte(duration_frames, self.fps),
            "Src_Duration": frames_to_smpte(src_dur_frames, src_fps),
            "Resolution": resolution,
            "_seq_start_frames": seq_start,
            "_seq_end_frames": seq_end,
        }


def consolidate_consecutive(
    clips: list[dict[str, Any]],
    fps: float,
    max_gap_frames: int = 48,
) -> list[dict[str, Any]]:
    """
    Merge consecutive edits of the same song into a single cue-sheet entry.

    Two clips are "consecutive" when they share the same Name and the gap
    between the first clip's end and the next clip's start is <= max_gap_frames
    (default 48 frames ≈ 2 sec, covers crossfades).  Non-consecutive reuses of
    the same song become separate entries.
    """
    if not clips:
        return []

    sorted_clips = sorted(clips, key=lambda c: c["_seq_start_frames"])
    merged: list[dict[str, Any]] = []

    current = dict(sorted_clips[0])
    for nxt in sorted_clips[1:]:
        same_song = nxt["Name"] == current["Name"]
        gap = nxt["_seq_start_frames"] - current["_seq_end_frames"]

        if same_song and gap <= max_gap_frames:
            current["_seq_end_frames"] = max(
                current["_seq_end_frames"], nxt["_seq_end_frames"]
            )
            current["Seq_Out"] = frames_to_smpte(current["_seq_end_frames"], fps)
            dur = current["_seq_end_frames"] - current["_seq_start_frames"]
            current["Duration"] = frames_to_smpte(max(0, dur), fps)
        else:
            merged.append(current)
            current = dict(nxt)

    merged.append(current)
    return merged
