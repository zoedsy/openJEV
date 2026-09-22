"""Explicit settings for local inference or an remote GPU service."""

import os
from dataclasses import dataclass
from pathlib import Path

MODEL_ID = "onnx-community/multilingual-MiniLMv2-L6-mnli-xnli-ONNX"
MODEL_REVISION = "ca5daf3d11b6c4b3143b1f4602a2edfb64c3ad7e"
MODEL_SHA256 = "55614f3c7da74184742eaa0006b978744437aa91de9ba4913db42f94d7844a8f"


@dataclass(frozen=True)
class Settings:
    backend: str = "nli"
    kev_url: str = "http://127.0.0.1:8009"
    diffusion_url: str = "http://127.0.0.1:8008"
    diffusion_max_tokens: int = 8192
    relay_command: str = ""
    relay_identity_file: str = "/data/openjev/status.json"
    model_id: str = MODEL_ID
    revision: str = MODEL_REVISION
    device: str = "cpu"
    max_tokens: int = 512
    api_key: str = ""
    offline: bool = False
    cache_dir: str = ".models"

    @classmethod
    def from_env(cls):
        backend = os.getenv("OPENJEV_BACKEND", "nli")
        if backend not in {"nli", "kev", "diffusiongemma"}:
            raise ValueError("OPENJEV_BACKEND must be nli, kev or diffusiongemma")
        return cls(
            backend=backend,
            kev_url=os.getenv("OPENJEV_KEV_URL", "http://127.0.0.1:8009"),
            relay_command=os.getenv("OPENJEV_RELAY_COMMAND", ""),
            relay_identity_file=os.getenv("OPENJEV_RELAY_IDENTITY_FILE", "/data/openjev/status.json"),
            diffusion_url=os.getenv("OPENJEV_DIFFUSION_URL", "http://127.0.0.1:8008"),
            diffusion_max_tokens=int(os.getenv("OPENJEV_DIFFUSION_MAX_TOKENS", "8192")),
            model_id=os.getenv("OPENJEV_MODEL", MODEL_ID),
            revision=os.getenv("OPENJEV_REVISION", MODEL_REVISION),
            device=os.getenv("OPENJEV_DEVICE", "cpu"),
            api_key=os.getenv("OPENJEV_API_KEY", ""),
            offline=os.getenv("OPENJEV_OFFLINE", "0") == "1",
            cache_dir=str(Path(os.getenv("OPENJEV_CACHE_DIR", ".models")).resolve()),
        )
