# mono-dl

Small CLI: metadata from monochrome.tf, streams via Deezer or Qobuz.

Requires Python 3.10+.

## Setup

Run from the `mono-dl` directory (not `mono-dl/mono_dl`):

```bash
pip install -r requirements.txt
```

If you use it often:

```bash
pip install -e .
```

Then `mono-dl ...` works from anywhere.

## Search

```bash
python -m mono_dl search "michael jackson bad"
python -m mono_dl search "bad" -t tracks
python -m mono_dl search "michael jackson bad" -i
python -m mono_dl search "michael jackson bad" --pick 1,3
python -m mono_dl search "michael jackson bad" -d
```

With `-i` you get a numbered list. Enter e.g. `1`, `1,3`, or `2-5`. Enter alone skips the download.

Tracks, albums, and playlists can be downloaded directly. Artists only print a link — no download yet.

## Download by ID or URL

```bash
python -m mono_dl track 16953801
python -m mono_dl album 16953800
python -m mono_dl playlist <uuid>
python -m mono_dl url https://monochrome.tf/album/16953800
python -m mono_dl info track 16953801
```

Default output: `./downloads`

## Options

Applies to `track`, `album`, `playlist`, `url`, `search`:

```
-o, --output     output directory (default: ./downloads)
-p, --provider   auto | deezer | qobuz  (default: auto)
-q, --quality    lossless | high | low
-f, --force      overwrite existing files
```

For `search` only:

```
-n, --limit      results per category (default: 15)
-t, --type       tracks, albums, artists, playlists
```

`auto` tries Deezer first (FLAC via ISRC), then Qobuz.

## Env

All optional:

```
MONO_DL_DEEZER_API=https://dzr.tabs-vs-spaces.wtf
MONO_DL_QOBUZ_API=https://qobuz.kennyy.com.br
MONO_DL_INSTANCES=path/to/instances.json
```

Without `MONO_DL_INSTANCES`, API hosts are read from `monochrome/public/instances.json`, otherwise a built-in fallback list is used.
