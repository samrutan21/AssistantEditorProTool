"""Simple read-only / append log widget for assistant messages."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class ChatBox(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText("Assistant output will appear here…")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._text)

    def append(self, message: str) -> None:
        self._text.appendPlainText(message)

    def clear(self) -> None:
        self._text.clear()
