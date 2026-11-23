"""ELT pipeline for the goodrecmovies API.

Extract -> Load (raw) -> Transform -> Load (processed)

API: https://goodrecmovies.com/api/list  (no key required)
Note: the API does not support field selection, so we fetch the full
payload and drop unwanted columns in the transform step.
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths (resolved relative to the project root, so it works from anywhere)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "raw.json"
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "output.csv"

# ---------------------------------------------------------------------------
# API configuration (goodrecmovies public API — no key required)
# ---------------------------------------------------------------------------
API_URL = "https://goodrecmovies.com/api/list"
API_PARAMS = {"kind": "movie", "pageSize": 100}  # page supplied in the loop
MAX_PAGES = 10           # default: 10 * 100 = up to 1,000 movies
SLEEP_BETWEEN_PAGES = 1  # seconds, to respect per-IP rate limits

# Columns we want to keep in the processed output (the API returns many more,
# including a huge per-country `watch` object and TMDB/trailer metadata).
KEEP_COLUMNS = [
    "tconst",
    "kind",
    "primaryTitle",
    "startYear",
    "runtimeMin",
    "genres",
    "countries",
    "language",
    "avgRating",
    "votes",
    "goodrecIndex",
    "tier",
    "rank",
    "overview",
]

RENAME_MAP = {
    "tconst": "imdb_id",
    "primaryTitle": "primary_title",
    "startYear": "start_year",
    "runtimeMin": "runtime_min",
    "avgRating": "avg_rating",
    "goodrecIndex": "goodrec_index",
}


# ---------------------------------------------------------------------------
# EXTRACT
# ---------------------------------------------------------------------------
def extract(max_pages: int = MAX_PAGES) -> dict:
    """Fetch several pages from the API and return one combined payload."""
    all_rows = []
    total = None

    for page in range(max_pages):
        params = {**API_PARAMS, "page": page}
        print(f"[EXTRACT] GET {API_URL}  params={params}")
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()

        # Surface rate-limit info on the first page
        if page == 0:
            rl = response.headers.get("RateLimit-Policy")
            if rl:
                print(f"[EXTRACT] RateLimit-Policy: {rl}")

        data = response.json()
        rows = data.get("rows", [])
        total = data.get("total", total)
        print(f"[EXTRACT] page {page}: {len(rows)} rows "
              f"(cumulative {len(all_rows) + len(rows)} / total {total})")

        if not rows:
            break
        all_rows.extend(rows)

        # Stop early if we've reached the end of the pool
        if total is not None and len(all_rows) >= total:
            break

        # Be polite to a rate-limited, key-less API
        if page < max_pages - 1:
            time.sleep(SLEEP_BETWEEN_PAGES)

    print(f"[EXTRACT] collected {len(all_rows)} rows across pages")
    return {"rows": all_rows, "total": total}


# ---------------------------------------------------------------------------
# LOAD (RAW)
# ---------------------------------------------------------------------------
def load_raw(data: dict) -> None:
    """Persist the raw JSON snapshot (gitignored)."""
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"[LOAD RAW] wrote {RAW_PATH} ({RAW_PATH.stat().st_size:,} bytes)")


# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Select useful columns, rename, filter, flatten list columns."""
    # 1) Select only the columns we care about (drops watch, posterPath,
    #    trailer*, tmdb*, collection*, adult, etc.)
    present = [c for c in KEEP_COLUMNS if c in df.columns]
    missing = [c for c in KEEP_COLUMNS if c not in df.columns]
    if missing:
        print(f"[TRANSFORM] warning: columns not in API payload: {missing}")
    df = df[present].copy()

    # 2) Rename to snake_case
    df = df.rename(columns=RENAME_MAP)

    # 3) Filter: keep only titles released after 2000.
    #    Null start_year values are dropped here (NaN > 2000 is False).
    before = len(df)
    df = df[df["start_year"] > 2000].copy()
    print(f"[TRANSFORM] filter start_year > 2000: {before} -> {len(df)} rows")

    # 4) Flatten list columns into readable strings
    for col in ("genres", "countries"):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: ", ".join(v) if isinstance(v, list) else v
            )

    return df


# ---------------------------------------------------------------------------
# LOAD (PROCESSED)
# ---------------------------------------------------------------------------
def load_processed(df: pd.DataFrame) -> None:
    """Write the cleaned CSV (committed to the repo)."""
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)
    print(f"[LOAD PROCESSED] wrote {PROCESSED_PATH} ({len(df)} rows)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="goodrecmovies ELT pipeline")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh API call even if data/raw/raw.json exists",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help=f"Number of pages to fetch (default {MAX_PAGES}, 100 rows/page)",
    )
    args = parser.parse_args()

    # ---------------- EXTRACT + LOAD (RAW) ----------------
    if RAW_PATH.exists() and not args.refresh:
        print(f"[EXTRACT] cache hit — using raw snapshot: {RAW_PATH}")
        data = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    else:
        data = extract(max_pages=args.max_pages)
        load_raw(data)

    # ---------------- LOAD RAW -> DataFrame ----------------
    df = pd.DataFrame(data["rows"])
    print(f"[INFO] raw DataFrame shape: {df.shape}")
    print(f"[INFO] raw columns: {list(df.columns)}")

    # ---------------- TRANSFORM ----------------
    df = transform(df)
    print(f"[INFO] processed shape: {df.shape}")
    print(f"[INFO] processed columns: {list(df.columns)}")

    # ---------------- LOAD (PROCESSED) ----------------
    load_processed(df)


if __name__ == "__main__":
    main()