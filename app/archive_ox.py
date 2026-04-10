"""Archive Ox Batch Uploader panel for Assistant Editor Pro.

Provides a PySide6 panel that wraps the Selenium-based ArchiveOxAutomator,
letting users log in, select files, configure record metadata, and run
the batch upload — all within the main application's nav stack.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor

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


# ── Worker thread ───────────────────────────────────────────

class _BatchWorker(QThread):
    """Runs the full Archive Ox flow in a background thread."""

    progress = Signal(int, int, str)   # current, total, message
    finished = Signal(list)            # list of result dicts
    error = Signal(str)

    def __init__(
        self,
        email: str,
        password: str,
        files: list[str],
        project: str,
        record_type: str,
        copyright_owner: str,
        date_value: str,
        source_info: str,
        notes: str,
        naming_pattern: str,
    ):
        super().__init__()
        self.email = email
        self.password = password
        self.files = files
        self.project = project
        self.record_type = record_type
        self.copyright_owner = copyright_owner
        self.date_value = date_value
        self.source_info = source_info
        self.notes = notes
        self.naming_pattern = naming_pattern

    def run(self) -> None:
        try:
            from app.archive_ox_core import ArchiveOxAutomator

            auto = ArchiveOxAutomator()

            self.progress.emit(0, len(self.files), "Setting up browser…")
            if not auto.setup_driver():
                self.error.emit("Failed to start Chrome. Is Chrome installed?")
                return

            self.progress.emit(0, len(self.files), "Logging in to Archive Ox…")
            if not auto.login_to_archive_ox(self.email, self.password):
                auto.cleanup()
                self.error.emit(
                    "Login failed — check your email/password and try again."
                )
                return

            def _on_progress(i: int, total: int, msg: str) -> None:
                self.progress.emit(i, total, msg)

            results = auto.process_batch(
                self.files,
                source_info=self.source_info,
                naming_pattern=self.naming_pattern,
                record_type=self.record_type,
                project_name=self.project,
                copyright_owner=self.copyright_owner,
                date_value=self.date_value,
                notes=self.notes,
                on_progress=_on_progress,
            )

            output_dir = Path(self.files[0]).parent if self.files else Path.cwd()
            auto.save_results(results, str(output_dir / "batch_results.json"))
            auto.cleanup()
            self.finished.emit(results)

        except Exception as exc:
            self.error.emit(str(exc))


# ── Panel ───────────────────────────────────────────────────

class ArchiveOxPanel(QWidget):
    """Full-width panel that integrates into the nav stack."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {_BG_DEEP};")

        self._files: list[str] = []
        self._running = False
        self._worker: _BatchWorker | None = None

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

        header = QLabel("ARCHIVE OX UPLOADER")
        header.setFont(QFont("SF Pro Display", 12, QFont.Bold))
        header.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; letter-spacing: 2px; padding-bottom: 4px;"
        )
        fa.addWidget(header)
        sub = QLabel("Batch-create records and rename files with Archive Ox IDs")
        sub.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px; padding-bottom: 10px;"
        )
        fa.addWidget(sub)
        fa.addWidget(_divider())
        fa.addSpacing(20)

        cols = QHBoxLayout()
        cols.setSpacing(28)

        # ── Col 1: Credentials + File Selection ─────────────
        col1 = QVBoxLayout()
        col1.setSpacing(0)

        col1.addWidget(_section_label("EMAIL"))
        col1.addSpacing(6)
        self._email = QLineEdit()
        self._email.setPlaceholderText("you@example.com")
        col1.addWidget(self._email)
        col1.addSpacing(10)

        col1.addWidget(_section_label("PASSWORD"))
        col1.addSpacing(6)
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("Archive Ox password")
        col1.addWidget(self._password)
        col1.addSpacing(16)

        col1.addWidget(_divider())
        col1.addSpacing(14)

        col1.addWidget(_section_label("FILE SELECTION"))
        col1.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_files = QPushButton("Select Files")
        self._btn_files.setObjectName("secondaryBtn")
        self._btn_files.setCursor(Qt.PointingHandCursor)
        self._btn_files.clicked.connect(self._pick_files)
        btn_row.addWidget(self._btn_files)

        self._btn_folder = QPushButton("Select Folder")
        self._btn_folder.setObjectName("secondaryBtn")
        self._btn_folder.setCursor(Qt.PointingHandCursor)
        self._btn_folder.clicked.connect(self._pick_folder)
        btn_row.addWidget(self._btn_folder)
        col1.addLayout(btn_row)
        col1.addSpacing(4)

        self._file_label = _status_label("No files selected")
        col1.addWidget(self._file_label)
        col1.addStretch()

        cols.addLayout(col1, stretch=1)

        # ── Col 2: Record Details ───────────────────────────
        col2 = QVBoxLayout()
        col2.setSpacing(0)

        col2.addWidget(_section_label("PROJECT"))
        col2.addSpacing(6)
        self._project = QComboBox()
        self._project.setObjectName("comboBox")
        self._project.setEditable(True)
        self._project.addItems(["", "OSOS", "TOKYO"])
        col2.addWidget(self._project)
        col2.addSpacing(10)

        col2.addWidget(_section_label("RECORD TYPE"))
        col2.addSpacing(6)
        self._rec_type = QComboBox()
        self._rec_type.setObjectName("comboBox")
        self._rec_type.addItems(["auto", "Audio", "Footage", "Still"])
        col2.addWidget(self._rec_type)
        col2.addSpacing(10)

        col2.addWidget(_section_label("COPYRIGHT"))
        col2.addSpacing(6)
        self._copyright = QLineEdit()
        self._copyright.setPlaceholderText("Copyright holder")
        col2.addWidget(self._copyright)
        col2.addSpacing(10)

        col2.addWidget(_section_label("DATE"))
        col2.addSpacing(6)
        self._date = QLineEdit()
        self._date.setPlaceholderText("YYYY-MM-DD")
        col2.addWidget(self._date)
        col2.addStretch()

        cols.addLayout(col2, stretch=1)

        # ── Col 3: Additional Info ──────────────────────────
        col3 = QVBoxLayout()
        col3.setSpacing(0)

        col3.addWidget(_section_label("SOURCE INFO"))
        col3.addSpacing(6)
        self._source = QLineEdit()
        self._source.setPlaceholderText("Optional source description")
        col3.addWidget(self._source)
        col3.addSpacing(10)

        col3.addWidget(_section_label("NOTES"))
        col3.addSpacing(6)
        self._notes = QLineEdit()
        self._notes.setText("Archive Ox batch upload")
        col3.addWidget(self._notes)
        col3.addSpacing(10)

        col3.addWidget(_section_label("NAMING PATTERN"))
        col3.addSpacing(6)
        self._naming = QLineEdit()
        self._naming.setText("{serial}_{name}{ext}")
        col3.addWidget(self._naming)
        col3.addSpacing(4)
        hint = QLabel("{serial} = record ID, {name} = filename, {ext} = extension")
        hint.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        col3.addWidget(hint)
        col3.addStretch()

        cols.addLayout(col3, stretch=1)

        fa.addLayout(cols)
        fa.addStretch()
        fa.addSpacing(12)

        # ── Action bar ──────────────────────────────────────
        self._btn_start = QPushButton("START PROCESSING")
        self._btn_start.setObjectName("downloadBtn")
        self._btn_start.setCursor(Qt.PointingHandCursor)
        self._btn_start.setFixedHeight(46)
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        glow = QGraphicsDropShadowEffect()
        glow.setColor(QColor(_GREEN))
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        self._btn_start.setGraphicsEffect(glow)
        fa.addWidget(self._btn_start)
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

    # ── File selection ──────────────────────────────────────

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files",
            str(Path.home()),
            "All files (*)",
        )
        if paths:
            self._files = paths
            self._file_label.setText(f"{len(paths)} file(s) selected")
            self._btn_start.setEnabled(True)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", str(Path.home())
        )
        if folder:
            self._files = [
                os.path.join(root, f)
                for root, _, files in os.walk(folder)
                for f in files
                if not f.startswith(".")
            ]
            self._file_label.setText(
                f"{len(self._files)} file(s) found in folder"
            )
            self._btn_start.setEnabled(bool(self._files))

    # ── Processing ──────────────────────────────────────────

    def _on_start(self) -> None:
        if self._running or not self._files:
            return

        email = self._email.text().strip()
        pw = self._password.text()
        if not email or not pw:
            QMessageBox.warning(
                self, "Missing Credentials",
                "Enter your Archive Ox email and password.",
            )
            return

        ok = QMessageBox.question(
            self,
            "Confirm",
            f"Process {len(self._files)} file(s)?\n\n"
            "This will:\n"
            "1. Log into Archive Ox\n"
            "2. Create a record for each file\n"
            "3. Rename local files with record IDs",
        )
        if ok != QMessageBox.Yes:
            return

        self._running = True
        self._btn_start.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setMaximum(len(self._files))

        self._worker = _BatchWorker(
            email=email,
            password=pw,
            files=self._files,
            project=self._project.currentText(),
            record_type=self._rec_type.currentText(),
            copyright_owner=self._copyright.text(),
            date_value=self._date.text(),
            source_info=self._source.text(),
            notes=self._notes.text(),
            naming_pattern=self._naming.text(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, cur: int, total: int, msg: str) -> None:
        self._progress.setValue(cur)
        self._status.setText(msg)

    def _on_done(self, results: list) -> None:
        self._running = False
        self._btn_start.setEnabled(True)
        self._progress.setValue(self._progress.maximum())

        ok = sum(1 for r in results if r["status"] == "success")
        fail = len(results) - ok
        self._status.setText(
            f"Complete — {ok} succeeded, {fail} failed. "
            "Results saved to batch_results.json"
        )

    def _on_error(self, msg: str) -> None:
        self._running = False
        self._btn_start.setEnabled(True)
        self._status.setText(f"Error: {msg}")
