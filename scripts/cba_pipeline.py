"""Helpers for the weekly refresh: what to download, how to check the result, what to publish.

Everything here is plain functions. The network calls (OPM, Hugging Face) are passed in by
refresh.py, so the tests run with fakes and need neither.
"""
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "opm-cba-archive weekly refresh (https://github.com/abigailhaddad/opm-cba-archive)"
RETRY_FAILED_AFTER_DAYS = 7   # a record whose last download failed is tried again after this long
BLOCK_CODES = (403, 429)      # stop the whole run on either
CURATED_FLAGS = {"confirmed", "confirmed_secondary", "confirmed_then_reinstated"}
REVIEW_COVERAGE = {"covered", "partly_or_unclear"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------- reading state ----------

def load_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def latest_download_state(log_rows):
    """id -> the log row to trust: the last 'ok' row if there is one, else the last row."""
    state = {}
    for row in log_rows:
        if row.get("status") == "ok" or row["id"] not in state or state[row["id"]].get("status") != "ok":
            state[row["id"]] = row
    return state


def quote_url(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, ""))


def _parse_t(t):
    try:
        return dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------- what to download ----------

def plan_downloads(records, state, hf_pdf_ids, published_rows=None, now=None, force_ids=(), limit=None,
                   retry_after_days=RETRY_FAILED_AFTER_DAYS):
    """Return [{'id', 'url', 'reason'}] for the files to fetch this run, most important first.

    records: the current listing. state: latest_download_state(). hf_pdf_ids: ids that already have a
    pdfs/<id>.pdf on Hugging Face. published_rows: the table as last published; its listed_fileSize and
    fileUrl say what the listing showed when each file was last fetched, so a changed file is spotted once
    and not again after it has been published.
    Reasons: forced, new, url_changed, file_changed, missing_on_hf, retry.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    published = {r["id"]: r for r in (published_rows or [])}
    force = set(force_ids)
    order = {"forced": 0, "new": 1, "url_changed": 2, "file_changed": 3, "missing_on_hf": 4, "retry": 5}
    plan = []
    for r in records:
        rid = r["id"]
        url = quote_url(r["fileUrl"])
        s = state.get(rid)
        pub = published.get(rid)
        reason = None
        if rid in force:
            reason = "forced"
        elif s is None:
            reason = "new"
        elif s.get("status") != "ok":
            last = _parse_t(s.get("t"))
            if last is None or (now - last).days >= retry_after_days:
                reason = "retry"
        elif s.get("url") != url:
            reason = "url_changed"
        elif pub and (pub.get("listed_fileSize") != (r.get("fileSize") or "") or pub.get("fileUrl") != r["fileUrl"]):
            reason = "file_changed"
        elif rid not in hf_pdf_ids:
            reason = "missing_on_hf"
        if reason:
            plan.append({"id": rid, "url": url, "reason": reason})
    plan.sort(key=lambda x: order[x["reason"]])
    if limit is not None:
        plan = plan[:limit]
    return plan


# ---------- downloading ----------

def http_fetch(url, retries=3, backoff=5, timeout=120):
    """GET a file. Retries timeouts and 5xx; never retries a 4xx. Returns (status, content_type, body)."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise
            last = e
        except Exception as e:  # timeouts, connection resets
            last = e
        if attempt < retries - 1:
            time.sleep(backoff * 2 ** attempt)
    raise last


def download_files(plan, fetch, outdir, log_path, sleep=1.0, now=None):
    """Fetch each planned file, write it atomically and log it. Stops at the first 403 or 429.

    Returns {'ok': [ids], 'failed': [ids], 'blocked': bool}. The log schema matches scripts/download.py.
    """
    os.makedirs(outdir, exist_ok=True)
    result = {"ok": [], "failed": [], "blocked": False}
    with open(log_path, "a") as log:
        for i, item in enumerate(plan):
            rec = {"id": item["id"], "url": item["url"],
                   "t": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "reason": item["reason"]}
            blocked = False
            try:
                status, ctype, body = fetch(item["url"])
                if not body.startswith(b"%PDF-"):
                    raise ValueError(f"not a PDF (starts with {body[:8]!r})")
                dest = os.path.join(outdir, item["id"] + ".pdf")
                with open(dest + ".part", "wb") as f:
                    f.write(body)
                os.replace(dest + ".part", dest)
                rec.update(http=status, ctype=ctype, status="ok", bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), magic=body[:5].decode("latin1"))
                result["ok"].append(item["id"])
            except Exception as e:
                code = getattr(e, "code", None)
                rec.update(status="error", error=repr(e)[:300], http=code)
                result["failed"].append(item["id"])
                blocked = code in BLOCK_CODES
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if blocked:
                result["blocked"] = True
                break
            if sleep and i < len(plan) - 1:
                time.sleep(sleep)
    return result


# ---------- text extraction ----------

def extract_record(src, dst, run=subprocess.run):
    """Run pdfinfo and pdftotext -layout on one PDF. Returns the record scripts/extract.py logs."""
    rec = {"id": os.path.splitext(os.path.basename(src))[0]}
    try:
        info = run(["pdfinfo", src], capture_output=True, text=True, timeout=60, errors="replace")
        m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
        rec["pages"] = int(m.group(1)) if m else None
        rec["encrypted"] = bool(re.search(r"^Encrypted:\s+yes", info.stdout, re.M))
        rec["pdfinfo_err"] = info.stderr.strip()[:200] or None
        r = run(["pdftotext", "-layout", src, dst], capture_output=True, text=True, timeout=300, errors="replace")
        rec["pdftotext_rc"] = r.returncode
        rec["pdftotext_err"] = r.stderr.strip()[:200] or None
        txt = open(dst, encoding="utf-8", errors="replace").read() if os.path.exists(dst) else ""
        rec["chars_nonws"] = len(re.sub(r"\s", "", txt))
        rec["words"] = len(re.findall(r"[A-Za-z]{3,}", txt))
    except Exception as e:
        rec["error"] = repr(e)[:200]
    return rec


# ---------- the table ----------

NUMERIC_COLUMNS = {"download_http", "bytes", "sha256_dup_count", "pages", "words"}
BOOLEAN_COLUMNS = {"is_pdf_magic", "encrypted"}


def typed_row(row):
    """A row read back from the CSV (all strings) with its numbers and booleans restored, so that
    csv.writer(QUOTE_NONNUMERIC) writes it exactly as build_table.py wrote it."""
    out = {}
    for k, v in row.items():
        if v == "" and (k in NUMERIC_COLUMNS or k in BOOLEAN_COLUMNS):
            out[k] = None
        elif k in NUMERIC_COLUMNS:
            out[k] = int(v)
        elif k in BOOLEAN_COLUMNS:
            out[k] = v == "True"
        else:
            out[k] = v
    return out


def read_rows(path):
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(open(path, newline="")))


# ---------- checks before publishing ----------

def verify_table(rows, listing_records, prev_rows, pdf_ids, text_ids, redownloaded=()):
    """Return a list of problems with the rebuilt table. An empty list means safe to publish.

    rows: the new table (dicts of strings). prev_rows: the published table. pdf_ids / text_ids: ids that
    will have a PDF / text file on Hugging Face after this run (already there, or about to be uploaded).
    redownloaded: ids fetched this run, the only ones allowed to change hash.
    """
    problems = []
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        problems.append(f"{len(ids) - len(set(ids))} duplicate ids in the table")
    current = [r for r in rows if r.get("in_current_listing", "True") == "True"]
    listed = {r["id"] for r in listing_records}
    if len(current) != len(listing_records) or {r["id"] for r in current} != listed:
        problems.append(f"table has {len(current)} rows in the current listing, listing has {len(listing_records)}")
    new_ids = set(ids)
    lost = [r["id"] for r in prev_rows if r["id"] not in new_ids]
    if lost:
        problems.append(f"{len(lost)} rows in the published table are missing from the new one (first: {lost[0]})")
    prev = {r["id"]: r for r in prev_rows}
    redown = set(redownloaded)
    for r in rows:
        if r["download_status"] == "ok":
            if not SHA_RE.match(r.get("sha256") or ""):
                problems.append(f"{r['id']}: downloaded but no valid sha256")
            if r["is_pdf_magic"] != "True":
                problems.append(f"{r['id']}: downloaded file is not a PDF")
            if r["id"] not in pdf_ids:
                problems.append(f"{r['id']}: no PDF on Hugging Face or in this run's upload")
            if r["id"] not in text_ids:
                problems.append(f"{r['id']}: no text file on Hugging Face or in this run's upload")
        p = prev.get(r["id"])
        if p:
            if p["download_status"] == "ok" and r["id"] not in redown and r["sha256"] != p["sha256"]:
                problems.append(f"{r['id']}: hash changed without a re-download")
            if p["termination_flag"] in CURATED_FLAGS and r["termination_flag"] != p["termination_flag"]:
                problems.append(f"{r['id']}: curated flag {p['termination_flag']} changed to {r['termination_flag']}")
    return problems[:50]


def flag_changes(rows, prev_rows):
    """Existing rows whose flag changed (not an error: the rules read the listing fields, which can change)."""
    prev = {r["id"]: r["termination_flag"] for r in prev_rows}
    return [(r["id"], prev[r["id"]], r["termination_flag"]) for r in rows
            if r["id"] in prev and prev[r["id"]] != r["termination_flag"]]


# ---------- what to publish ----------

def commit_plan(rows, prev_rows, hf_files, pdf_dir, text_dir, csv_path, remote_csv_bytes, downloaded):
    """The Hugging Face commit as a list of (path_in_repo, local_path). Additions only, never deletes.

    A PDF and its text go up when the file was downloaded this run and is new to Hugging Face or has a
    different hash from the published row. The table goes up when it differs from the published one.
    """
    prev = {r["id"]: r for r in prev_rows}
    sha = {r["id"]: r["sha256"] for r in rows}
    ops = []
    for rid in sorted(downloaded):
        pdf = os.path.join(pdf_dir, rid + ".pdf")
        txt = os.path.join(text_dir, rid + ".txt")
        if not os.path.exists(pdf) or sha.get(rid) in (None, ""):
            continue
        unchanged = f"pdfs/{rid}.pdf" in hf_files and rid in prev and prev[rid]["sha256"] == sha[rid]
        if unchanged:
            continue
        ops.append((f"pdfs/{rid}.pdf", pdf))
        if os.path.exists(txt):
            ops.append((f"text/{rid}.txt", txt))
    if remote_csv_bytes != open(csv_path, "rb").read():
        ops.append(("agreements.csv", csv_path))
    return ops


def review_markdown(rows, added_ids, today):
    """Markdown list of new agreements in agencies the orders name, for a person to review."""
    new = [r for r in rows if r["id"] in set(added_ids) and r["eo_coverage"] in REVIEW_COVERAGE]
    if not new:
        return ""
    lines = [f"# New agreements to review ({today})", "",
             "These were added to OPM's listing this week and fall in agencies the executive orders name. "
             "Each has the default flag from `scripts/coverage.py` and `scripts/build_table.py`. If you find a "
             "document that shows one was terminated, add a row to `data/terminations/sources.csv` and "
             "`record_flags.csv`.", "",
             "| Agency | Unit | Union | Local | Flag | Coverage |", "|---|---|---|---|---|---|"]
    for r in sorted(new, key=lambda r: (r["agencyName"], r["laborUnionName"])):
        cells = [r["agencyName"], r["subAgencyOrComponent"] or r["activityOfficeRegion"], r["laborUnionName"],
                 r["local"], r["termination_flag"], r["eo_coverage"]]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(lines) + "\n"


def file_sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()
