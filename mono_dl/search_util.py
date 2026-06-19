from __future__ import annotations

from typing import Any

from .util import track_artist, track_title


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "??:??"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def print_search_results(
    results: dict[str, list[dict[str, Any]]], *, show_types: set[str] | None = None
) -> list[tuple[str, dict[str, Any]]]:
    types = show_types or {"tracks", "albums", "artists", "playlists"}
    index = 1
    index_map: list[tuple[str, dict[str, Any]]] = []

    if "tracks" in types and results.get("tracks"):
        print("\nTracks:")
        for item in results["tracks"]:
            artist = track_artist(item)
            album = (item.get("album") or {}).get("title") or "?"
            dur = format_duration(item.get("duration"))
            print(f"  [{index}] {track_title(item)} — {artist} ({album}) [{dur}] id={item.get('id')}")
            index_map.append(("track", item))
            index += 1

    if "albums" in types and results.get("albums"):
        print("\nAlbums:")
        for item in results["albums"]:
            artist_obj = item.get("artist") or {}
            artist = artist_obj.get("name") if isinstance(artist_obj, dict) else str(artist_obj or "?")
            if not artist or artist == "?":
                artists = item.get("artists") or []
                if artists:
                    artist = artists[0].get("name", "?")
            n = item.get("numberOfTracks") or "?"
            print(f"  [{index}] {item.get('title')} — {artist} ({n} tracks) id={item.get('id')}")
            index_map.append(("album", item))
            index += 1

    if "artists" in types and results.get("artists"):
        print("\nArtists:")
        for item in results["artists"]:
            print(f"  [{index}] {item.get('name')} id={item.get('id')}")
            index_map.append(("artist", item))
            index += 1

    if "playlists" in types and results.get("playlists"):
        print("\nPlaylists:")
        for item in results["playlists"]:
            n = item.get("numberOfTracks") or "?"
            title = item.get("title") or item.get("name")
            print(f"  [{index}] {title} ({n} tracks) id={item.get('uuid') or item.get('id')}")
            index_map.append(("playlist", item))
            index += 1

    return index_map


def parse_pick_list(raw: str, max_index: int) -> list[int]:
    picks: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                if 1 <= i <= max_index:
                    picks.add(i)
        else:
            i = int(part)
            if 1 <= i <= max_index:
                picks.add(i)
    return sorted(picks)
