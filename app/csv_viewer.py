"""CSV Viewer panel for Assistant Editor Pro.

Embeddable panel with a tabbed interface — each opened CSV gets its own
closable tab containing a full table + cell-preview splitter.
"""

from __future__ import annotations

import csv
import os
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ── Palette (matches main app) ─────────────────────────────
_BG_DEEP = "#0A0A0C"
_BG_SURFACE = "#16161A"
_BG_INPUT = "#1C1C22"
_BORDER = "#28282F"
_TEXT_PRIMARY = "#E2E2E8"
_TEXT_SECONDARY = "#8888A0"
_TEXT_MUTED = "#5C5C72"

_CSV_SNIFF_DELIMS = ",;\t|"


def _detect_delimiter(sample: str) -> str:
    if not sample or not sample.strip():
        return ","
    first_line = next((ln for ln in sample.splitlines() if ln.strip()), "")
    if not first_line:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=_CSV_SNIFF_DELIMS)
        delim = dialect.delimiter
    except csv.Error:
        delim = ","

    def _fc(line: str, d: str) -> int:
        try:
            return len(next(csv.reader([line], delimiter=d)))
        except (csv.Error, StopIteration):
            return 0

    if _fc(first_line, ",") >= 3 and _fc(first_line, delim) <= 2:
        return ","
    return delim


def _divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {_BORDER};")
    return line


# ── Single-CSV tab content ──────────────────────────────────

class _CSVTab(QWidget):
    """One tab's worth of content: table + cell preview."""

    def __init__(self, path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.file_path = path

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(3)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setVisible(False)
        self.table.setFont(QFont("SF Pro Text", 12))
        self.table.currentCellChanged.connect(self._on_cell)
        splitter.addWidget(self.table)

        preview_box = QWidget()
        pv = QVBoxLayout(preview_box)
        pv.setContentsMargins(0, 6, 0, 0)
        pv.setSpacing(4)
        hint = QLabel("SELECTED CELL")
        hint.setObjectName("previewHint")
        pv.addWidget(hint)
        self.preview = QTextEdit()
        self.preview.setObjectName("cellPreview")
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("SF Mono", 12))
        self.preview.setMaximumHeight(100)
        self.preview.setPlaceholderText("Click a cell to preview its contents")
        pv.addWidget(self.preview)
        splitter.addWidget(preview_box)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        vbox.addWidget(splitter)

        self._row_count = 0
        self._col_count = 0
        self._load(path)

    def _on_cell(self, row: int, col: int, _pr: int, _pc: int) -> None:
        item = self.table.item(row, col)
        self.preview.setPlainText(item.text() if item else "")

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(1024)
            f.seek(0)
            delim = _detect_delimiter(sample)
            rows: List[List[str]] = list(csv.reader(f, delimiter=delim))

        if not rows:
            return

        header_idx = 0
        for i, row in enumerate(rows):
            if sum(1 for c in row if c and c.strip()) >= 3:
                header_idx = i
                break

        headers = rows[header_idx]
        headers = [
            h.strip() if h else f"Col {i + 1}"
            for i, h in enumerate(headers)
        ]

        data = [
            r for r in rows[header_idx + 1:]
            if any(c and c.strip() for c in r)
        ]

        max_cols = (
            max(len(headers), *(len(r) for r in data))
            if data else len(headers)
        )
        if len(headers) < max_cols:
            headers.extend(
                f"Col {i + 1}" for i in range(len(headers), max_cols)
            )

        self.table.clear()
        self.table.setColumnCount(max_cols)
        self.table.setRowCount(len(data))
        self.table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(data):
            for c in range(max_cols):
                text = row[c] if c < len(row) else ""
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()
        for c in range(max_cols):
            w = self.table.columnWidth(c)
            self.table.setColumnWidth(c, min(max(w, 80), 350))

        self._row_count = len(data)
        self._col_count = max_cols

    @property
    def info(self) -> str:
        return (
            f"{self._row_count} rows, {self._col_count} columns  —  "
            f"{self.file_path}"
        )


# ── Panel ───────────────────────────────────────────────────

class CSVViewerPanel(QWidget):
    """Full-width panel that integrates into the nav stack."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {_BG_DEEP};")
        self._build()

    def _build(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Tab area (majority of UI) ───────────────────────
        self._tabs = QTabWidget()
        self._tabs.setObjectName("csvTabs")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._update_status)
        vbox.addWidget(self._tabs, stretch=1)

        # Placeholder shown when no tabs are open
        self._empty = QLabel("Open a CSV file to get started")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 14px; padding: 40px;"
        )
        vbox.addWidget(self._empty)

        # ── Bottom bar ──────────────────────────────────────
        vbox.addWidget(_divider())
        bar = QWidget()
        bar.setStyleSheet(f"background-color: {_BG_SURFACE};")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(16, 8, 16, 8)
        bh.setSpacing(10)

        btn_open = QPushButton("Open CSV")
        btn_open.setObjectName("secondaryBtn")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(lambda: self.open_csv())
        bh.addWidget(btn_open)

        btn_clear = QPushButton("Clear All")
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_all)
        bh.addWidget(btn_clear)

        bh.addStretch()

        self._status = QLabel("No files open")
        self._status.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px;"
        )
        bh.addWidget(self._status)

        vbox.addWidget(bar)

        # Keyboard shortcut: Cmd/Ctrl+C copies the active cell
        sc = QShortcut(QKeySequence.Copy, self)
        sc.activated.connect(self._copy_cell)

        self._sync_placeholder()

    # ── Public API ──────────────────────────────────────────

    def open_csv(self, path: str | None = None) -> None:
        """Open a CSV file in a new tab. Prompts if *path* is None."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select CSV File",
                "",
                "CSV Files (*.csv *.tsv *.txt);;All Files (*)",
            )
        if not path:
            return
        try:
            tab = _CSVTab(path, self)
        except Exception as exc:
            self._status.setText(f"Error: {exc}")
            return
        name = os.path.basename(path)
        idx = self._tabs.addTab(tab, name)
        self._tabs.setCurrentIndex(idx)
        self._sync_placeholder()

    def clear_all(self) -> None:
        """Close every open tab."""
        while self._tabs.count():
            self._tabs.removeTab(0)
        self._sync_placeholder()

    # ── Internal ────────────────────────────────────────────

    def _close_tab(self, idx: int) -> None:
        self._tabs.removeTab(idx)
        self._sync_placeholder()

    def _sync_placeholder(self) -> None:
        has_tabs = self._tabs.count() > 0
        self._tabs.setVisible(has_tabs)
        self._empty.setVisible(not has_tabs)
        if not has_tabs:
            self._status.setText("No files open")

    def _update_status(self, idx: int) -> None:
        tab = self._tabs.widget(idx)
        if isinstance(tab, _CSVTab):
            self._status.setText(tab.info)

    def _copy_cell(self) -> None:
        tab = self._tabs.currentWidget()
        if isinstance(tab, _CSVTab):
            item = tab.table.currentItem()
            if item:
                QApplication.clipboard().setText(item.text())
