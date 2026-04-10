import os
from dataclasses import dataclass

@dataclass
class AppSettings:
    OLLAMA_HOST = os.getenv("MINI_IP", "localhost")
    OLLAMA_PORT = "11434"
    
    # Default fallback values if the user leaves UI fields blank
    DEFAULT_FPS: float = 23.976
    DEFAULT_ARCHIVAL_TAG: str = "" # No longer hardcoded to OSOS
    
    # Technical constants
    SUPPORTED_AUDIO: tuple = ('.wav', '.mp3', '.aif', '.aiff', '.m4a')

    @property
    def ollama_url(self) -> str:
        return f"http://{self.OLLAMA_HOST}:{self.OLLAMA_PORT}/api/generate"

# Global settings instance
settings = AppSettings()


def ollama_base_url() -> str:
    """Scheme + host + port (no path), for `/api/chat` or `/api/generate`."""
    return f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}".rstrip("/")


def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "gemma4:26b")