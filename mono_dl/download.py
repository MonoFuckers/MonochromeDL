from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import album_artist, build_filename, build_folder, ensure_dir, track_artist, track_title


def tag_audio(path: Path, track: dict[str, Any], album: dict[str, Any] | None = None) -> None:
    try:
        from mutagen.flac import FLAC
        from mutagen.id3 import ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK
        from mutagen.mp3 import MP3
    except ImportError:
        return

    album_obj = album or track.get("album") or {}
    title = track_title(track)
    artist = track_artist(track)
    album_title = album_obj.get("title") or "Unknown Album"
    album_art = album_artist(album_obj if album else {"artist": track.get("artist")}, track)
    release = (album or {}).get("releaseDate") or album_obj.get("releaseDate") or ""
    track_no = track.get("trackNumber")

    suffix = path.suffix.lower()
    if suffix == ".flac":
        audio = FLAC(path)
        audio["title"] = title
        audio["artist"] = artist
        audio["album"] = album_title
        audio["albumartist"] = album_art
        if release:
            audio["date"] = release[:10]
        if track_no:
            audio["tracknumber"] = str(track_no)
        isrc = track.get("isrc")
        if isrc:
            audio["isrc"] = isrc
        audio.save()
    elif suffix == ".mp3":
        try:
            audio = MP3(path, ID3=ID3)
        except Exception:
            return
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall("TIT2")
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(TPE2(encoding=3, text=album_art))
        audio.tags.add(TALB(encoding=3, text=album_title))
        if release:
            audio.tags.add(TDRC(encoding=3, text=release[:10]))
        if track_no:
            audio.tags.add(TRCK(encoding=3, text=str(track_no)))
        audio.tags.add(TCON(encoding=3, text="Music"))
        audio.save()


def download_track_file(
    resolver,
    track: dict[str, Any],
    out_dir: Path,
    *,
    provider: str = "auto",
    quality: str = "lossless",
    album: dict[str, Any] | None = None,
    folder_template: str | None = None,
    filename_template: str | None = None,
    skip_existing: bool = True,
) -> Path:
    if album:
        sub = build_folder(album, track, folder_template)
        target_dir = ensure_dir(out_dir / sub)
    else:
        target_dir = ensure_dir(out_dir)

    stream = resolver.resolve(track, provider=provider, quality=quality)
    filename = build_filename(track, stream.ext, filename_template)
    dest = target_dir / filename

    if skip_existing and dest.exists() and dest.stat().st_size > 0:
        return dest

    temp = dest.with_suffix(dest.suffix + ".part")
    resolver.download_stream(stream, str(temp))
    if temp.exists():
        if dest.exists():
            dest.unlink()
        temp.rename(dest)

    tag_audio(dest, track, album)
    return dest
