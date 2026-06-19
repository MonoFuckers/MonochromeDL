from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .client import MetadataError, MonochromeClient
from .download import download_track_file
from .providers import StreamResolver
from .search_util import parse_pick_list, print_search_results
from .util import parse_monochrome_url


def _download_selection(args: argparse.Namespace, index_map: list[tuple[str, dict]], picks: list[int]) -> int:
    client = MonochromeClient()
    resolver = StreamResolver()
    ok = 0
    for pick in picks:
        kind, item = index_map[pick - 1]
        try:
            if kind == "track":
                print(f"Downloading track [{pick}]...")
                path = download_track_file(
                    resolver,
                    item,
                    Path(args.output),
                    provider=args.provider,
                    quality=args.quality,
                    skip_existing=not args.force,
                )
                print(f"  -> {path}")
                ok += 1
            elif kind == "album":
                album, tracks = client.get_album(item["id"])
                args_copy = argparse.Namespace(**vars(args))
                args_copy.id = str(item["id"])
                ok += cmd_album(args_copy) == 0
            elif kind == "playlist":
                args_copy = argparse.Namespace(**vars(args))
                args_copy.id = str(item.get("uuid") or item.get("id"))
                ok += cmd_playlist(args_copy) == 0
            elif kind == "artist":
                print(f"Artist download not yet supported — open https://monochrome.tf/artist/{item['id']}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"  x [{pick}] failed: {exc}", file=sys.stderr)
    return ok


def cmd_track(args: argparse.Namespace) -> int:
    client = MonochromeClient()
    resolver = StreamResolver()
    track = client.get_track(args.id)
    print(f"Downloading: {client.describe_track(track)}")
    path = download_track_file(
        resolver,
        track,
        Path(args.output),
        provider=args.provider,
        quality=args.quality,
        skip_existing=not args.force,
    )
    print(f"Saved: {path}")
    return 0


def cmd_album(args: argparse.Namespace) -> int:
    client = MonochromeClient()
    resolver = StreamResolver()
    album, tracks = client.get_album(args.id)
    title = album.get("title") or args.id
    print(f"Album: {title} ({len(tracks)} tracks)")
    ok = 0
    for index, track in enumerate(tracks, 1):
        try:
            print(f"[{index}/{len(tracks)}] {client.describe_track(track)}")
            path = download_track_file(
                resolver,
                track,
                Path(args.output),
                provider=args.provider,
                quality=args.quality,
                album=album,
                skip_existing=not args.force,
            )
            print(f"  -> {path}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  x failed: {exc}", file=sys.stderr)
    print(f"Done: {ok}/{len(tracks)} tracks")
    return 0 if ok else 1


def cmd_playlist(args: argparse.Namespace) -> int:
    client = MonochromeClient()
    resolver = StreamResolver()
    playlist, tracks = client.get_playlist(args.id)
    title = playlist.get("title") or playlist.get("name") or args.id
    print(f"Playlist: {title} ({len(tracks)} tracks)")
    ok = 0
    for index, track in enumerate(tracks, 1):
        try:
            print(f"[{index}/{len(tracks)}] {client.describe_track(track)}")
            path = download_track_file(
                resolver,
                track,
                Path(args.output),
                provider=args.provider,
                quality=args.quality,
                skip_existing=not args.force,
            )
            print(f"  -> {path}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  x failed: {exc}", file=sys.stderr)
    print(f"Done: {ok}/{len(tracks)} tracks")
    return 0 if ok else 1


def cmd_url(args: argparse.Namespace) -> int:
    kind, item_id = parse_monochrome_url(args.url)
    if kind == "album":
        args.id = item_id
        return cmd_album(args)
    if kind == "track":
        args.id = item_id
        return cmd_track(args)
    if kind == "playlist":
        args.id = item_id
        return cmd_playlist(args)
    print(f"Unsupported URL type: {kind}", file=sys.stderr)
    return 1


def cmd_search(args: argparse.Namespace) -> int:
    client = MonochromeClient()
    type_map = {
        "track": "tracks",
        "tracks": "tracks",
        "album": "albums",
        "albums": "albums",
        "artist": "artists",
        "artists": "artists",
        "playlist": "playlists",
        "playlists": "playlists",
    }
    raw_types = [t.lower() for t in (args.type or ["all"])]
    if "all" in raw_types:
        show_types = {"tracks", "albums", "artists", "playlists"}
    else:
        show_types = {type_map.get(t, t) for t in raw_types}

    if show_types == {"tracks"}:
        results = {"tracks": client.search_tracks(args.query, args.limit), "albums": [], "artists": [], "playlists": []}
    elif show_types == {"albums"}:
        results = {"tracks": [], "albums": client.search_albums(args.query, args.limit), "artists": [], "playlists": []}
    else:
        results = client.search_all(args.query, args.limit)
        for key in list(results.keys()):
            if key not in show_types:
                results[key] = []

    total = sum(len(v) for v in results.values())
    if total == 0:
        print("No results.")
        return 1

    print(f'Search: "{args.query}" ({total} results)')
    index_map = print_search_results(results, show_types=show_types)

    if args.pick:
        picks = parse_pick_list(args.pick, len(index_map))
        if not picks:
            print("No valid picks.", file=sys.stderr)
            return 1
        _download_selection(args, index_map, picks)
        return 0

    if args.interactive:
        try:
            raw = input("\nDownload which? (e.g. 1,3 or 2-5, Enter to skip): ").strip()
        except EOFError:
            return 0
        if not raw:
            return 0
        picks = parse_pick_list(raw, len(index_map))
        if picks:
            _download_selection(args, index_map, picks)
        return 0

    if args.download:
        track_results = results.get("tracks") or []
        if not track_results:
            print("No tracks to download.", file=sys.stderr)
            return 1
        resolver = StreamResolver()
        ok = 0
        for track in track_results:
            try:
                path = download_track_file(
                    resolver,
                    track,
                    Path(args.output),
                    provider=args.provider,
                    quality=args.quality,
                    skip_existing=not args.force,
                )
                print(f"  -> {path}")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  x {client.describe_track(track)}: {exc}", file=sys.stderr)
        return 0 if ok else 1

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    client = MonochromeClient()
    if args.kind == "track":
        track = client.get_track(args.id)
        print(client.describe_track(track))
        return 0
    if args.kind == "album":
        album, tracks = client.get_album(args.id)
        print(f"{album.get('title')} — {len(tracks)} tracks")
        for track in tracks:
            print(f"  - {client.describe_track(track)} id={track.get('id')}")
        return 0
    playlist, tracks = client.get_playlist(args.id)
    print(f"{playlist.get('title') or playlist.get('name')} — {len(tracks)} tracks")
    for track in tracks:
        print(f"  - {client.describe_track(track)} id={track.get('id')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mono-dl",
        description="Download music via Monochrome API metadata and stream providers (Deezer/Qobuz).",
    )
    parser.add_argument("--version", action="version", version=f"mono-dl {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", default="./downloads", help="Output directory (default: ./downloads)")
    common.add_argument(
        "-p",
        "--provider",
        choices=["auto", "deezer", "qobuz"],
        default="auto",
        help="Stream provider (default: auto = deezer -> qobuz)",
    )
    common.add_argument(
        "-q",
        "--quality",
        choices=["lossless", "high", "low"],
        default="lossless",
        help="Audio quality (default: lossless)",
    )
    common.add_argument("-f", "--force", action="store_true", help="Re-download even if file exists")

    p_track = sub.add_parser("track", parents=[common], help="Download a single track by TIDAL id")
    p_track.add_argument("id", help="TIDAL track id")
    p_track.set_defaults(func=cmd_track)

    p_album = sub.add_parser("album", parents=[common], help="Download all tracks from an album")
    p_album.add_argument("id", help="TIDAL album id")
    p_album.set_defaults(func=cmd_album)

    p_playlist = sub.add_parser("playlist", parents=[common], help="Download a playlist")
    p_playlist.add_argument("id", help="TIDAL playlist uuid")
    p_playlist.set_defaults(func=cmd_playlist)

    p_url = sub.add_parser("url", parents=[common], help="Download from a monochrome.tf URL")
    p_url.add_argument("url", help="e.g. https://monochrome.tf/album/16953800")
    p_url.set_defaults(func=cmd_url)

    p_search = sub.add_parser("search", parents=[common], help="Search and optionally download")
    p_search.add_argument("query", help='Search query, e.g. "michael jackson bad"')
    p_search.add_argument("-n", "--limit", type=int, default=15, help="Max results per category")
    p_search.add_argument(
        "-t",
        "--type",
        action="append",
        default=None,
        choices=["all", "tracks", "albums", "artists", "playlists", "track", "album", "artist", "playlist"],
        help="Result types (repeatable, default: all)",
    )
    p_search.add_argument("-d", "--download", action="store_true", help="Download all track results")
    p_search.add_argument("-i", "--interactive", action="store_true", help="Pick results to download")
    p_search.add_argument("--pick", metavar="N", help="Download picks, e.g. 1,3 or 2-5")
    p_search.set_defaults(func=cmd_search)

    p_info = sub.add_parser("info", help="Show metadata without downloading")
    p_info.add_argument("kind", choices=["track", "album", "playlist"])
    p_info.add_argument("id")
    p_info.set_defaults(func=cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MetadataError as exc:
        print(f"Metadata error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
