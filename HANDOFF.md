# Operator guide

For whoever looks after this repo next. You don't need to be a developer for most of it.

## What runs by itself, and what doesn't

Every Monday at 11:17 UTC a GitHub Action (`.github/workflows/weekly.yml`) refreshes the whole dataset:

1. Installs `poppler-utils` (for `pdftotext`) and runs the tests.
2. Asks OPM's listing API for the current list of agreements and checks it. It refuses to save a listing that is empty, has duplicate or missing ids, or has more than 5% fewer records than last time.
3. Compares the new listing to the previous one and writes what was added, removed or changed to `data/changes/YYYY-MM-DD.md`. If nothing changed it throws the new listing away, so a quiet week adds no commit.
4. `scripts/refresh.py` works out what to download: records that are new, whose file URL or size changed, that Hugging Face doesn't have a PDF for, or whose last download failed more than a week ago. It never downloads the whole 2 GB set. It waits a second between requests, sends an honest User-Agent, retries timeouts and server errors, and stops the whole run at the first 403 or 429.
5. Extracts text from what it downloaded, rebuilds `data/cba_agreements.csv` and `data/SUMMARY.md` from the logs, and checks the result: the table has one row per listed record, every downloaded file has a valid hash and a PDF and text file on Hugging Face, no row from the published table is missing, no file's hash changed without a re-download, and no curated flag changed.
6. Publishes to Hugging Face as **one commit that only adds or overwrites files**: the new PDFs and text, the new `agreements.csv`, and the dataset card if `hf/README.md` changed in git. The commit is pinned to the version it read, so it fails rather than overwrite someone else's change. It never deletes anything.
7. Commits the listing, change log, download and extract logs, table and summary to this repo.
8. Opens issues: "OPM listing changed" when records were added or removed; "New agreements to review for termination flags" listing new agreements in the agencies the orders name; "Weekly refresh failed" when the run goes red.

A week with nothing new downloads nothing, publishes nothing and ends green.

**The only manual job is reviewing termination flags** (see below). The dataset itself refreshes with no one touching it.

### What turns the run red

The run exits with a code and the last step fails on anything but 0. The issue it opens says which:

| Code | Meaning | What to do |
|---|---|---|
| 2 | The checks before publishing failed. Nothing was published. | Read the log lines starting `CHECKS FAILED`. |
| 3 | OPM refused a request (403 or 429). What was fetched before is published. | Wait a week. If it keeps happening, OPM may have blocked the User-Agent; look before running again. |
| 4 | There is something to publish and `HF_TOKEN` is not set. | Add the secret (below). |
| 5 | The Hugging Face commit failed, or the dataset could not be read. | Usually the dataset changed between the read and the commit, or the token expired. Run again. |
| 6 | Most new downloads failed. | Check whether OPM changed its file URLs. |

## Where things live

| What | Where |
|---|---|
| Source | OPM's database: https://www.opm.gov/policy-data-oversight/labor-management-relations/collective-bargaining-agreements/ (the script posts to the undocumented API behind that page) |
| PDFs and extracted text | Hugging Face dataset linked in `README.md` (`pdfs/<id>.pdf`, `text/<id>.txt`). Locally they sit in `data/files/` and `data/text/`, which git ignores. |
| Main table | `data/cba_agreements.csv`, and `agreements.csv` on Hugging Face (the same file) |
| What has been downloaded and extracted | `data/download_log.jsonl`, `data/extract_log.jsonl` |
| Hash of the dataset card last published | `data/hf_card.sha256` |
| Where each termination flag comes from | `data/terminations/sources.csv` and `record_flags.csv`; copies of the source documents are alongside |
| Counts and caveats | `METHODS.md` (the 2026-11-01 pull); `data/SUMMARY.md` is generated every week |
| Weekly listings, change logs and review lists | `data/raw/`, `data/changes/` |
| Hugging Face dataset card | `hf/README.md` |

## Secrets and permissions

- `GITHUB_TOKEN` is supplied by GitHub. The workflow asks to write contents (to commit) and issues.
- `HF_TOKEN` is a repo secret: a Hugging Face token with write access to the dataset. Without it the run publishes nothing and goes red (code 4) if there is anything to publish. A dry run does not need it.

## Testing it by hand

Actions > "weekly refresh" > Run workflow. The defaults are a **dry run**: it does everything except commit to Hugging Face or to this repo, and prints what it would publish.

- `limit`: download at most this many files (default 300; 0 downloads none).
- `dry_run`: leave ticked to test. Untick to publish for real.
- `force_ids`: comma-separated record ids to download again. Use two or three to see the whole path work on a quiet week.

A good first test: `limit` 3, `force_ids` with three ids from `data/cba_agreements.csv`, dry run ticked. The log should show three files downloaded, text extracted, the table rebuilt and `nothing to publish` or a short list. Run the same thing with the dry run unticked to see a real commit.

To run it on your own machine: `pip install -r requirements.txt`, install poppler, then `python3 scripts/fetch_listing.py` and `python3 scripts/refresh.py --dry-run --limit 3`.

The original step-by-step scripts (`download.py`, `extract.py`, `build_table.py`, `summary.py`) still work on their own. `refresh.py` runs the same table and summary scripts.

## Termination flags go stale

The flags in the table are leads, not findings, and a person curates them. They were built from sources collected on 2026-11-01. Court injunctions and agency orders change quickly, and the `uncertain_injunction` rows say in their own text that current status wasn't checked. The 700 `inferred` rows are agreements swept in by a DoD order, with no document naming each one.

How the automatic refresh treats them:

- A new agreement gets the flag the rules in `scripts/coverage.py` and `scripts/build_table.py` give it: the DoD rules, or `not_flagged_no_source_found` (the orders name the agency, no source found) or `not_flagged_agency_not_named`.
- A flag set by hand in `data/terminations/record_flags.csv` is never touched. The refresh does not write to `data/terminations/`, and the checks fail the run if a `confirmed`, `confirmed_secondary` or `confirmed_then_reinstated` flag changes.
- The "New agreements to review" issue lists the week's new agreements in agencies the orders name. Read it, look for a termination document, and add a row to `sources.csv` and `record_flags.csv` if you find one. The next refresh picks it up.

Whoever owns this has to keep doing that review and re-check the old sources. `METHODS.md` describes what each flag means and how it was assigned.

## What a new owner changes

- Copy or move the Hugging Face dataset, and set the repo secret `HF_TOKEN` to a token that can write to it.
- Change the dataset name in `scripts/hf_client.py` (`REPO_ID`, or set the `CBA_HF_REPO` variable), in `README.md` and in `hf/README.md`.
- Anyone who should get the issues needs to watch the repo.

## Tests

```
pip install -r requirements.txt
python -m pytest -q tests
```

They cover the listing check and diff, the download plan, the stop rules, the checks before publishing, the commit plan (additions only), the table build, and the rule that curated flags are never overwritten. They use fakes for OPM and Hugging Face, so they need no network. Nothing tests the flag rules for individual agencies beyond the defaults.
