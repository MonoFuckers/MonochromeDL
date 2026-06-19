from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def sanitize_filename(value: str | None) -> str:
    if not value:
        return "Unknown"
    return re.sub(r'[\\/:*?"<>|]', "_", value).strip() or "Unknown"


def track_title(track: dict[str, Any]) -> str:
    title = track.get("title") or "Unknown Title"
    version = track.get("version")
    if version:
        return f"{title} ({version})"
    return title


def track_artist(track: dict[str, Any]) -> str:
    artist = track.get("artist") or {}
    if artist.get("name"):
        return artist["name"]
    artists = track.get("artists") or []
    if artists and artists[0].get("name"):
        return artists[0]["name"]
    return "Unknown Artist"


def album_artist(album: dict[str, Any], fallback_track: dict[str, Any] | None = None) -> str:
    artist = album.get("artist") or {}
    if artist.get("name"):
        return artist["name"]
    if fallback_track:
        return track_artist(fallback_track)
    return "Unknown Artist"


def format_template(template: str, data: dict[str, Any]) -> str:
    result = template
    for key, value in data.items():
        result = result.replace(f"{{{key}}}", sanitize_filename(str(value) if value is not None else ""))
    return result


def build_filename(track: dict[str, Any], ext: str, template: str | None = None) -> str:
    tpl = template or "{trackNumber} - {artist} - {title}"
    track_number = int(track.get("trackNumber") or track.get("track_number") or 0)
    data = {
        "trackNumber": f"{track_number:02d}",
        "artist": track_artist(track),
        "title": track_title(track),
        "album": (track.get("album") or {}).get("title") or "Unknown Album",
        "discNumber": str(track.get("volumeNumber") or track.get("discNumber") or 1),
    }
    name = format_template(tpl, data)
    return f"{name}.{ext.lstrip('.')}"


def build_folder(album: dict[str, Any], track: dict[str, Any] | None, template: str | None = None) -> str:
    tpl = template or "{albumTitle} - {albumArtist}"
    release = album.get("releaseDate") or ""
    year = release[:4] if release else ""
    data = {
        "albumTitle": album.get("title") or "Unknown Album",
        "albumArtist": album_artist(album, track),
        "year": year,
    }
    return format_template(tpl, data)


def parse_monochrome_url(url: str) -> tuple[str, str]:
    """Return (kind, id) for monochrome.tf URLs."""
    patterns = [
        (r"monochrome\.tf/album/(\d+)", "album"),
        (r"monochrome\.tf/track/(\d+)", "track"),
        (r"monochrome\.tf/playlist/([0-9a-f-]+)", "playlist"),
        (r"monochrome\.tf/artist/(\d+)", "artist"),
    ]
    for pattern, kind in patterns:
        match = re.search(pattern, url, re.I)
        if match:
            return kind, match.group(1)
    raise ValueError(f"Unsupported Monochrome URL: {url}")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
