from __future__ import annotations

from typing import Any

import httpx

from .config import TIDAL_PROXY, load_api_instances
from .util import track_artist, track_title


class MetadataError(Exception):
    pass


class MonochromeClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.instances = load_api_instances()
        self.timeout = timeout
        self.tidal_proxy = TIDAL_PROXY.rstrip("/")

    def _fetch_json(self, url: str) -> Any:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "mono-dl/0.1"})
            response.raise_for_status()
            return response.json()

    def _fetch_with_failover(self, path: str) -> Any:
        last_error: Exception | None = None
        for base in self.instances:
            url = f"{base.rstrip('/')}{path}"
            try:
                return self._fetch_json(url)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise MetadataError(f"All API instances failed for {path}: {last_error}")

    @staticmethod
    def _unwrap(data: Any) -> Any:
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    @staticmethod
    def _normalize_track(raw: dict[str, Any]) -> dict[str, Any]:
        item = raw.get("item") if isinstance(raw.get("item"), dict) else raw
        if not isinstance(item, dict):
            raise MetadataError("Invalid track payload")
        return item

    def get_track(self, track_id: str | int) -> dict[str, Any]:
        try:
            data = self._unwrap(self._fetch_with_failover(f"/info/?id={track_id}"))
        except MetadataError:
            data = self._fetch_json(f"{self.tidal_proxy}/api/v1/tracks/{track_id}/?countryCode=US")

        if isinstance(data, list):
            for entry in data:
                track = self._normalize_track(entry)
                if str(track.get("id")) == str(track_id):
                    return track
            if data:
                return self._normalize_track(data[0])
        if isinstance(data, dict):
            if str(data.get("id")) == str(track_id) or data.get("title"):
                return self._normalize_track(data)
        raise MetadataError(f"Track {track_id} not found")

    def get_album(self, album_id: str | int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data = self._unwrap(self._fetch_with_failover(f"/album/?id={album_id}"))
        if not isinstance(data, dict):
            raise MetadataError(f"Album {album_id} not found")

        album = dict(data)
        items = album.pop("items", None) or data.get("items") or []
        tracks = [self._normalize_track(i) for i in items if i]

        if not album.get("title") and tracks:
            album.setdefault("title", (tracks[0].get("album") or {}).get("title"))
        if not album.get("artist") and tracks:
            album["artist"] = tracks[0].get("artist") or (tracks[0].get("artists") or [None])[0]

        total = album.get("numberOfTracks") or len(tracks)
        offset = len(tracks)
        while total and len(tracks) < int(total) and offset < 10_000:
            try:
                page = self._unwrap(
                    self._fetch_with_failover(f"/album/?id={album_id}&offset={offset}&limit=500")
                )
            except MetadataError:
                break
            page_items = page.get("items") if isinstance(page, dict) else page
            if not page_items:
                break
            batch = [self._normalize_track(i) for i in page_items]
            if tracks and batch and batch[0].get("id") == tracks[0].get("id"):
                break
            tracks.extend(batch)
            offset += len(batch)
            if len(batch) == 0:
                break

        return album, tracks

    def get_playlist(self, playlist_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data = self._unwrap(self._fetch_with_failover(f"/playlist/?id={playlist_id}"))
        if not isinstance(data, dict):
            raise MetadataError(f"Playlist {playlist_id} not found")

        playlist = dict(data)
        items = playlist.get("items") or []
        tracks = [self._normalize_track(i) for i in items if i]

        offset = len(tracks)
        while playlist.get("numberOfTracks") and len(tracks) < int(playlist["numberOfTracks"]):
            try:
                page = self._unwrap(self._fetch_with_failover(f"/playlist/?id={playlist_id}&offset={offset}"))
            except MetadataError:
                break
            page_items = page.get("items") if isinstance(page, dict) else []
            if not page_items:
                break
            batch = [self._normalize_track(i) for i in page_items]
            tracks.extend(batch)
            offset += len(batch)

        return playlist, tracks

    def search_tracks(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        from urllib.parse import quote

        data = self._unwrap(self._fetch_with_failover(f"/search/?s={quote(query)}"))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        tracks = []
        for i in items:
            raw = i.get("item") if isinstance(i, dict) and "item" in i else i
            if isinstance(raw, dict):
                tracks.append(self._normalize_track(raw))
        return tracks[:limit]

    def search_albums(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        from urllib.parse import quote

        data = self._unwrap(self._fetch_with_failover(f"/search/?al={quote(query)}"))
        if not isinstance(data, dict):
            return []
        albums = data.get("albums") or {}
        items = albums.get("items") if isinstance(albums, dict) else []
        if not isinstance(items, list):
            items = []
        return items[:limit]

    def search_artists(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        from urllib.parse import quote

        data = self._unwrap(self._fetch_with_failover(f"/search/?a={quote(query)}"))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return items[:limit]

    def search_playlists(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        from urllib.parse import quote

        data = self._unwrap(self._fetch_with_failover(f"/search/?p={quote(query)}"))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return items[:limit]

    def search_all(self, query: str, limit: int = 25) -> dict[str, list[dict[str, Any]]]:
        from urllib.parse import quote

        try:
            data = self._unwrap(self._fetch_with_failover(f"/search/?al={quote(query)}"))
            if isinstance(data, dict):
                tracks = [self._normalize_track(i) for i in (data.get("tracks") or {}).get("items") or []]
                albums = (data.get("albums") or {}).get("items") or []
                artists = (data.get("artists") or {}).get("items") or []
                playlists = (data.get("playlists") or {}).get("items") or []
                if tracks or albums:
                    return {
                        "tracks": tracks[:limit],
                        "albums": albums[:limit],
                        "artists": artists[:limit],
                        "playlists": playlists[:limit],
                    }
        except MetadataError:
            pass

        return {
            "tracks": self.search_tracks(query, limit),
            "albums": self.search_albums(query, limit),
            "artists": self.search_artists(query, limit),
            "playlists": self.search_playlists(query, limit),
        }

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.search_tracks(query, limit)

    @staticmethod
    def describe_track(track: dict[str, Any]) -> str:
        isrc = track.get("isrc") or "no-isrc"
        return f"{track_title(track)} — {track_artist(track)} [{isrc}]"
