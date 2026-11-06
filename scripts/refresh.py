"""The weekly refresh, after the listing has been fetched and diffed.

    python3 scripts/refresh.py [--limit 300] [--dry-run] [--force-ids ID,ID]

It downloads only the files that are new, changed, missing from Hugging Face, or due a retry,
extracts their text, rebuilds data/cba_agreements.csv, checks the result, and publishes it to
Hugging Face as one commit that only adds or overwrites files. A run with nothing new changes
nothing and exits 0.

Exit codes: 0 fine (including nothing to do), 2 the checks failed so nothing was published,
3 OPM refused a request (403/429; what was fetched before that is still published),
4 there is something to publish and HF_TOKEN is not set, 5 the Hugging Face commit failed,
6 most of this run's downloads failed.
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cba_pipeline as cp  # noqa: E402
from hf_client import HfClient  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
MIN_FAIL_SHARE = 0.5      # of this run's new/changed downloads, how many may fail before the run is red
MIN_FAIL_COUNT = 4        # ...and only judge when at least this many were attempted


def say(*a):
    print(*a, flush=True)


def write_outputs(**kv):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def run_script(name, root):
    env = dict(os.environ, CBA_ROOT=root)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, name)], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        say(r.stdout[-2000:], r.stderr[-2000:])
        raise RuntimeError(f"{name} failed with exit code {r.returncode}")
    return r.stdout


def card_hash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def main(argv=None, fetch=None, hf=None, extract=None, sleep=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--limit", type=int, default=300, help="download at most this many files this run")
    ap.add_argument("--force-ids", default="", help="comma-separated record ids to download again (for testing)")
    ap.add_argument("--dry-run", action="store_true", help="do everything except the Hugging Face commit")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between downloads")
    args = ap.parse_args(argv)
    fetch = fetch or cp.http_fetch
    extract = extract or cp.extract_record
    hf = hf or HfClient()
    root = os.path.abspath(args.root)
    P = lambda *a: os.path.join(root, *a)
    today = dt.date.today().isoformat()
    problems = []

    listings = sorted(glob.glob(P("data/raw/cba_listing_*.json")))
    if not listings:
        say("no listing in data/raw: run scripts/fetch_listing.py first")
        return 2
    records = json.load(open(listings[-1]))["results"]

    revision, hf_files, remote_csv = hf.read_state()
    if revision is None:
        say("the Hugging Face dataset does not exist or cannot be read")
        return 5
    hf_pdf_ids = {f[5:-4] for f in hf_files if f.startswith("pdfs/") and f.endswith(".pdf")}
    hf_text_ids = {f[5:-4] for f in hf_files if f.startswith("text/") and f.endswith(".txt")}
    published_rows = []
    if remote_csv:
        import csv, io
        published_rows = list(csv.DictReader(io.StringIO(remote_csv.decode("utf-8"))))
    else:
        published_rows = cp.read_rows(P("data/cba_agreements.csv"))

    log_path = P("data/download_log.jsonl")
    state = cp.latest_download_state(cp.load_jsonl(log_path))
    force = [x for x in args.force_ids.split(",") if x.strip()]
    full_plan = cp.plan_downloads(records, state, hf_pdf_ids, published_rows, force_ids=force)
    plan = full_plan[: args.limit]
    reasons = {}
    for item in plan:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    say(f"listing: {len(records)} records. To download: {len(plan)} {reasons or ''}"
        + (f" ({len(full_plan) - len(plan)} more waiting for the next run)" if len(full_plan) > len(plan) else ""))

    pdf_dir, text_dir = P("data/files"), P("data/text")
    os.makedirs(text_dir, exist_ok=True)
    result = {"ok": [], "failed": [], "blocked": False}
    if plan:
        result = cp.download_files(plan, fetch, pdf_dir, log_path, sleep=args.delay if sleep is None else sleep)
        say(f"downloaded {len(result['ok'])}, failed {len(result['failed'])}" + (", BLOCKED by OPM" if result["blocked"] else ""))
        ex_log = P("data/extract_log.jsonl")
        extract_failed = 0
        with open(ex_log, "a") as out:
            for rid in result["ok"]:
                rec = extract(os.path.join(pdf_dir, rid + ".pdf"), os.path.join(text_dir, rid + ".txt"))
                out.write(json.dumps(rec) + "\n")
                if rec.get("error") or rec.get("pdftotext_rc") not in (0, None):
                    extract_failed += 1
        if result["ok"] and extract_failed == len(result["ok"]) and len(result["ok"]) >= 3:
            problems.append("text extraction failed for every file this run (is poppler-utils installed?)")
        if result["blocked"]:
            problems.append("OPM refused a request (HTTP 403 or 429); stopped downloading. A person should look before the next run")
        # Retries of known-bad records are expected to fail; judge only files we had no result for before.
        fresh = [i for i in plan if i["reason"] in ("new", "url_changed", "file_changed", "forced", "missing_on_hf")]
        fresh_ids = {i["id"] for i in fresh}
        fresh_failed = [r for r in result["failed"] if r in fresh_ids]
        if len(fresh) >= MIN_FAIL_COUNT and len(fresh_failed) / len(fresh) >= MIN_FAIL_SHARE and not result["blocked"]:
            problems.append(f"{len(fresh_failed)} of {len(fresh)} new or changed downloads failed")

    # rebuild the table and summary from the logs
    run_script("build_table.py", root)
    run_script("summary.py", root)
    csv_path = P("data/cba_agreements.csv")
    rows = cp.read_rows(csv_path)

    local_pdfs = {f[:-4] for f in os.listdir(pdf_dir)} if os.path.isdir(pdf_dir) else set()
    local_texts = {f[:-4] for f in os.listdir(text_dir)} if os.path.isdir(text_dir) else set()
    bad = cp.verify_table(rows, records, published_rows, hf_pdf_ids | local_pdfs, hf_text_ids | local_texts,
                          redownloaded=result["ok"])
    if bad:
        say("CHECKS FAILED, nothing published:")
        for b in bad:
            say("  -", b)
        write_outputs(published=0, review_count=0, problems=len(bad))
        return 2
    changed_flags = cp.flag_changes(rows, published_rows)
    if changed_flags:
        say(f"{len(changed_flags)} existing rows changed flag (listing fields changed); first: {changed_flags[0]}")

    ops = cp.commit_plan(rows, published_rows, hf_files, pdf_dir, text_dir, csv_path, remote_csv, result["ok"])
    card_path = P("hf/README.md")
    card_state = P("data/hf_card.sha256")
    recorded = open(card_state).read().strip() if os.path.exists(card_state) else None
    if card_hash(card_path) and card_hash(card_path) != recorded:
        ops.append(("README.md", card_path))

    # a person-review list for agreements that are in the listing but not yet in the published table
    # (so a week that failed before publishing lists them again next time, and a published one does not)
    published_ids = {r["id"] for r in published_rows}
    added_ids = [r["id"] for r in records if r["id"] not in published_ids] if published_rows else []
    review = cp.review_markdown(rows, added_ids, today)
    if review:
        os.makedirs(P("data/changes"), exist_ok=True)
        with open(P("data/changes", f"review-{today}.md"), "w") as f:
            f.write(review)
    review_count = review.count("\n| ") - 1 if review else 0

    published = 0
    if not ops:
        say("nothing to publish")
    else:
        say(f"to publish: {len(ops)} files in one commit")
        for repo_path, _ in ops[:12]:
            say("   +", repo_path)
        if len(ops) > 12:
            say(f"   ... and {len(ops) - 12} more")
        if args.dry_run:
            say("dry run: nothing committed to Hugging Face")
        elif not getattr(hf, "token", None) and not os.environ.get("HF_TOKEN"):
            problems.append("there is something to publish and HF_TOKEN is not set")
            write_outputs(published=0, review_count=review_count, problems=len(problems))
            for p in problems:
                say("[health] PROBLEM:", p)
            return 4
        else:
            try:
                hf.commit(ops, f"Weekly refresh {today}: {len(result['ok'])} files downloaded", revision)
                published = len(ops)
                if any(p == "README.md" for p, _ in ops):
                    open(card_state, "w").write(card_hash(card_path) + "\n")
                say("published")
            except Exception as e:  # network, auth, or the dataset changed since we read it
                say(f"[health] PROBLEM: the Hugging Face commit failed: {e!r}")
                write_outputs(published=0, review_count=review_count, problems=1)
                return 5

    write_outputs(published=published, downloaded=len(result["ok"]), failed=len(result["failed"]),
                  review_count=review_count, problems=len(problems), dry_run=str(args.dry_run).lower())
    for p in problems:
        say("[health] PROBLEM:", p)
    if result["blocked"]:
        return 3
    if problems:
        return 6
    say("[health] ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
