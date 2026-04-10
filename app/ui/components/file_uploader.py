"""File picker for project XML or media lists."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget


class FileUploader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self._label = QLabel("No file selected")
        self._label.setWordWrap(True)
        btn = QPushButton("Choose XML…")
        btn.clicked.connect(self._pick_file)
        row = QHBoxLayout(self)
        row.addWidget(btn, 0)
        row.addWidget(self._label, 1)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open project XML",
            "",
            "XML files (*.xml);;All files (*)",
        )
        if path:
            self._path = Path(path)
            self._label.setText(str(self._path))

    def selected_path(self) -> Path | None:
        return self._path
