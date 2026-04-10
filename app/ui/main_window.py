import sys
import os
import json
import uuid as _uuid
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel,
    QLineEdit, QFrame, QMessageBox, QGraphicsDropShadowEffect,
    QScrollArea, QSizePolicy, QComboBox, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from app.yt_downloader import YTDownloaderPanel
from app.archive_ox import ArchiveOxPanel
from app.csv_viewer import CSVViewerPanel
from app.ai.api_client import PROVIDER_MODELS, PROVIDER_LABELS, fetch_ollama_models
from app.ai.key_store import get_key, set_key

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
_BG_DEEP       = "#0A0A0C"
_BG_SIDEBAR    = "#101014"
_BG_SURFACE    = "#16161A"
_BG_INPUT      = "#1C1C22"
_BORDER        = "#28282F"
_BORDER_FOCUS  = "#5C7CFA"
_TEXT_PRIMARY   = "#E2E2E8"
_TEXT_SECONDARY = "#8888A0"
_TEXT_MUTED     = "#5C5C72"
_ACCENT        = "#5C7CFA"
_ACCENT_HOVER  = "#7B93FF"
_ACCENT_PRESS  = "#4A64D4"
_BTN_BG        = "#1C1C22"
_BTN_HOVER     = "#252530"
_BTN_PRESS     = "#1A1A24"
_DANGER        = "#FF6B6B"
_NAV_BG        = "#08080A"

# ---------------------------------------------------------------------------
# Chat persistence directory
# ---------------------------------------------------------------------------
_CHAT_DIR = Path(__file__).resolve().parent.parent.parent / "chat_history"

# ---------------------------------------------------------------------------
# Global stylesheet
# ---------------------------------------------------------------------------
STYLESHEET = f"""
    QMainWindow {{
        background-color: {_BG_DEEP};
    }}

    /* --- Nav rail --- */
    QFrame#navRail {{
        background-color: {_NAV_BG};
        border-right: 1px solid {_BORDER};
    }}
    QPushButton#navBtn {{
        background-color: transparent;
        color: {_TEXT_MUTED};
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        padding: 14px 4px;
        font-size: 9px;
        font-weight: 600;
        letter-spacing: 0.6px;
    }}
    QPushButton#navBtn:hover {{
        color: {_TEXT_SECONDARY};
        background-color: #0E0E12;
    }}
    QPushButton#navBtn:checked {{
        color: {_ACCENT};
        border-left: 3px solid {_ACCENT};
        background-color: #0E0E14;
    }}

    /* --- Tool panel / form sidebar --- */
    QFrame#toolPanel {{
        background-color: {_BG_SIDEBAR};
        border-right: 1px solid {_BORDER};
    }}

    /* --- Chat history sidebar --- */
    QFrame#chatHistoryPanel {{
        background-color: {_BG_SIDEBAR};
        border-right: 1px solid {_BORDER};
    }}
    QPushButton#chatHistoryItem {{
        background-color: transparent;
        color: {_TEXT_SECONDARY};
        border: none;
        border-radius: 6px;
        text-align: left;
        padding: 10px 12px;
        font-size: 12px;
    }}
    QPushButton#chatHistoryItem:hover {{
        background-color: {_BG_INPUT};
    }}
    QPushButton#chatHistoryItem:checked {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
    }}
    QPushButton#newChatBtn {{
        background-color: {_ACCENT};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#newChatBtn:hover {{
        background-color: {_ACCENT_HOVER};
    }}
    QPushButton#newChatBtn:pressed {{
        background-color: {_ACCENT_PRESS};
    }}

    /* Section labels */
    QLabel#sectionLabel {{
        color: {_TEXT_MUTED};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1.8px;
        padding: 0px;
        margin: 0px;
    }}

    /* Status labels (file path readouts) */
    QLabel#statusLabel {{
        color: {_TEXT_SECONDARY};
        font-size: 11px;
        padding: 2px 0px;
    }}

    /* --- Inputs --- */
    QLineEdit {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 13px;
        selection-background-color: {_ACCENT};
    }}
    QLineEdit:focus {{
        border: 1px solid {_BORDER_FOCUS};
    }}
    QLineEdit::placeholder {{
        color: {_TEXT_MUTED};
    }}

    /* --- Buttons (secondary) --- */
    QPushButton#secondaryBtn {{
        background-color: {_BTN_BG};
        color: {_TEXT_SECONDARY};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 9px 14px;
        font-size: 12px;
        font-weight: 500;
        letter-spacing: 0.5px;
    }}
    QPushButton#secondaryBtn:hover {{
        background-color: {_BTN_HOVER};
        color: {_TEXT_PRIMARY};
        border: 1px solid #3A3A44;
    }}
    QPushButton#secondaryBtn:pressed {{
        background-color: {_BTN_PRESS};
    }}

    /* --- Primary action --- */
    QPushButton#primaryBtn {{
        background-color: {_ACCENT};
        color: #FFFFFF;
        border: 1px solid {_ACCENT_HOVER};
        border-radius: 8px;
        padding: 14px 20px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QPushButton#primaryBtn:hover {{
        background-color: {_ACCENT_HOVER};
        border: 1px solid #95ABFF;
    }}
    QPushButton#primaryBtn:pressed {{
        background-color: {_ACCENT_PRESS};
        border: 1px solid {_ACCENT};
    }}

    /* --- Content panels --- */
    QWidget#contentPanel {{
        background-color: {_BG_DEEP};
    }}

    QTextEdit#chatBox {{
        background-color: transparent;
        color: {_TEXT_SECONDARY};
        border: none;
        font-size: 13px;
        line-height: 1.6;
        padding: 12px;
    }}

    QTextEdit#chatInput {{
        background-color: {_BG_SURFACE};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 10px;
        padding: 12px 14px;
        font-size: 13px;
        selection-background-color: {_ACCENT};
    }}
    QTextEdit#chatInput:focus {{
        border: 1px solid {_BORDER_FOCUS};
    }}

    QPushButton#sendBtn {{
        background-color: {_BG_SURFACE};
        color: {_TEXT_SECONDARY};
        border: 1px solid {_BORDER};
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    QPushButton#sendBtn:hover {{
        background-color: {_BTN_HOVER};
        color: {_TEXT_PRIMARY};
        border-color: {_ACCENT};
    }}
    QPushButton#sendBtn:pressed {{
        background-color: {_BTN_PRESS};
    }}

    /* --- Attach button --- */
    QPushButton#attachBtn {{
        background-color: transparent;
        color: {_TEXT_MUTED};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton#attachBtn:hover {{
        color: {_TEXT_PRIMARY};
        border-color: #3A3A44;
        background-color: {_BTN_HOVER};
    }}

    /* --- Attachment chips --- */
    QPushButton#chipBtn {{
        background-color: {_BG_INPUT};
        color: {_TEXT_SECONDARY};
        border: 1px solid {_BORDER};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 11px;
    }}
    QPushButton#chipBtn:hover {{
        border-color: {_DANGER};
        color: {_DANGER};
    }}

    /* --- Provider bar (assistant panel) --- */
    QWidget#providerBar {{
        background-color: {_BG_SIDEBAR};
        border-bottom: 1px solid {_BORDER};
    }}
    QComboBox#providerCombo, QComboBox#modelCombo {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 5px;
        padding: 5px 8px;
        font-size: 11px;
        min-width: 110px;
        max-height: 28px;
    }}
    QComboBox#providerCombo:focus, QComboBox#modelCombo:focus {{
        border: 1px solid {_BORDER_FOCUS};
    }}
    QPushButton#apiKeyBtn {{
        background-color: transparent;
        color: {_TEXT_MUTED};
        border: 1px solid {_BORDER};
        border-radius: 5px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 500;
        max-height: 28px;
    }}
    QPushButton#apiKeyBtn:hover {{
        color: {_TEXT_PRIMARY};
        border-color: {_ACCENT};
        background-color: {_BTN_HOVER};
    }}
    QPushButton#apiKeyBtn[hasKey="true"] {{
        color: #34C759;
        border-color: #34C759;
    }}
    QLabel#providerLabel {{
        color: {_TEXT_MUTED};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}

    /* --- Combo box --- */
    QComboBox {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 13px;
    }}
    QComboBox:focus {{
        border: 1px solid {_BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {_TEXT_MUTED};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        selection-background-color: {_ACCENT};
        selection-color: #FFFFFF;
        padding: 4px;
    }}

    /* --- Sidebar scroll area --- */
    QScrollArea#sidebarScroll {{
        background: transparent;
        border: none;
    }}
    QScrollArea#sidebarScroll > QWidget > QWidget {{
        background: transparent;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #2A2A34;
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #3A3A48;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
        height: 0px;
    }}

    /* --- CSV tab widget --- */
    QTabWidget#csvTabs::pane {{
        background-color: {_BG_DEEP};
        border: none;
        border-top: 1px solid {_BORDER};
    }}
    QTabBar::tab {{
        background-color: {_BG_INPUT};
        color: {_TEXT_SECONDARY};
        border: 1px solid {_BORDER};
        border-bottom: none;
        padding: 7px 18px;
        font-size: 11px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        background-color: {_BG_DEEP};
        color: {_TEXT_PRIMARY};
        border-bottom: 1px solid {_BG_DEEP};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {_BTN_HOVER};
        color: {_TEXT_PRIMARY};
    }}
    QTabBar::close-button {{
        image: none;
        subcontrol-position: right;
        padding: 2px;
        border-radius: 3px;
    }}
    QTabBar::close-button:hover {{
        background-color: #FF6B6B40;
    }}

    /* --- Table (CSV viewer + YT quality list) --- */
    QTableWidget {{
        background-color: {_BG_DEEP};
        alternate-background-color: #121216;
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        gridline-color: {_BORDER};
        font-size: 12px;
        selection-background-color: #2A3A6A;
        selection-color: {_TEXT_PRIMARY};
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QTableWidget::item:selected {{
        background-color: #2A3A6A;
    }}
    QHeaderView::section {{
        background-color: #14141A;
        color: {_TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        padding: 6px 8px;
        border: none;
        border-right: 1px solid {_BORDER};
        border-bottom: 1px solid {_BORDER};
    }}
    QHeaderView::section:hover {{
        color: {_TEXT_PRIMARY};
        background-color: {_BTN_HOVER};
    }}

    /* --- Cell preview --- */
    QTextEdit#cellPreview {{
        background-color: {_BG_SURFACE};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-family: "SF Mono", "Menlo", "Consolas", monospace;
        font-size: 12px;
        selection-background-color: {_ACCENT};
    }}
    QLabel#previewHint {{
        color: {_TEXT_MUTED};
        font-size: 10px;
        letter-spacing: 0.4px;
    }}

    /* --- Quality / resume list (YouTube downloader) --- */
    QListWidget#qualityList {{
        background-color: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        font-family: "SF Mono";
        font-size: 11px;
        padding: 4px;
        outline: none;
    }}
    QListWidget#qualityList::item {{
        padding: 7px 10px;
        border-radius: 4px;
    }}
    QListWidget#qualityList::item:selected {{
        background-color: {_ACCENT};
        color: #FFFFFF;
    }}
    QListWidget#qualityList::item:hover:!selected {{
        background-color: {_BTN_HOVER};
    }}

    /* --- Progress bar --- */
    QProgressBar#dlProgress {{
        background-color: {_BG_INPUT};
        border: 1px solid {_BORDER};
        border-radius: 5px;
        text-align: center;
        color: {_TEXT_PRIMARY};
        font-size: 11px;
        min-height: 22px;
    }}
    QProgressBar#dlProgress::chunk {{
        background-color: #34C759;
        border-radius: 4px;
    }}

    /* --- Green download button --- */
    QPushButton#downloadBtn {{
        background-color: #34C759;
        color: #FFFFFF;
        border: 1px solid #2DB84E;
        border-radius: 8px;
        padding: 14px 20px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QPushButton#downloadBtn:hover {{
        background-color: #2DB84E;
        border: 1px solid #45D06A;
    }}
    QPushButton#downloadBtn:pressed {{
        background-color: #28A745;
    }}
    QPushButton#downloadBtn:disabled {{
        background-color: {_BTN_BG};
        color: {_TEXT_MUTED};
        border: 1px solid {_BORDER};
    }}
"""


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


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_TEXT_EXTS = {".csv", ".txt", ".xml", ".json", ".md", ".log", ".tsv", ".srt"}


class ChatInput(QTextEdit):
    """QTextEdit that emits ``submitted`` on Enter and inserts a newline on Shift+Enter."""

    submitted = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
        else:
            super().keyPressEvent(event)


class AssistantEditorPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant Editor Pro")
        self.setMinimumSize(1100, 800)
        self.setStyleSheet(STYLESHEET)

        self.xml_path = ""
        self.edl_paths: list[str] = []
        self.music_edl_path = ""
        self.export_folder = ""

        # Chat history state
        self._chat_sessions: list[dict] = []
        self._active_chat_id = ""
        self._conversation: list[dict] = []
        self._chat_buttons: dict[str, QPushButton] = {}
        self._load_all_chats()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root = QHBoxLayout(main_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Nav rail ────────────────────────────────────────────
        nav_rail = QFrame()
        nav_rail.setObjectName("navRail")
        nav_rail.setFixedWidth(64)
        nav_layout = QVBoxLayout(nav_rail)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(0)

        brand = QLabel("AEP")
        brand.setAlignment(Qt.AlignCenter)
        brand.setFont(QFont("SF Pro Display", 11, QFont.Bold))
        brand.setStyleSheet(
            f"color: {_ACCENT}; letter-spacing: 2px; padding: 10px 0 16px 0;"
        )
        nav_layout.addWidget(brand)

        self._nav_buttons: list[QPushButton] = []
        self._tool_stack = QStackedWidget()

        self._add_nav_button(nav_layout, "Report\nAnalysis", 0)
        self._add_nav_button(nav_layout, "Assistant", 1)
        self._add_nav_button(nav_layout, "YouTube\nDownload", 2)
        self._add_nav_button(nav_layout, "Archive Ox\nUploader", 3)
        self._add_nav_button(nav_layout, "CSV\nViewer", 4)

        nav_layout.addStretch()
        root.addWidget(nav_rail)

        # ── Content area (full-width stacked panels) ────────────
        self._tool_stack.addWidget(self._build_report_panel())
        self._tool_stack.addWidget(self._build_assistant_panel())
        self._tool_stack.addWidget(YTDownloaderPanel(self))
        self._tool_stack.addWidget(ArchiveOxPanel(self))
        self.csv_panel = CSVViewerPanel(self)
        self._tool_stack.addWidget(self.csv_panel)
        root.addWidget(self._tool_stack, stretch=1)

        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)

        # Initialize active chat
        if self._chat_sessions:
            self._active_chat_id = self._chat_sessions[0]["id"]
            self.chat_box.setHtml(self._chat_sessions[0].get("html", ""))
            self._chat_title_label.setText(
                self._chat_sessions[0].get("title", "New Chat")
            )
            self._conversation = list(
                self._chat_sessions[0].get("conversation", [])
            )
        else:
            self._active_chat_id = str(_uuid.uuid4())

        self._refresh_chat_list()

    # ── Nav helpers ─────────────────────────────────────────────

    def _add_nav_button(
        self, layout: QVBoxLayout, label: str, index: int
    ) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("navBtn")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(58)
        btn.clicked.connect(lambda: self._switch_panel(index))
        layout.addWidget(btn)
        self._nav_buttons.append(btn)
        return btn

    def _switch_panel(self, index: int) -> None:
        if self._tool_stack.currentIndex() == 1:
            self._save_current_chat()
        self._tool_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    # ── Panel builders ──────────────────────────────────────────

    def _build_report_panel(self) -> QWidget:
        """Full-width panel: 3-column form on top, output log on bottom."""
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {_BG_DEEP};")
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Top: form area (majority of height) ────────────
        form_area = QWidget()
        fa = QVBoxLayout(form_area)
        fa.setContentsMargins(28, 24, 28, 0)
        fa.setSpacing(0)

        header = QLabel("REPORT ANALYSIS")
        header.setFont(QFont("SF Pro Display", 12, QFont.Bold))
        header.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; letter-spacing: 2px; "
            f"padding-bottom: 4px;"
        )
        fa.addWidget(header)

        sub = QLabel("Archival, Music & Effects Reports")
        sub.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px; "
            f"padding-bottom: 10px;"
        )
        fa.addWidget(sub)
        fa.addWidget(_divider())
        fa.addSpacing(20)

        # ── 3-column form grid ──────────────────────────────
        columns = QHBoxLayout()
        columns.setSpacing(28)

        # Column 1 — Frame Rate & Source Files
        col1 = QVBoxLayout()
        col1.setSpacing(0)

        col1.addWidget(_section_label("SEQUENCE FRAME RATE"))
        fps_hint = QLabel("Auto-detected from XML when available")
        fps_hint.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        col1.addWidget(fps_hint)
        col1.addSpacing(6)
        self.fps_combo = QComboBox()
        self.fps_combo.addItems([
            "23.976", "24", "25", "29.97", "30",
            "48", "50", "59.94", "60",
        ])
        self.fps_combo.setCurrentIndex(0)
        self.fps_combo.setEditable(True)
        self.fps_combo.lineEdit().setPlaceholderText("Custom FPS")
        col1.addWidget(self.fps_combo)
        col1.addSpacing(16)

        col1.addWidget(_divider())
        col1.addSpacing(14)

        col1.addWidget(_section_label("SOURCE XML"))
        col1.addSpacing(6)
        self.btn_upload = QPushButton("Choose XML File…")
        self.btn_upload.setObjectName("secondaryBtn")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.clicked.connect(self.select_xml)
        col1.addWidget(self.btn_upload)
        col1.addSpacing(3)
        self.xml_label = _status_label("No file selected")
        col1.addWidget(self.xml_label)
        col1.addSpacing(14)

        col1.addWidget(_section_label("EDL FILES  (OPTIONAL)"))
        col1.addSpacing(6)
        self.btn_edl = QPushButton("Add EDL Files…")
        self.btn_edl.setObjectName("secondaryBtn")
        self.btn_edl.setCursor(Qt.PointingHandCursor)
        self.btn_edl.clicked.connect(self.select_edls)
        col1.addWidget(self.btn_edl)
        col1.addSpacing(3)
        self.edl_label = _status_label("No EDL files added")
        col1.addWidget(self.edl_label)
        col1.addSpacing(14)

        col1.addWidget(_section_label("MUSIC EDL  (OPTIONAL)"))
        col1.addSpacing(6)
        self.btn_music_edl = QPushButton("Choose Music EDL…")
        self.btn_music_edl.setObjectName("secondaryBtn")
        self.btn_music_edl.setCursor(Qt.PointingHandCursor)
        self.btn_music_edl.clicked.connect(self.select_music_edl)
        col1.addWidget(self.btn_music_edl)
        col1.addSpacing(3)
        self.music_edl_label = _status_label(
            "Falls back to main EDLs"
        )
        col1.addWidget(self.music_edl_label)
        col1.addStretch()

        columns.addLayout(col1, stretch=1)

        # Column 2 — Identifiers & Filters
        col2 = QVBoxLayout()
        col2.setSpacing(0)

        col2.addWidget(_section_label("ARCHIVAL IDENTIFIER"))
        col2.addSpacing(6)
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("e.g. OSOS")
        col2.addWidget(self.tag_input)
        col2.addSpacing(16)

        col2.addWidget(_divider())
        col2.addSpacing(14)

        col2.addWidget(_section_label("MUSIC TRACK FILTER"))
        m_hint = QLabel("Only needed when using main EDLs")
        m_hint.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        col2.addWidget(m_hint)
        col2.addSpacing(6)
        m_row = QHBoxLayout()
        m_row.setSpacing(8)
        self.m_start = QLineEdit()
        self.m_end = QLineEdit()
        self.m_start.setPlaceholderText("Start  e.g. A16")
        self.m_end.setPlaceholderText("End  e.g. A17")
        m_row.addWidget(self.m_start)
        m_row.addWidget(self.m_end)
        col2.addLayout(m_row)
        col2.addSpacing(16)

        col2.addWidget(_divider())
        col2.addSpacing(14)

        col2.addWidget(_section_label("EFFECTS VIDEO TRACKS"))
        hint = QLabel("Leave empty to scan all tracks")
        hint.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        col2.addWidget(hint)
        col2.addSpacing(6)
        e_row = QHBoxLayout()
        e_row.setSpacing(8)
        self.e_start = QLineEdit()
        self.e_end = QLineEdit()
        self.e_start.setPlaceholderText("e.g. V1")
        self.e_end.setPlaceholderText("e.g. V4")
        e_row.addWidget(self.e_start)
        e_row.addWidget(self.e_end)
        col2.addLayout(e_row)
        col2.addStretch()

        columns.addLayout(col2, stretch=1)

        # Column 3 — Export
        col3 = QVBoxLayout()
        col3.setSpacing(0)

        col3.addWidget(_section_label("EXPORT DESTINATION"))
        col3.addSpacing(6)
        self.btn_dest = QPushButton("Set Export Folder…")
        self.btn_dest.setObjectName("secondaryBtn")
        self.btn_dest.setCursor(Qt.PointingHandCursor)
        self.btn_dest.clicked.connect(self.select_dest)
        col3.addWidget(self.btn_dest)
        col3.addSpacing(3)
        self.dest_label = _status_label("No folder selected")
        col3.addWidget(self.dest_label)
        col3.addStretch()

        columns.addLayout(col3, stretch=1)

        fa.addLayout(columns)
        fa.addStretch()
        fa.addSpacing(12)

        # ── Action bar ──────────────────────────────────────
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.btn_run = QPushButton("GENERATE REPORTS")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setFixedHeight(46)
        glow = QGraphicsDropShadowEffect()
        glow.setColor(QColor(_ACCENT))
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        self.btn_run.setGraphicsEffect(glow)
        action_bar.addWidget(self.btn_run, stretch=1)

        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setObjectName("secondaryBtn")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedHeight(46)
        self.btn_reset.clicked.connect(self.reset_inputs)
        action_bar.addWidget(self.btn_reset)

        fa.addLayout(action_bar)
        fa.addSpacing(12)

        vbox.addWidget(form_area, stretch=3)

        # ── Bottom: output log ──────────────────────────────
        vbox.addWidget(_divider())

        output_area = QWidget()
        output_area.setStyleSheet(
            f"background-color: {_BG_SURFACE};"
        )
        oa = QVBoxLayout(output_area)
        oa.setContentsMargins(28, 10, 28, 12)
        oa.setSpacing(4)

        log_label = QLabel("OUTPUT")
        log_label.setObjectName("sectionLabel")
        oa.addWidget(log_label)

        self.report_log = QTextEdit()
        self.report_log.setObjectName("chatBox")
        self.report_log.setReadOnly(True)
        self.report_log.setFont(QFont("SF Mono", 12))
        self.report_log.setText(
            "Ready for analysis. Load an XML and generate "
            "reports to begin."
        )
        oa.addWidget(self.report_log, stretch=1)

        vbox.addWidget(output_area, stretch=1)
        return panel

    def _build_assistant_panel(self) -> QWidget:
        """Full-width panel: chat history sidebar (240px) + conversation (stretch)."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left: chat history sidebar ──────────────────────
        history = QFrame()
        history.setObjectName("chatHistoryPanel")
        history.setFixedWidth(240)
        hist_layout = QVBoxLayout(history)
        hist_layout.setContentsMargins(12, 16, 12, 12)
        hist_layout.setSpacing(8)

        hist_header = QLabel("CHATS")
        hist_header.setFont(QFont("SF Pro Display", 10, QFont.Bold))
        hist_header.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; letter-spacing: 2px; padding: 4px 0;"
        )
        hist_layout.addWidget(hist_header)

        btn_new = QPushButton("+ New Chat")
        btn_new.setObjectName("newChatBtn")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setFixedHeight(36)
        btn_new.clicked.connect(self._new_chat)
        hist_layout.addWidget(btn_new)

        hist_layout.addWidget(_divider())

        self._chat_list_scroll = QScrollArea()
        self._chat_list_scroll.setWidgetResizable(True)
        self._chat_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chat_list_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self._chat_list_widget = QWidget()
        self._chat_list_layout = QVBoxLayout(self._chat_list_widget)
        self._chat_list_layout.setContentsMargins(0, 8, 0, 0)
        self._chat_list_layout.setSpacing(2)
        self._chat_list_layout.addStretch()

        self._chat_list_scroll.setWidget(self._chat_list_widget)
        hist_layout.addWidget(self._chat_list_scroll, stretch=1)

        layout.addWidget(history)

        # ── Right: chat conversation ────────────────────────
        content = QWidget()
        content.setObjectName("contentPanel")
        c = QVBoxLayout(content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(0)

        # Provider / model bar
        provider_bar = QWidget()
        provider_bar.setObjectName("providerBar")
        provider_bar.setFixedHeight(46)
        pb = QHBoxLayout(provider_bar)
        pb.setContentsMargins(20, 6, 20, 6)
        pb.setSpacing(10)

        lbl_prov = QLabel("Provider")
        lbl_prov.setObjectName("providerLabel")
        pb.addWidget(lbl_prov)

        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("providerCombo")
        for key in PROVIDER_MODELS:
            self.provider_combo.addItem(PROVIDER_LABELS[key], key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        pb.addWidget(self.provider_combo)

        lbl_model = QLabel("Model")
        lbl_model.setObjectName("providerLabel")
        pb.addWidget(lbl_model)

        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self.model_combo.setEditable(True)
        self._populate_model_combo("ollama")
        pb.addWidget(self.model_combo)

        pb.addStretch()

        self.btn_api_key = QPushButton("API Key")
        self.btn_api_key.setObjectName("apiKeyBtn")
        self.btn_api_key.setCursor(Qt.PointingHandCursor)
        self.btn_api_key.clicked.connect(self._manage_api_key)
        pb.addWidget(self.btn_api_key)
        self._refresh_key_indicator()

        c.addWidget(provider_bar)

        # Chat title header
        chat_header = QWidget()
        chat_header.setFixedHeight(42)
        chat_header.setStyleSheet(
            f"background-color: {_BG_SIDEBAR}; "
            f"border-bottom: 1px solid {_BORDER};"
        )
        ch_layout = QHBoxLayout(chat_header)
        ch_layout.setContentsMargins(20, 0, 20, 0)
        self._chat_title_label = QLabel("New Chat")
        self._chat_title_label.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;"
        )
        ch_layout.addWidget(self._chat_title_label)
        ch_layout.addStretch()
        c.addWidget(chat_header)

        chat_wrap = QWidget()
        chat_wrap.setStyleSheet(f"background-color: {_BG_DEEP};")
        cw = QVBoxLayout(chat_wrap)
        cw.setContentsMargins(20, 16, 20, 8)

        self.chat_box = QTextEdit()
        self.chat_box.setObjectName("chatBox")
        self.chat_box.setReadOnly(True)
        self.chat_box.setFont(QFont("SF Mono", 12))
        self.chat_box.setText(
            "Send a message to start chatting."
        )
        cw.addWidget(self.chat_box, stretch=1)
        c.addWidget(chat_wrap, stretch=1)

        # Input bar
        self.attached_files: list[str] = []

        input_bar = QWidget()
        input_bar.setStyleSheet(
            f"background-color: {_BG_SIDEBAR}; "
            f"border-top: 1px solid {_BORDER};"
        )
        ib = QVBoxLayout(input_bar)
        ib.setContentsMargins(20, 14, 20, 14)
        ib.setSpacing(8)

        self._chips_widget = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._chips_widget.setVisible(False)
        ib.addWidget(self._chips_widget)

        self.chat_input = ChatInput()
        self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText(
            "Ask a question…  (Enter to send, Shift+Enter for newline)"
        )
        self.chat_input.setMaximumHeight(100)
        self.chat_input.setFont(QFont("SF Pro Text", 13))
        ib.addWidget(self.chat_input)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_attach = QPushButton("Attach File…")
        self.btn_attach.setObjectName("attachBtn")
        self.btn_attach.setCursor(Qt.PointingHandCursor)
        self.btn_attach.clicked.connect(self.attach_file)
        action_row.addWidget(self.btn_attach)

        action_row.addStretch()

        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("sendBtn")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        action_row.addWidget(self.btn_send)
        ib.addLayout(action_row)

        c.addWidget(input_bar)
        layout.addWidget(content, stretch=1)
        return panel

    # ── Provider / model helpers ──────────────────────────────

    def _populate_model_combo(self, provider_key: str) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if provider_key == "ollama":
            models = fetch_ollama_models()
        else:
            models = PROVIDER_MODELS.get(provider_key, [])
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.blockSignals(False)

    def _on_provider_changed(self, index: int) -> None:
        key = self.provider_combo.currentData()
        self._populate_model_combo(key or "ollama")
        self._refresh_key_indicator()

    def _refresh_key_indicator(self) -> None:
        """Update API Key button to show whether a key is stored."""
        provider = self.provider_combo.currentData() or "ollama"
        if provider == "ollama":
            self.btn_api_key.setText("Local")
            self.btn_api_key.setProperty("hasKey", True)
            self.btn_api_key.setEnabled(False)
        else:
            has = bool(get_key(provider))
            self.btn_api_key.setText("API Key ✓" if has else "API Key")
            self.btn_api_key.setProperty("hasKey", has)
            self.btn_api_key.setEnabled(True)
        self.btn_api_key.style().unpolish(self.btn_api_key)
        self.btn_api_key.style().polish(self.btn_api_key)

    def _manage_api_key(self) -> None:
        provider = self.provider_combo.currentData() or "ollama"
        if provider == "ollama":
            return
        label = PROVIDER_LABELS.get(provider, provider)
        current = get_key(provider)

        from PySide6.QtWidgets import QInputDialog

        key, ok = QInputDialog.getText(
            self,
            f"{label} API Key",
            f"Enter your {label} API key:\n"
            "(leave blank to remove)",
            QLineEdit.Password,
            current,
        )
        if ok:
            set_key(provider, key.strip())
            self._refresh_key_indicator()

    def get_provider(self) -> str:
        return self.provider_combo.currentData() or "ollama"

    def get_model(self) -> str:
        return self.model_combo.currentText().strip()

    # ── Chat history methods ─────────────────────────────────

    def _load_all_chats(self) -> None:
        """Load all saved chat sessions from disk."""
        self._chat_sessions = []
        if not _CHAT_DIR.exists():
            return
        for f in sorted(
            _CHAT_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._chat_sessions.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    def _save_current_chat(self) -> None:
        """Persist the active chat session to disk."""
        if not self._active_chat_id:
            return
        plain = self.chat_box.toPlainText().strip()
        if not plain or plain == "Send a message to start chatting.":
            return

        title = self._auto_title()
        html = self.chat_box.toHtml()
        conversation = getattr(self, "_conversation", [])
        data = {
            "id": self._active_chat_id,
            "title": title,
            "html": html,
            "conversation": conversation,
            "provider": self.get_provider(),
            "model": self.get_model(),
            "created": datetime.now().isoformat(),
        }

        found = False
        for i, s in enumerate(self._chat_sessions):
            if s["id"] == self._active_chat_id:
                self._chat_sessions[i] = data
                found = True
                break
        if not found:
            self._chat_sessions.insert(0, data)

        _CHAT_DIR.mkdir(parents=True, exist_ok=True)
        path = _CHAT_DIR / f"{self._active_chat_id}.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        self._refresh_chat_list()

    def _new_chat(self) -> None:
        """Start a fresh chat session, saving the current one first."""
        if self._active_chat_id:
            self._save_current_chat()
        self._active_chat_id = str(_uuid.uuid4())
        self._conversation = []
        self.chat_box.clear()
        self.chat_box.setText("Send a message to start chatting.")
        self._chat_title_label.setText("New Chat")
        self._refresh_chat_list()

    def _load_chat(self, chat_id: str) -> None:
        """Switch to a previously saved chat."""
        if chat_id == self._active_chat_id:
            return
        self._save_current_chat()
        for session in self._chat_sessions:
            if session["id"] == chat_id:
                self._active_chat_id = chat_id
                self.chat_box.setHtml(session.get("html", ""))
                self._chat_title_label.setText(
                    session.get("title", "Chat")
                )
                self._conversation = list(
                    session.get("conversation", [])
                )
                break
        self._refresh_chat_list()

    def _auto_title(self) -> str:
        """Derive a title from the first user message in the chat."""
        text = self.chat_box.toPlainText().strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("You:"):
                title = line[4:].strip()[:50]
                return title if title else "New Chat"
        return "New Chat"

    def _refresh_chat_list(self) -> None:
        """Rebuild the chat history buttons in the sidebar."""
        if not hasattr(self, "_chat_list_layout"):
            return

        while self._chat_list_layout.count() > 0:
            item = self._chat_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._chat_buttons.clear()

        for session in self._chat_sessions:
            chat_id = session["id"]
            title = session.get("title", "New Chat")
            btn = QPushButton(title)
            btn.setObjectName("chatHistoryItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(chat_id == self._active_chat_id)
            btn.clicked.connect(
                lambda _, cid=chat_id: self._load_chat(cid)
            )
            self._chat_list_layout.addWidget(btn)
            self._chat_buttons[chat_id] = btn

        self._chat_list_layout.addStretch()

    def closeEvent(self, event):
        self._save_current_chat()
        super().closeEvent(event)

    # ── File selection & utility methods ─────────────────────

    def select_xml(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Premiere XML", "", "XML Files (*.xml)"
        )
        if path:
            self.xml_path = path
            self.xml_label.setText(os.path.basename(path))

    def select_music_edl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Music EDL", "", "EDL Files (*.edl);;All Files (*)"
        )
        if path:
            self.music_edl_path = path
            self.music_edl_label.setText(os.path.basename(path))

    def select_edls(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select EDL Files", "", "EDL Files (*.edl);;All Files (*)"
        )
        for p in paths:
            if p not in self.edl_paths:
                self.edl_paths.append(p)
        if self.edl_paths:
            names = [os.path.basename(p) for p in self.edl_paths]
            self.edl_label.setText(", ".join(names))
        else:
            self.edl_label.setText("No EDL files added")

    def select_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if path:
            self.export_folder = path
            self.dest_label.setText(path)

    def attach_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach Files",
            "",
            "All supported (*.png *.jpg *.jpeg *.gif *.webp *.csv *.txt "
            "*.xml *.json *.md *.log *.tsv *.srt);;"
            "Images (*.png *.jpg *.jpeg *.gif *.webp);;"
            "Text / Data (*.csv *.txt *.xml *.json *.md *.log *.tsv *.srt);;"
            "All files (*)",
        )
        for p in paths:
            if p not in self.attached_files:
                self.attached_files.append(p)
        self._rebuild_chips()

    def _remove_attachment(self, path: str) -> None:
        if path in self.attached_files:
            self.attached_files.remove(path)
        self._rebuild_chips()

    def _rebuild_chips(self) -> None:
        while self._chips_layout.count() > 0:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for filepath in self.attached_files:
            name = os.path.basename(filepath)
            chip = QPushButton(f"  {name}  ✕")
            chip.setObjectName("chipBtn")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(f"Click to remove: {filepath}")
            chip.clicked.connect(
                lambda _=False, p=filepath: self._remove_attachment(p)
            )
            self._chips_layout.addWidget(chip)

        self._chips_layout.addStretch()
        self._chips_widget.setVisible(len(self.attached_files) > 0)

    def get_selected_fps(self) -> float:
        """Return the frame rate selected in the combo box."""
        text = self.fps_combo.currentText().strip()
        try:
            return float(text)
        except ValueError:
            return 23.976

    def open_csv_viewer(self, path: str | None = None) -> None:
        """Switch to the CSV Viewer panel and optionally open a file."""
        self._switch_panel(4)
        if path:
            self.csv_panel.open_csv(path)

    def reset_inputs(self) -> None:
        """Clear all source inputs and status labels for a fresh run."""
        self.xml_path = ""
        self.xml_label.setText("No file selected")

        self.edl_paths.clear()
        self.edl_label.setText("No EDL files added")

        self.music_edl_path = ""
        self.music_edl_label.setText("Optional — falls back to main EDLs")

        self.fps_combo.setCurrentIndex(0)

        self.tag_input.clear()
        self.m_start.clear()
        self.m_end.clear()
        self.e_start.clear()
        self.e_end.clear()

        self.export_folder = ""
        self.dest_label.setText("No folder selected")

        self.report_log.clear()
        self.report_log.setText(
            "Inputs cleared — ready for a new session."
        )


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = AssistantEditorPro()
    window.show()
    sys.exit(app.exec())
