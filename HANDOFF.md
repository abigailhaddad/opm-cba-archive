# Handoff

## What this is
Every federal union contract in OPM's public database, as PDFs and text, with a first-pass flag for contracts terminated under the 2025 executive orders.
- Code: https://github.com/abigailhaddad/opm-cba-archive
- Data: https://huggingface.co/datasets/abigailhaddad/opm-cba-agreements (columns and limits: see the dataset card)
- Site: https://opm-union-contracts.abigailhaddad.com (built from https://github.com/abigailhaddad/dataset-explorer, site `opm-union-contracts`)

## What runs on its own
- `.github/workflows/weekly.yml` runs Mondays and refreshes everything: it fetches OPM's listing, downloads only new or changed PDFs, extracts the text, rebuilds `data/cba_agreements.csv` and publishes to Hugging Face in one commit that only adds or overwrites files. A week with nothing new commits nothing and ends green. It opens an issue when records are added or removed, when new agreements need a flag review, and when a run fails.
- **By hand: the termination flags.** They come from sources in `data/terminations/` (`sources.csv` and `record_flags.csv`), and the refresh never edits that folder. New agreements get a default flag. When the issue "New agreements to review for termination flags" appears, look for a termination document and add a row to both files. Old flags go stale as courts rule, so re-check them. `METHODS.md` and the README say what each flag means.

## Secrets
- `HF_TOKEN` (repo secret): a Hugging Face token with write access to the dataset. Without it the run goes red whenever there is something to publish.
- `GITHUB_TOKEN` comes from GitHub. The workflow asks to write contents and issues.

## If you take it over
- Copy or move the dataset to your own Hugging Face account and set `HF_TOKEN` to a token that can write to it.
- Replace `abigailhaddad` in `scripts/hf_client.py` (or set the `CBA_HF_REPO` variable), `scripts/cba_pipeline.py` (the User-Agent), `README.md` and `hf/README.md`. To find them: `grep -rn abigailhaddad . --exclude-dir=.git --exclude-dir=data`.
- The website lives in the dataset-explorer repo (`configs/opm-cba.json`). It needs its own Cloudflare Pages project.
- Watch the repo to get the issues.

## When it breaks
Open the Actions tab and the "weekly refresh" run. A failed run opens an issue, "Weekly refresh failed", with the exit code of `scripts/refresh.py`:
- 2: the checks before publishing failed, or there is no listing. Nothing was published. Read the log lines starting `CHECKS FAILED`.
- 3: OPM refused a request (403 or 429). Wait, and look before running again.
- 4: there is something to publish and `HF_TOKEN` is not set.
- 5: the Hugging Face commit failed, or the dataset could not be read. Usually run it again.
- 6: text extraction failed for every file, or a large share of the new downloads failed. Check whether OPM changed its file URLs.

To run it by hand, see "Testing it by hand" in the README. The defaults are a dry run.

## Costs
No model is called, so nothing in the code charges per use.
