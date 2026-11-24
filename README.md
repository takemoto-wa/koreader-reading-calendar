# KOReader Reading Calendar

Turn a KOReader `statistics.sqlite3` reading database into a beautiful, self-contained HTML visualization: a book-cover reading calendar (GitHub-style heatmap where each day is filled with the cover of the book read that day) plus a reading-time leaderboard sorted from most to least time. The output is a single HTML file with all data and covers embedded — no network dependency, just double-click to open offline.

![Example reading calendar](docs/example-square.png)

## Features

- **Cover-based reading calendar** — a 7-row × N-week grid spanning your whole reading period. Each reading day is filled with the cover of the book you read most that day; opacity encodes daily reading duration, and multi-book days show stacked mini-covers.
- **Reading-time leaderboard** — books ranked by total reading time, covers front and center, with sqrt-scaled bars so short-duration books stay visible. Sorted by time / days / title.
- **Two-way highlighting** — click a day to highlight the books read that day in the leaderboard; click a book to outline every day it was read in the calendar.
- **Fully self-contained output** — data, book covers (base64), CSS and JS are all inlined. Works from `file://` with zero external fonts, CDNs, or network images.
- **Accessible & responsive** — keyboard grid navigation (roving tabindex + arrow keys), screen-reader labels, reduced-motion support, and a responsive layout for mobile.
- **Reusable pipeline** — parameterized scripts take any database and epub directory; the HTML template is data-driven, so no hand-editing of text is needed between datasets.

## Requirements

- Python 3.x
- [Pillow](https://python-pillow.org/) (`pip install pillow`)
- Google Chrome (only needed for the optional screenshot verification step)

## Installation

Install as a WorkBuddy skill by copying this folder into your skills directory:

```bash
# User-level (available across all projects)
cp -r koreader-reading-calendar ~/.workbuddy/skills/
```

On Windows the user-level skills directory is `C:\Users\Administrator\.workbuddy\skills\`.

You can also run the scripts directly from a terminal — they have no dependency on WorkBuddy itself.

## Usage

The scripts live in `scripts/`. Quote paths that contain spaces.

### Step 1 — Inspect the database

```bash
python scripts/inspect_db.py --db "<path/to/statistics.sqlite3>" --threshold 300
```

Prints the books, reading time, date range and candidate list. Use this to confirm the threshold and decide whether any duplicate editions should be merged.

### Step 2 — Build the data JSON

```bash
python scripts/build_data.py \
  --db "<path/to/statistics.sqlite3>" \
  --epub-root "<path/to/epub/directory>" \
  --out "<workdir>/reading_data.json" \
  --threshold 300 \
  --merge '{"1": 6}' \
  --covers '{"13": "/path/to/cover.jpg"}'
```

- `--threshold` — minimum reading time in **seconds** (300 = 5 minutes).
- `--merge` — merge duplicate editions of the same book (`alias id → canonical id`).
- `--covers` — explicitly assign a cover for a book (value can be an epub filename, an absolute image path, or a filename in `--fallback-dir`).
- `--names` — assign a short display title. **English-language books always keep their original English title**: a name containing Chinese characters is ignored for them (no auto-translation is ever performed). English name overrides still work.

Covers are matched automatically by book title + author against epub metadata. See [Step 2b](#step-2b-optional-generate-fallback-covers) for books with no epub available.

### Step 2b (optional) — Generate fallback covers

```bash
python scripts/gen_cover.py --title "The Martian" --author "Andy Weir" \
  --out "<workdir>/fallback/the_martian.jpg" --theme auto
```

Then pass `--fallback-dir "<workdir>/fallback"` (or `--covers`) to `build_data.py` to use it.

### Step 3 — Render the HTML

```bash
python scripts/render_html.py \
  --data "<workdir>/reading_data.json" \
  --template "assets/template.html" \
  --out "<workdir>/index.html"
```

Header text, KPIs and footer copy are filled in from the data by JavaScript — no manual edits needed.

### Step 4 — Verify and preview

```bash
python scripts/verify.py \
  --html "<workdir>/index.html" \
  --data "<workdir>/reading_data.json" \
  --screenshot "<workdir>/preview.png"
```

Validates that embedded data is consistent, covers are inlined, there are no external dependencies, and id mappings are complete. With `--screenshot`, renders a preview via headless Chrome.

## Project structure

```
koreader-reading-calendar/
├── SKILL.md                       # WorkBuddy skill definition (Chinese)
├── README.md                      # This file
├── assets/
│   └── template.html              # Data-driven calendar + leaderboard template
├── scripts/
│   ├── inspect_db.py              # Inspect DB, list candidate books and stats
│   ├── build_data.py              # Build data JSON from DB + epub directory
│   ├── gen_cover.py               # Generate typographic fallback covers
│   ├── render_html.py             # Inject data into template → single HTML file
│   └── verify.py                  # Structure checks + headless-browser screenshot
├── references/
│   └── data_structure.md          # KOReader schema, cover extraction, data contract
└── docs/
    └── example-square.png         # Example output
```

## Data contract

`build_data.py` emits `reading_data.json` with four top-level keys:

- `meta` — source, generation date, threshold, date range, excluded-book count
- `stats` — book count, total time, active days, span days
- `books` — one entry per book (id, title, author, time, days, base64 cover, color, …), sorted by time descending
- `calendar` — map from `YYYY-MM-DD` to the list of books read that day (sorted by duration descending); only days with reading are present, the frontend fills the gaps

See [references/data_structure.md](references/data_structure.md) for the full schema, epub cover-extraction flow, and visual/interaction contract.

## Important notes

- **Durations are in seconds** — a 5-minute threshold is `300`.
- **English books keep their original English titles — never auto-translate.** `display_title()` in `build_data.py` ignores any Chinese `--names` override for English books, so the calendar and leaderboard always show the original title (e.g. *The Martian*, *Project Hail Mary*). This is an explicit user requirement — do not add translation logic.
- **Book ids are not necessarily contiguous** (e.g. 6, 20, 25). All `bookId → book` lookups must map by id, never by array index, or the cross-view highlighting will silently fail.
- **Duplicate editions** of the same work may have different ids. Ask whether to merge before using `--merge`.
- `book.total_read_time` should closely match `SUM(page_stat_data.duration)` grouped by day (within a few seconds); a large mismatch indicates anomalous data.
- Use the raw `page_stat_data` table for daily aggregation — **do not** use the `page_stat` view, which expands pages and double-counts.
- The output must stay self-contained: no external fonts, CDNs, or network images; covers are inlined as base64.
- `assets/template.html` is the single source of truth for layout — do not rewrite its styles.

## License

MIT
