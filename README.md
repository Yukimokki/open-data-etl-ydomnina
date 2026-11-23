# Open Data ETL — goodrecmovies

A small ELT pipeline that pulls movie data from the public
[goodrecmovies API](https://goodrecmovies.com/api/list), cleans it with pandas,
and saves a dashboard-ready CSV. Includes a short exploratory analysis of
whether movie rank depends on runtime.

## Data source

- **API:** `https://goodrecmovies.com/api/list` (OpenAPI spec:
  `https://goodrecmovies.com/openapi.json`)
- **Auth:** none — no API key, no OAuth.
- **Pool size:** 3,491 movies at the time of writing.
- **Rate limits:** per IP; surfaced in the `RateLimit-Policy` response header.
  The pipeline sleeps 1 s between pages to stay polite.
- **License (per API metadata):** IMDb public datasets + TMDB.

The API returns a large payload per movie (including a per-country `watch`
object). We keep only 14 useful columns and drop the rest during transform.

## Pipeline (ELT)

`src/main.py` implements **Extract → Load (raw) → Transform → Load (processed)**:

1. **Extract** — `requests.get` over pages `0..N-1` (`pageSize=100`,
   `MAX_PAGES` configurable via `--max-pages`).
2. **Load (raw)** — the full JSON response is saved to
   `data/raw/raw.json` (gitignored). If the snapshot exists, it is reused
   unless `--refresh` is passed — this makes the pipeline reproducible even
   if the API changes.
3. **Transform** (pandas):
   - select 14 columns (`KEEP_COLUMNS`), dropping `watch`, `posterPath`,
     `trailer*`, `tmdb*`, `collection*`, `adult`
   - rename to snake_case (`primaryTitle` → `primary_title`, …)
   - filter `start_year > 2000`
   - flatten `genres` / `countries` lists into readable strings
4. **Load (processed)** — clean table written to
   `data/processed/output.csv`.

## How to run

```bash
# 1. create venv (optional) and install deps
pip install -r requirements.txt

# 2. run the pipeline (fresh fetch, 10 pages = up to 1,000 movies)
python -m src.main --refresh --max-pages 10

# 3. (optional) exploratory analysis + figures
python -m src.analysis