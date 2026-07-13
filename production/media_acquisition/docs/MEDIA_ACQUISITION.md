# Media Acquisition

Downloads the creator's **own** YouTube + Instagram video content to a local media library,
then automatically runs the [Voice Dataset Builder](../../voice_dataset/) on it. Local,
incremental, resumable, checksum-verified. One command:

```bash
python -m production.media_acquisition.download
```

> Phase P0. **No voice cloning** in this phase.

## Authorized use

These are the creator's own channels. The Instagram provider authenticates with the
creator's **own** account (session/credentials you supply) and only fetches content that
account is authorized to access. The module uses standard tools (yt-dlp, instaloader) in
their normal mode — it does **not** bypass any platform protection or terms.

## Validate first (recommended)

Before pulling an entire channel, validate the whole pipeline on a small batch:

```bash
python -m production.media_acquisition.download --limit 25
```

This downloads the 25 most-recent videos per platform, runs metadata + the dataset builder,
and prints the full summary — so you catch any issue before processing hundreds of files.
Then re-run without `--limit` for the full channel (already-downloaded files are skipped).

## Setup

- **YouTube**: `pip install yt-dlp` (and `ffmpeg` on PATH for merging/most formats).
- **Instagram**: `pip install instaloader`, then provide your own session via env:
  - `INSTAGRAM_USERNAME` + `INSTALOADER_SESSION_FILE` (a saved instaloader session — preferred), or
  - `INSTAGRAM_USERNAME` + `INSTAGRAM_PASSWORD`.
  Without these the Instagram step reports "unavailable" and is skipped.
- **Voice builder**: needs `ffmpeg` to extract audio from downloaded video (WAV inputs skip it).

Each provider is skipped gracefully when its tool/credentials are absent; the run still
completes and produces (empty) datasets.

## What is downloaded

| | Download | Skip |
|---|---|---|
| **YouTube** | long-form videos, Shorts (highest quality) | community posts, live/upcoming streams, deleted/private |
| **Instagram** | Reels, single video posts | images, carousels, stories, non-video posts |

## Folder layout

```
production_assets/tanshi/
  media/
    youtube/            <- downloaded YouTube files
    instagram/          <- downloaded Instagram files
    download.log        <- append-only download log
  voice/
    raw/{youtube,instagram}/   <- media linked here for the builder
    accepted/ · rejected/
    metadata/
      media.sqlite  · media.csv  · media.xlsx     (acquisition DB)
      dataset.sqlite · dataset.csv · dataset.xlsx  (voice dataset)
```

All metadata (media.* and dataset.*) is co-located under `voice/metadata/`.

## Metadata database (`media.*`)

Columns: `id, platform, url, title, publish_date, duration, resolution, fps, checksum,
filename, status, download_time` plus `item_id, codec, kind, thumbnail, description`.
`status` ∈ `downloaded | skipped | failed`. SQLite is the source of truth; CSV/XLSX are
exported from it.

## Download features

- **Incremental** — an item recorded as `downloaded` with its file present is skipped.
- **Checksum** — every file gets a SHA-256; stored and used for dedup.
- **Duplicate detection** — identical checksum under a different id ⇒ skipped.
- **Resume** — partial downloads continue (yt-dlp `continuedl`, instaloader streaming).
- **Retry** — up to `Config.retries` attempts with backoff.
- **Download log** — every OK/RETRY/FAIL/SKIP/DUP line in `media/download.log`.

## Execution order

1. Download all authorized **YouTube** videos → print YouTube summary.
2. Download all authorized **Instagram** videos → print Instagram summary.
3. Export `media.{sqlite,csv,xlsx}`, link media into `voice/raw`, and run the **Voice Dataset
   Builder** → it writes `dataset.{sqlite,csv,xlsx}` and `accepted/` / `rejected/`.
4. Print the combined **PRODUCTION SUMMARY**: YouTube media · Instagram media · total
   downloaded hours · accepted speech hours · rejected speech hours · dataset quality · top
   rejection reasons.

CLI flags: `--limit N`, `--youtube-only`, `--instagram-only`, `--skip-voice`,
`--base DIR`, `--creator NAME`.

## Tests

```bash
python -m pytest production/media_acquisition/tests -q
```

Hermetic, deterministic, offline: an in-memory `FakeProvider` drives the engine and the full
CLI (including a real Voice Dataset Builder pass over synthetic WAVs), and an autouse fixture
blocks outbound sockets. The real yt-dlp/instaloader integrations are exercised only when
those tools + credentials are present; otherwise their tests report the provider unavailable.

## Notes

- Independent of the Voice Dataset Builder — this module only calls that builder's public CLI
  after downloads; the builder does not depend on this module.
- Instagram support is best-effort and may need minor adjustment for the installed
  instaloader version; the pipeline core does not depend on it.
