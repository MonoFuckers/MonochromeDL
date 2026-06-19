from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_API_INSTANCES = [
    "https://us-west.monochrome.tf",
    "https://api.monochrome.tf",
    "https://eu-central.monochrome.tf",
    "https://arran.monochrome.tf",
    "https://monochrome-api.samidy.com",
    "https://triton.squid.wtf",
    "https://wolf.qqdl.site",
    "https://maus.qqdl.site",
    "https://vogel.qqdl.site",
    "https://hund.qqdl.site",
    "https://tidal.kinoplus.online",
]

TIDAL_PROXY = "https://tidal-proxy.monochrome.tf"
DEEZER_API = "https://dzr.tabs-vs-spaces.wtf"
QOBUZ_API = "https://qobuz.kennyy.com.br"


def load_api_instances() -> list[str]:
    candidates: list[Path] = []
    env_path = os.environ.get("MONO_DL_INSTANCES")
    if env_path:
        candidates.append(Path(env_path))
    here = Path(__file__).resolve().parent
    candidates.append(here.parent.parent / "monochrome" / "public" / "instances.json")

    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            api = data.get("api") or []
            cleaned = [str(u).rstrip("/") for u in api if u]
            if cleaned:
                return cleaned
        except (OSError, json.JSONDecodeError):
            continue
    return DEFAULT_API_INSTANCES.copy()
