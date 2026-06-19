from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Literal
from urllib.parse import quote

import httpx

from .config import DEEZER_API, QOBUZ_API

ProviderName = Literal["auto", "deezer", "qobuz"]
QualityName = Literal["lossless", "high", "low"]


@dataclass
class StreamResult:
    url: str
    provider: str
    ext: str
    headers: dict[str, str] | None = None


class StreamResolver:
    BROWSER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Referer": "https://monochrome.tf/",
        "Origin": "https://monochrome.tf",
    }

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.deezer_base = os.environ.get("MONO_DL_DEEZER_API", DEEZER_API).rstrip("/")
        self.qobuz_base = os.environ.get("MONO_DL_QOBUZ_API", QOBUZ_API).rstrip("/")

    def resolve(self, track: dict[str, Any], provider: ProviderName = "auto", quality: QualityName = "lossless") -> StreamResult:
        isrc = (track.get("isrc") or "").strip()
        order: list[str]
        if provider == "auto":
            order = ["deezer", "qobuz"]
        else:
            order = [provider]

        errors: list[str] = []
        for name in order:
            try:
                if name == "deezer":
                    if not isrc:
                        raise ValueError("missing ISRC")
                    return self._deezer(isrc, quality)
                if name == "qobuz":
                    if not isrc:
                        raise ValueError("missing ISRC")
                    return self._qobuz(isrc, quality)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
        raise RuntimeError("No stream source available — " + "; ".join(errors))

    def _deezer_format(self, quality: QualityName) -> str:
        if quality == "high":
            return "MP3_320"
        if quality == "low":
            return "MP3_128"
        return "FLAC"

    def _deezer_ext(self, fmt: str) -> str:
        return "mp3" if fmt.startswith("MP3") else "flac"

    def _deezer(self, isrc: str, quality: QualityName) -> StreamResult:
        fmt = self._deezer_format(quality)
        url = f"{self.deezer_base}/stream/?isrc={quote(isrc, safe='')}&format={fmt}"
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=self.BROWSER_HEADERS) as client:
            response = client.get(url, headers={"Range": "bytes=0-0"})
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}")
        return StreamResult(url=url, provider="deezer", ext=self._deezer_ext(fmt), headers=self.BROWSER_HEADERS)

    def _qobuz_quality(self, quality: QualityName) -> str:
        if quality == "high":
            return "5"
        if quality == "low":
            return "5"
        return "6"

    def _qobuz(self, isrc: str, quality: QualityName) -> StreamResult:
        with httpx.Client(timeout=self.timeout) as client:
            search = client.get(f"{self.qobuz_base}/api/get-music", params={"q": isrc, "offset": 0})
            search.raise_for_status()
            payload = search.json()
            tracks = (payload.get("data") or {}).get("tracks", {}).get("items") or []
            match = next((t for t in tracks if (t.get("isrc") or "").lower() == isrc.lower()), None)
            if not match and tracks:
                match = tracks[0]
            if not match or not match.get("id"):
                raise RuntimeError("no Qobuz match")

            q = self._qobuz_quality(quality)
            stream = client.get(
                f"{self.qobuz_base}/api/download-music",
                params={"track_id": match["id"], "quality": q},
            )
            stream.raise_for_status()
            stream_json = stream.json()
            url = (stream_json.get("data") or {}).get("url")
            if not url:
                raise RuntimeError("empty stream URL")
        ext = "flac" if q in {"6", "27"} else "mp3"
        return StreamResult(url=url, provider="qobuz", ext=ext)

    def download_stream(
        self,
        stream: StreamResult,
        dest: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> str:
        with httpx.Client(timeout=None, follow_redirects=True, headers=self.BROWSER_HEADERS) as client:
            req_headers = {**(stream.headers or {}), **self.BROWSER_HEADERS}
            with client.stream("GET", stream.url, headers=req_headers) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or 0)
                downloaded = 0
                with open(dest, "wb") as handle:
                    for chunk in response.iter_bytes(1024 * 256):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(downloaded, total)
        return dest
