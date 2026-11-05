# Operator guide

For whoever looks after this repo next. You don't need to be a developer for most of it.

## What runs by itself, and what doesn't

Every Monday at 11:17 UTC a GitHub Action (`.github/workflows/weekly.yml`) does this:

1. Runs the tests.
2. Asks OPM's listing API for the current list of agreements and checks it. It refuses to save a listing that is empty, has duplicate or missing ids, or has more than 5% fewer records than last time.
3. Compares the new listing to the previous one and writes what was added, removed or changed to `data/changes/YYYY-MM-DD.md`.
4. Commits the new listing (`data/raw/`) and the change file to the repo.
5. Opens a GitHub issue titled "OPM listing changed" if any record was added or removed, or adds a comment to the open one. If the pipeline itself fails, it does the same under "Weekly listing pipeline failed".

**It does not download any PDFs, extract text, rebuild the table, or touch Hugging Face.** Those steps are manual (see "Refreshing the data by hand"). Nothing in this repo uploads to Hugging Face; the dataset was published by hand.

So `data/cba_agreements.csv`, the termination flags and the Hugging Face dataset are all as of the 2026-11-01 pull until someone redoes the manual steps below. A change to a file URL or a new record shows up in the weekly change file and nowhere else.

Scheduled workflows only run from the default branch. This workflow is not on `main` yet (it was added on the `pipeline` branch), so it will not run until it is merged. Until then, no weekly listing is saved and no issues are opened.

## Where things live

| What | Where |
|---|---|
| Source | OPM's database: https://www.opm.gov/policy-data-oversight/labor-management-relations/collective-bargaining-agreements/ (the script posts to the undocumented API behind that page) |
| PDFs and extracted text | Hugging Face dataset linked in `README.md`. Locally they sit in `data/files/` and `data/text/`, which git ignores, so a fresh clone doesn't have them. |
| Main table | `data/cba_agreements.csv` |
| Where each termination flag comes from | `data/terminations/sources.csv` and `record_flags.csv`; copies of the source documents are alongside |
| Counts and caveats | `METHODS.md`; `data/SUMMARY.md` is generated |
| Weekly listings and change logs | `data/raw/`, `data/changes/` |
| Hugging Face dataset card | `hf/README.md` (matches the card on the Hub as of 2026-11-05) |

## Secrets and permissions

- `GITHUB_TOKEN` is supplied by GitHub. The workflow asks for permission to write contents (to commit the listing) and issues (to open them). No setup needed.
- No Hugging Face token is used by the workflow. The manual upload needs a Hugging Face account with write access to the dataset.

## Refreshing the data by hand

Run from the repo root. `extract.py` needs `pdftotext` and `pdfinfo` (poppler) installed.

```
python3 -I scripts/fetch_listing.py
LISTING=$(ls data/raw/cba_listing_*.json | tail -1)
python3 -I scripts/download.py "$LISTING" data/files data/download_log.jsonl $(( $(date +%s) + 3600 ))
python3 -I scripts/extract.py data/files data/text data/extract_log.jsonl
python3 -I scripts/build_table.py
python3 -I scripts/summary.py
```

The `download.py` arguments are the listing, the output folder, the log, and a deadline as a Unix timestamp (the example gives it an hour). `download.py` waits a second between requests and stops at its deadline or at 3 GB, so it can be run again to resume. `build_table.py` uses the newest listing in `data/raw/`; if that listing has records you haven't downloaded, those rows come out without a hash or page count. Download first.

Then upload the PDFs, `text/`, `agreements.csv` and the card to Hugging Face yourself. There is no script for that.

## Termination flags go stale

The flags in the table are leads, not findings. They were built from sources collected on 2026-11-01. Court injunctions and agency orders change quickly, and the `uncertain_injunction` rows say in their own text that current status wasn't checked. The 700 `inferred` rows are agreements swept in by a DoD order, with no document naming each one. The flags are only as good as `sources.csv`, which is edited by hand.

Whoever owns this has to re-check the sources and add rows to `sources.csv` and `record_flags.csv`. Nothing automatic does that. `METHODS.md` describes what each flag means and how it was assigned.

## What a new owner changes

Nothing in the scripts, tests or workflow names a GitHub or Hugging Face account. Only the docs do:

- `README.md`: the link to the Hugging Face dataset.
- `hf/README.md`: the link back to this repo.
- The Hugging Face dataset itself, which lives under the old owner's account until moved or copied.
- Any bot or person who gets the "OPM listing changed" issues: they go to whoever watches this repo.

## Tests

```
pip install -r requirements.txt
python -m pytest -q tests
```

They cover the listing check and the diff. Nothing tests the table build or the flag rules.
