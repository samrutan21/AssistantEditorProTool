"""YouTube Downloader panel for Assistant Editor Pro.

Ports the functionality of youtube-downloader-pro (tkinter) into a PySide6
panel that slots into the main application's QStackedWidget.
"""

from __future__ import annotations

import os
import ssl
import sys
import json
import subprocess
from pathlib import Path
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QInputDialog, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor

# ── SSL workarounds (same as original) ──────────────────────
ssl._create_default_https_context = ssl._create_unverified_context
os.environ.setdefault("PYTHONHTTPSVERIFY", "0")
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except (ImportError, AttributeError):
    pass

def _ensure_ytdlp() -> bool:
    """Import yt-dlp, auto-upgrading to the latest version first."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "yt-dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    try:
        global yt_dlp
        import yt_dlp  # type: ignore[import-untyped]
        return True
    except ImportError:
        return False

_HAS_YTDLP = _ensure_ytdlp()

# ── Palette (matches main app) ─────────────────────────────
_BG_DEEP = "#0A0A0C"
_BG_SURFACE = "#16161A"
_BG_INPUT = "#1C1C22"
_BORDER = "#28282F"
_TEXT_PRIMARY = "#E2E2E8"
_TEXT_SECONDARY = "#8888A0"
_TEXT_MUTED = "#5C5C72"
_ACCENT = "#5C7CFA"
_GREEN = "#34C759"


# ── Helpers (same pattern as main_window) ───────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionLabel")
    return lbl


def _status_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("statusLabel")
    lbl.setWordWrap(True)
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {_BORDER};")
    return line


# ── Worker threads ──────────────────────────────────────────

class _AnalyzeWorker(QThread):
    finished = Signal(object, object, object)
    error = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "ignoreerrors": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if info is None:
                self.error.emit(
                    "Could not extract video info — the video may be "
                    "unavailable, private, or the URL is invalid."
                )
                return

            res_fmts: dict[str, list[dict]] = defaultdict(list)
            for fmt in info.get("formats", []):
                if fmt.get("vcodec") == "none":
                    continue
                h, w = fmt.get("height"), fmt.get("width")
                if h and w:
                    key = f"{w}x{h}"
                    res_fmts[key].append({
                        "format_id": fmt.get("format_id", ""),
                        "width": w,
                        "height": h,
                        "fps": fmt.get("fps", 30),
                        "filesize": fmt.get("filesize")
                        or fmt.get("filesize_approx", 0),
                        "has_audio": fmt.get("acodec", "none") != "none",
                    })

            audio_codecs: dict[str, dict] = {}
            for fmt in info.get("formats", []):
                ac = fmt.get("acodec") or ""
                if fmt.get("vcodec") != "none" or ac in ("none", ""):
                    continue
                abr = fmt.get("abr") or 0
                fid = fmt.get("format_id", "")
                ext = fmt.get("ext", "")
                if ac.startswith("mp4a") or ac == "aac":
                    ck, cd = "aac", "AAC"
                elif ac == "opus":
                    ck, cd = "opus", "Opus"
                elif ac == "vorbis":
                    ck, cd = "vorbis", "Vorbis"
                else:
                    ck, cd = ac.lower().replace(".", "_"), ac.upper()
                if ck not in audio_codecs or abr > audio_codecs[ck].get("abr", 0):
                    audio_codecs[ck] = {
                        "format_id": fid,
                        "codec_key": ck,
                        "codec_display": cd,
                        "abr": abr,
                    }

            audio_list = sorted(
                audio_codecs.values(),
                key=lambda x: {"opus": 0, "aac": 1}.get(x["codec_key"], 99),
            )
            self.finished.emit(dict(info), dict(res_fmts), list(audio_list))
        except Exception as exc:
            self.error.emit(str(exc))


class _DownloadWorker(QThread):
    progress = Signal(float, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, url: str, opts: dict):
        super().__init__()
        self.url = url
        self.opts = opts

    def run(self) -> None:
        try:
            self.opts["progress_hooks"] = [self._hook]
            with yt_dlp.YoutubeDL(self.opts) as ydl:
                ydl.download([self.url])
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))

    def _hook(self, d: dict) -> None:
        if d["status"] == "downloading":
            dl = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            pct = min((dl / total) * 100, 98.0) if total > 0 else 0
            spd = d.get("speed", 0)
            eta = d.get("eta", 0)
            s = f"{spd / 1_000_000:.1f} MB/s" if spd else "…"
            e = f"{int(eta // 60)}m {int(eta % 60)}s" if eta else "…"
            self.progress.emit(pct, f"Downloading — {s} • ETA: {e}")
        elif d["status"] == "finished":
            self.progress.emit(99, "Merging video and audio…")


# ── Panel ───────────────────────────────────────────────────

class YTDownloaderPanel(QWidget):
    """Full-width panel that integrates into the nav stack."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {_BG_DEEP};")

        self._info: dict | None = None
        self._res_fmts: dict[str, list[dict]] = {}
        self._audio_opts: list[dict] = []
        self._quality_map: list[dict] = []
        self._output = str(Path.home() / "Downloads")
        self._downloading = False
        self._partials: list[dict] = []
        self._worker: QThread | None = None

        self._build()

    # ── UI construction ─────────────────────────────────────

    def _build(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Top: form area ──────────────────────────────────
        form = QWidget()
        fa = QVBoxLayout(form)
        fa.setContentsMargins(28, 24, 28, 0)
        fa.setSpacing(0)

        header = QLabel("YOUTUBE DOWNLOADER")
        header.setFont(QFont("SF Pro Display", 12, QFont.Bold))
        header.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; letter-spacing: 2px; "
            f"padding-bottom: 4px;"
        )
        fa.addWidget(header)
        sub = QLabel("Download videos in any quality")
        sub.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px; padding-bottom: 10px;"
        )
        fa.addWidget(sub)
        fa.addWidget(_divider())
        fa.addSpacing(20)

        if not _HAS_YTDLP:
            msg = QLabel(
                "yt-dlp is not installed.\n\n"
                "Run:  pip install yt-dlp"
            )
            msg.setStyleSheet(
                f"color: {_TEXT_SECONDARY}; font-size: 13px; padding: 20px;"
            )
            msg.setWordWrap(True)
            fa.addWidget(msg)
            fa.addStretch()
            vbox.addWidget(form, stretch=1)
            return

        cols = QHBoxLayout()
        cols.setSpacing(28)

        # ── Col 1: Video URL & Info ─────────────────────────
        col1 = QVBoxLayout()
        col1.setSpacing(0)

        col1.addWidget(_section_label("VIDEO URL"))
        col1.addSpacing(6)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=..."
        )
        col1.addWidget(self._url_input)
        col1.addSpacing(8)

        self._btn_analyze = QPushButton("ANALYZE VIDEO")
        self._btn_analyze.setObjectName("primaryBtn")
        self._btn_analyze.setCursor(Qt.PointingHandCursor)
        self._btn_analyze.setFixedHeight(40)
        self._btn_analyze.clicked.connect(self._on_analyze)
        col1.addWidget(self._btn_analyze)
        col1.addSpacing(16)

        col1.addWidget(_divider())
        col1.addSpacing(14)

        col1.addWidget(_section_label("VIDEO INFORMATION"))
        col1.addSpacing(6)

        self._info_title = QLabel("No video loaded")
        self._info_title.setWordWrap(True)
        self._info_title.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; font-size: 12px;"
        )
        col1.addWidget(self._info_title)
        col1.addSpacing(4)

        self._info_details = QLabel("")
        self._info_details.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px;"
        )
        col1.addWidget(self._info_details)
        col1.addStretch()

        cols.addLayout(col1, stretch=1)

        # ── Col 2: Quality Selection ────────────────────────
        col2 = QVBoxLayout()
        col2.setSpacing(0)

        col2.addWidget(_section_label("SELECT QUALITY"))
        col2.addSpacing(6)

        self._quality_list = QListWidget()
        self._quality_list.setObjectName("qualityList")
        self._quality_list.currentRowChanged.connect(self._on_quality)
        col2.addWidget(self._quality_list, stretch=1)

        cols.addLayout(col2, stretch=2)

        # ── Col 3: Download Location & Resume ───────────────
        col3 = QVBoxLayout()
        col3.setSpacing(0)

        col3.addWidget(_section_label("DOWNLOAD LOCATION"))
        col3.addSpacing(6)
        self._btn_folder = QPushButton("Set Folder…")
        self._btn_folder.setObjectName("secondaryBtn")
        self._btn_folder.setCursor(Qt.PointingHandCursor)
        self._btn_folder.clicked.connect(self._browse)
        col3.addWidget(self._btn_folder)
        col3.addSpacing(3)
        self._loc_label = _status_label(self._output)
        col3.addWidget(self._loc_label)
        col3.addSpacing(16)

        col3.addWidget(_divider())
        col3.addSpacing(14)

        col3.addWidget(_section_label("PARTIAL DOWNLOADS"))
        col3.addSpacing(6)
        self._btn_scan = QPushButton("Scan for Partials")
        self._btn_scan.setObjectName("secondaryBtn")
        self._btn_scan.setCursor(Qt.PointingHandCursor)
        self._btn_scan.clicked.connect(self._scan_partials)
        col3.addWidget(self._btn_scan)
        col3.addSpacing(6)

        self._resume_list = QListWidget()
        self._resume_list.setObjectName("qualityList")
        self._resume_list.setMaximumHeight(100)
        self._resume_list.currentRowChanged.connect(self._on_partial_select)
        col3.addWidget(self._resume_list)
        col3.addSpacing(6)

        self._btn_resume = QPushButton("Resume Selected")
        self._btn_resume.setObjectName("secondaryBtn")
        self._btn_resume.setCursor(Qt.PointingHandCursor)
        self._btn_resume.setEnabled(False)
        self._btn_resume.clicked.connect(self._resume_download)
        col3.addWidget(self._btn_resume)
        col3.addStretch()

        cols.addLayout(col3, stretch=1)

        fa.addLayout(cols)
        fa.addStretch()
        fa.addSpacing(12)

        # ── Action bar ──────────────────────────────────────
        self._btn_download = QPushButton("DOWNLOAD")
        self._btn_download.setObjectName("downloadBtn")
        self._btn_download.setCursor(Qt.PointingHandCursor)
        self._btn_download.setFixedHeight(46)
        self._btn_download.setEnabled(False)
        self._btn_download.clicked.connect(self._on_download)
        glow = QGraphicsDropShadowEffect()
        glow.setColor(QColor(_GREEN))
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        self._btn_download.setGraphicsEffect(glow)
        fa.addWidget(self._btn_download)
        fa.addSpacing(12)

        vbox.addWidget(form, stretch=3)

        # ── Bottom: progress ────────────────────────────────
        vbox.addWidget(_divider())

        prog_area = QWidget()
        prog_area.setStyleSheet(f"background-color: {_BG_SURFACE};")
        pa = QVBoxLayout(prog_area)
        pa.setContentsMargins(28, 10, 28, 12)
        pa.setSpacing(6)

        pa.addWidget(_section_label("PROGRESS"))

        self._progress = QProgressBar()
        self._progress.setObjectName("dlProgress")
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        pa.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(
            f"color: {_TEXT_SECONDARY}; font-size: 11px;"
        )
        pa.addWidget(self._status)

        vbox.addWidget(prog_area, stretch=1)

    # ── Analyze ─────────────────────────────────────────────

    def _on_analyze(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Enter a YouTube URL first.")
            return

        self._btn_analyze.setEnabled(False)
        self._btn_analyze.setText("ANALYZING…")
        self._status.setText("Analyzing video…")

        self._worker = _AnalyzeWorker(url)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.error.connect(self._on_analyze_err)
        self._worker.start()

    def _on_analyze_done(
        self, info: dict, res_fmts: dict, audio: list
    ) -> None:
        self._btn_analyze.setEnabled(True)
        self._btn_analyze.setText("ANALYZE VIDEO")
        self._info = info
        self._res_fmts = res_fmts
        self._audio_opts = audio

        title = info.get("title", "Unknown")
        dur = info.get("duration", 0)
        up = info.get("uploader", "Unknown")
        h, m, s = dur // 3600, (dur % 3600) // 60, dur % 60
        self._info_title.setText(title)
        self._info_details.setText(f"{h}h {m}m {s}s  ·  {up}")

        self._quality_list.clear()
        self._quality_map.clear()

        for af in audio:
            abr = f" · {int(af['abr'])}kbps" if af.get("abr") else ""
            txt = f"{af['codec_display']} — native{abr}"
            self._quality_list.addItem(txt)
            self._quality_map.append({"type": "audio_native", **af})

        if audio:
            for codec, label, note in [
                ("mp3", "MP3", "192kbps · requires FFmpeg"),
                ("flac", "FLAC", "lossless · requires FFmpeg"),
                ("wav", "WAV", "lossless PCM · requires FFmpeg"),
            ]:
                self._quality_list.addItem(f"{label} — {note}")
                self._quality_map.append({
                    "type": "audio_transcode",
                    "codec": codec,
                })

        sorted_res = sorted(
            res_fmts.items(),
            key=lambda x: int(x[0].split("x")[1]),
            reverse=True,
        )
        for res, fmts in sorted_res:
            best = max(fmts, key=lambda f: (f["has_audio"], f["fps"]))
            w, h = res.split("x")
            hi = int(h)
            q = (
                "4K" if hi >= 2160 else "2K" if hi >= 1440
                else "Full HD" if hi >= 1080 else "HD" if hi >= 720
                else "SD" if hi >= 480 else "Low"
            )
            fs = best["filesize"]
            sz = (
                f"~{fs / 1e9:.1f} GB" if fs > 1e9
                else f"~{fs / 1e6:.1f} MB" if fs > 0
                else "size unknown"
            )
            a = "Audio: yes" if best["has_audio"] else "Audio: no"
            txt = f"{res} ({q}) · {best['fps']}fps · {a} · {sz}"
            self._quality_list.addItem(txt)
            self._quality_map.append({
                "type": "video",
                "format_id": best["format_id"],
                "resolution": res,
            })

        self._status.setText(
            "Video analyzed — select a quality and click Download."
        )

    def _on_analyze_err(self, msg: str) -> None:
        self._btn_analyze.setEnabled(True)
        self._btn_analyze.setText("ANALYZE VIDEO")
        self._status.setText(f"Error: {msg}")

    # ── Quality selection ───────────────────────────────────

    def _on_quality(self, row: int) -> None:
        self._btn_download.setEnabled(row >= 0)

    # ── Download ────────────────────────────────────────────

    def _on_download(self) -> None:
        row = self._quality_list.currentRow()
        if row < 0 or row >= len(self._quality_map) or self._downloading:
            return
        entry = self._quality_map[row]
        url = self._url_input.text().strip()
        if not url:
            return

        opts = self._build_opts(entry)
        self._start_download(url, opts)

    def _build_opts(self, entry: dict) -> dict:
        out = self._output
        os.makedirs(out, exist_ok=True)
        base = {
            "outtmpl": os.path.join(out, "%(title)s.%(ext)s"),
            "continuedl": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "retries": 10,
            "fragment_retries": 10,
        }

        t = entry["type"]
        if t == "audio_native":
            base["format"] = entry["format_id"]
        elif t == "audio_transcode":
            codec = entry["codec"]
            q = "0" if codec in ("flac", "wav") else "192"
            base["format"] = "bestaudio/best"
            base["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": q,
            }]
        else:
            base["format"] = f"{entry['format_id']}+bestaudio/best"
            base["merge_output_format"] = "mp4"

        return base

    def _start_download(self, url: str, opts: dict) -> None:
        self._downloading = True
        self._btn_download.setEnabled(False)
        self._progress.setValue(0)
        self._status.setText("Starting download…")

        self._worker = _DownloadWorker(url, opts)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_dl_done)
        self._worker.error.connect(self._on_dl_err)
        self._worker.start()

    def _on_progress(self, pct: float, text: str) -> None:
        self._progress.setValue(int(pct))
        self._status.setText(text)

    def _on_dl_done(self) -> None:
        self._downloading = False
        self._btn_download.setEnabled(True)
        self._progress.setValue(100)
        self._status.setText("Download complete!")

    def _on_dl_err(self, msg: str) -> None:
        self._downloading = False
        self._btn_download.setEnabled(True)
        self._status.setText(f"Download failed: {msg}")

    # ── Browse ──────────────────────────────────────────────

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Download Location", self._output
        )
        if d:
            self._output = d
            self._loc_label.setText(d)

    # ── Resume partial downloads ────────────────────────────

    def _scan_partials(self) -> None:
        self._partials.clear()
        self._resume_list.clear()
        self._btn_resume.setEnabled(False)

        dl_path = Path(self._output)
        if not dl_path.exists():
            self._resume_list.addItem("Directory does not exist.")
            return

        parts = list(dl_path.glob("*.part")) + list(dl_path.glob("*.PART"))
        parts = [p for p in parts if "-Frag" not in p.name]

        if not parts:
            self._resume_list.addItem("No partial downloads found.")
            return

        for pf in parts:
            try:
                sz = pf.stat().st_size
                sz_s = (
                    f"{sz / 1e9:.2f} GB" if sz > 1e9
                    else f"{sz / 1e6:.1f} MB"
                )
            except OSError:
                sz_s = "?"
            name = pf.stem

            ytdl = pf.with_suffix(".part.ytdl")
            if not ytdl.exists():
                ytdl = pf.parent / f"{name}.ytdl"

            self._partials.append({
                "path": str(pf),
                "name": name,
                "ytdl": str(ytdl) if ytdl.exists() else None,
            })
            self._resume_list.addItem(f"{name}  ({sz_s})")

        self._status.setText(
            f"Found {len(self._partials)} partial download(s)."
        )

    def _on_partial_select(self, row: int) -> None:
        self._btn_resume.setEnabled(0 <= row < len(self._partials))

    def _resume_download(self) -> None:
        row = self._resume_list.currentRow()
        if row < 0 or row >= len(self._partials) or self._downloading:
            return

        p = self._partials[row]
        url: str | None = None

        if p["ytdl"]:
            try:
                with open(p["ytdl"]) as f:
                    meta = json.load(f)
                url = meta.get("url") or meta.get("webpage_url")
            except Exception:
                pass

        if not url:
            url, ok = QInputDialog.getText(
                self,
                "Resume Download",
                f"Enter the YouTube URL for:\n{p['name']}",
            )
            if not ok or not url:
                return

        pf = Path(p["path"])
        opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": str(pf.with_suffix("")),
            "merge_output_format": "mp4",
            "continuedl": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "retries": 10,
            "fragment_retries": 10,
        }
        self._start_download(url, opts)
