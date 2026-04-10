"""Ollama client: background QThread worker for the UI."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from app.core.config import ollama_base_url, ollama_model

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class GemmaWorker(QThread):
    """Runs Ollama `/api/chat` off the UI thread with optional file attachments."""

    response_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
        file_texts: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.prompt = prompt
        self.model = model or ollama_model()
        self.images = images or []
        self.file_texts = file_texts or []

    def run(self) -> None:
        content = self.prompt
        if self.file_texts:
            preamble = "\n\n---\n".join(self.file_texts)
            content = (
                f"{preamble}\n\n---\n\n"
                f"Given the attached file contents above, {self.prompt}"
            )

        message: dict = {"role": "user", "content": content}
        if self.images:
            message["images"] = self.images

        url = f"{ollama_base_url()}/api/chat"
        payload = {
            "model": self.model,
            "messages": [message],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 16384,
            },
        }
        try:
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            data = response.json()
            msg = data.get("message") or {}
            text = msg.get("content", "No response content from model.")
            self.response_received.emit(str(text))
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Connection error: {e}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.error_occurred.emit(f"Bad response format: {e}")


def prepare_attachments(
    file_paths: list[str],
) -> tuple[list[str], list[str]]:
    """
    Split a list of file paths into base64 image strings and text-file contents.
    Returns (images_b64, file_texts).
    """
    images_b64: list[str] = []
    file_texts: list[str] = []

    for fp in file_paths:
        p = Path(fp)
        ext = p.suffix.lower()
        if ext in _IMAGE_EXTS:
            try:
                raw = p.read_bytes()
                images_b64.append(base64.b64encode(raw).decode("ascii"))
            except OSError:
                file_texts.append(f"[Could not read image: {p.name}]")
        else:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                file_texts.append(f"### File: {p.name}\n{text}")
            except OSError:
                file_texts.append(f"[Could not read file: {p.name}]")

    return images_b64, file_texts
