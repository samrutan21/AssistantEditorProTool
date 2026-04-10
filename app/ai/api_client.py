"""Unified LLM chat client — background QThread worker for the UI.

Supported providers:
  - ollama   (local, no API key)
  - claude   (Anthropic Messages API)
  - openai   (OpenAI Chat Completions API)
  - gemini   (Google Generative Language API)
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import requests
from PySide6.QtCore import QThread, Signal

from app.core.config import ollama_base_url, ollama_model

# ── image helpers ─────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def prepare_attachments(
    file_paths: list[str],
) -> tuple[list[dict], list[str]]:
    """Split file paths into image dicts and text-file contents.

    Returns ``(images, file_texts)`` where each image is
    ``{"b64": <base64-str>, "mime": <mime-type>}``.
    """
    images: list[dict] = []
    file_texts: list[str] = []

    for fp in file_paths:
        p = Path(fp)
        ext = p.suffix.lower()
        if ext in _IMAGE_EXTS:
            try:
                raw = p.read_bytes()
                images.append({
                    "b64": base64.b64encode(raw).decode("ascii"),
                    "mime": _MIME_MAP.get(ext, "image/png"),
                })
            except OSError:
                file_texts.append(f"[Could not read image: {p.name}]")
        else:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                file_texts.append(f"### File: {p.name}\n{text}")
            except OSError:
                file_texts.append(f"[Could not read file: {p.name}]")

    return images, file_texts


# ── default models per provider ──────────────────────────────

def fetch_ollama_models() -> list[str]:
    """Query the local Ollama server for all pulled models.

    Returns model names sorted with the user's configured default first.
    Falls back to just the configured model if the server is unreachable.
    """
    configured = ollama_model()
    try:
        resp = requests.get(
            f"{ollama_base_url()}/api/tags", timeout=3
        )
        resp.raise_for_status()
        models = [
            m["name"]
            for m in resp.json().get("models", [])
            if m.get("name")
        ]
        if not models:
            return [configured]
        if configured in models:
            models.remove(configured)
            models.insert(0, configured)
        return models
    except Exception:  # noqa: BLE001
        return [configured]


PROVIDER_MODELS: dict[str, list[str]] = {
    "ollama": fetch_ollama_models(),
    "claude": [
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
}

PROVIDER_LABELS: dict[str, str] = {
    "ollama": "Ollama (Local)",
    "claude": "Claude",
    "openai": "OpenAI",
    "gemini": "Gemini",
}

_REQUEST_TIMEOUT = 180  # seconds


# ── worker ────────────────────────────────────────────────────

class ChatWorker(QThread):
    """Sends a single chat turn to the selected LLM provider off-thread."""

    response_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str = "",
        prompt: str,
        conversation: list[dict] | None = None,
        images: list[dict] | None = None,
        file_texts: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.prompt = prompt
        self.conversation = conversation or []
        self.images = images or []
        self.file_texts = file_texts or []

    # ── entry point ───────────────────────────────────────────

    def run(self) -> None:
        try:
            sender = _SENDERS.get(self.provider)
            if sender is None:
                self.error_occurred.emit(
                    f"Unknown provider: {self.provider}"
                )
                return
            text = sender(self)
            self.response_received.emit(text)
        except requests.exceptions.RequestException as exc:
            self.error_occurred.emit(f"Connection error: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))


# ── provider-specific senders ─────────────────────────────────

def _build_content(prompt: str, file_texts: list[str]) -> str:
    """Merge file-text attachments into the user prompt."""
    if not file_texts:
        return prompt
    preamble = "\n\n---\n".join(file_texts)
    return (
        f"{preamble}\n\n---\n\n"
        f"Given the attached file contents above, {prompt}"
    )


def _send_ollama(w: ChatWorker) -> str:
    content = _build_content(w.prompt, w.file_texts)
    messages: list[dict[str, Any]] = [
        {"role": m["role"], "content": m["content"]}
        for m in w.conversation
    ]
    msg: dict[str, Any] = {"role": "user", "content": content}
    if w.images:
        msg["images"] = [img["b64"] for img in w.images]
    messages.append(msg)

    url = f"{ollama_base_url()}/api/chat"
    payload = {
        "model": w.model or ollama_model(),
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 16384},
    }
    resp = requests.post(url, json=payload, timeout=_REQUEST_TIMEOUT)
    if not resp.ok:
        try:
            body = resp.json()
            detail = body.get("error", f"HTTP {resp.status_code}")
        except (ValueError, KeyError):
            detail = f"HTTP {resp.status_code}"
        raise RuntimeError(f"Ollama error: {detail}")
    data = resp.json()
    return data.get("message", {}).get("content", "No response from model.")


def _send_claude(w: ChatWorker) -> str:
    if not w.api_key:
        raise ValueError("No API key set for Claude.")

    system_prompt = (
        "You are a professional creative-workflow assistant for film, "
        "television, and post-production. Answer clearly and thoroughly."
    )

    messages: list[dict] = []
    for m in w.conversation:
        messages.append({"role": m["role"], "content": m["content"]})

    content_parts: list[dict] = []
    user_text = _build_content(w.prompt, w.file_texts)
    if user_text:
        content_parts.append({"type": "text", "text": user_text})
    for img in w.images:
        content_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["mime"],
                "data": img["b64"],
            },
        })
    messages.append({"role": "user", "content": content_parts})

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": w.api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": w.model,
            "system": system_prompt,
            "max_tokens": 4096,
            "messages": messages,
        },
        timeout=_REQUEST_TIMEOUT,
    )
    if not resp.ok:
        _raise_api_error("Claude", resp)
    data = resp.json()
    parts = data.get("content", [])
    return "".join(p.get("text", "") for p in parts) or "No response."


def _send_openai(w: ChatWorker) -> str:
    if not w.api_key:
        raise ValueError("No API key set for OpenAI.")

    system_prompt = (
        "You are a professional creative-workflow assistant for film, "
        "television, and post-production. Answer clearly and thoroughly."
    )

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in w.conversation:
        messages.append({"role": m["role"], "content": m["content"]})

    user_text = _build_content(w.prompt, w.file_texts)
    if w.images:
        content: list[dict] = []
        if user_text:
            content.append({"type": "text", "text": user_text})
        for img in w.images:
            data_url = f"data:{img['mime']};base64,{img['b64']}"
            content.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_text})

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {w.api_key}",
        },
        json={
            "model": w.model,
            "messages": messages,
            "max_tokens": 4096,
        },
        timeout=_REQUEST_TIMEOUT,
    )
    if not resp.ok:
        _raise_api_error("OpenAI", resp)
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _send_gemini(w: ChatWorker) -> str:
    if not w.api_key:
        raise ValueError("No API key set for Gemini.")

    system_text = (
        "You are a professional creative-workflow assistant for film, "
        "television, and post-production. Answer clearly and thoroughly."
    )
    user_text = _build_content(w.prompt, w.file_texts)

    contents: list[dict] = []
    for m in w.conversation:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    parts: list[dict] = []
    if user_text:
        parts.append({"text": user_text})
    for img in w.images:
        parts.append({
            "inline_data": {
                "mime_type": img["mime"],
                "data": img["b64"],
            }
        })
    contents.append({"role": "user", "parts": parts})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{w.model}:generateContent?key={w.api_key}"
    )
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 4096},
        },
        timeout=_REQUEST_TIMEOUT,
    )
    if not resp.ok:
        _raise_api_error("Gemini", resp)
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        text_parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in text_parts) or "No response."
    return "No response from Gemini."


# ── error helper ──────────────────────────────────────────────

def _raise_api_error(provider: str, resp: requests.Response) -> None:
    try:
        body = resp.json()
    except (ValueError, KeyError):
        body = {}

    if provider == "Claude":
        msg = (body.get("error", {}) or {}).get("message", "")
    elif provider == "OpenAI":
        msg = (body.get("error", {}) or {}).get("message", "")
    elif provider == "Gemini":
        msg = (body.get("error", {}) or {}).get("message", "")
    else:
        msg = ""

    detail = msg or f"HTTP {resp.status_code}"
    raise RuntimeError(f"{provider} API error: {detail}")


_SENDERS = {
    "ollama": _send_ollama,
    "claude": _send_claude,
    "openai": _send_openai,
    "gemini": _send_gemini,
}
