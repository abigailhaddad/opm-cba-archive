"""OCR the scanned agreements (text_status no_text or low_text) with Tesseract.

    python3 -I scripts/ocr.py PDF_DIR [--workers 4] [--dpi 300]

PDF_DIR holds <id>.pdf files (data/files after a full download, or a folder of just the scanned ones
fetched from Hugging Face). For each record in data/cba_agreements.csv whose text_status is no_text or
low_text, it renders every page with pdftoppm (grayscale, 300 dpi), runs tesseract (English, default
page segmentation), and writes data/ocr/<id>.txt with a form feed between pages, the same page marker
pdftotext uses. One line per file goes to data/ocr_log.jsonl: the PDF's sha256, pages, words (counted
the way extract.py counts them), Tesseract's mean word confidence, and the tool versions.

A record already in the log with the same sha256 is skipped, so a rerun only does new or changed files.
Runs locally; the weekly workflow does not call it. Free tools only (poppler-utils, tesseract-ocr).
"""
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.environ.get("CBA_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
OCR_STATUSES = ("no_text", "low_text")


def tool_version(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return ((r.stdout or r.stderr).strip().splitlines() or [""])[0]


def ocr_page(png):
    """Text and the confidences of the words on one page image."""
    r = subprocess.run(["tesseract", png, "stdout", "-l", "eng", "tsv"], capture_output=True, text=True,
                       timeout=600, errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"tesseract failed on {png}: {r.stderr[-300:]}")
    lines, confs, cur, last_key = [], [], [], None
    for row in r.stdout.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or f[0] != "5":  # level 5 = a word
            continue
        key = (f[2], f[3], f[4])  # block, paragraph, line
        if key != last_key and cur:
            lines.append(" ".join(cur)); cur = []
            if last_key and key[:2] != last_key[:2]:
                lines.append("")
        last_key = key
        word = f[11]
        if word.strip():
            cur.append(word)
            if float(f[10]) >= 0:
                confs.append(float(f[10]))
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines), confs


def ocr_file(rid, pdf, out_txt, dpi):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", pdf, os.path.join(tmp, "p")],
                       check=True, capture_output=True, timeout=3600)
        pngs = sorted((f for f in os.listdir(tmp) if f.endswith(".png")),
                      key=lambda f: int(re.search(r"(\d+)\.png$", f).group(1)))
        pages, confs = [], []
        for png in pngs:
            text, c = ocr_page(os.path.join(tmp, png))
            pages.append(text); confs.extend(c)
    txt = "\f".join(pages) + "\f"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(txt)
    return {
        "id": rid,
        "sha256": hashlib.sha256(open(pdf, "rb").read()).hexdigest(),
        "pages": len(pages),
        "words": len(re.findall(r"[A-Za-z]{3,}", txt)),
        "mean_conf": round(sum(confs) / len(confs), 1) if confs else None,
        "dpi": dpi,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_dir")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)
    rows = list(csv.DictReader(open(P("data/cba_agreements.csv"), encoding="utf-8")))
    todo = [r for r in rows if r["text_status"] in OCR_STATUSES]
    log_path = P("data/ocr_log.jsonl")
    done = {}
    if os.path.exists(log_path):
        for l in open(log_path):
            j = json.loads(l); done[j["id"]] = j.get("sha256")
    os.makedirs(P("data/ocr"), exist_ok=True)
    versions = {"tesseract": tool_version(["tesseract", "--version"]), "pdftoppm": tool_version(["pdftoppm", "-v"])}
    jobs, missing = [], []
    for r in todo:
        pdf = os.path.join(args.pdf_dir, r["id"] + ".pdf")
        if done.get(r["id"]) == r["sha256"]:
            continue
        if not os.path.exists(pdf):
            missing.append(r["id"]); continue
        jobs.append((r["id"], pdf))
    print(f"{len(todo)} records need OCR; {len(jobs)} to do now; {len(todo) - len(jobs) - len(missing)} already done; "
          f"{len(missing)} PDFs not in {args.pdf_dir}", flush=True)
    failed = 0
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex, open(log_path, "a") as log:
        futs = {ex.submit(ocr_file, rid, pdf, P("data/ocr", rid + ".txt"), args.dpi): rid for rid, pdf in jobs}
        for fut in cf.as_completed(futs):
            rid = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # report and keep going; the record stays un-OCRed and is retried next run
                failed += 1
                print(f"FAILED {rid}: {e!r}", file=sys.stderr, flush=True)
                continue
            rec.update(versions, t=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            log.write(json.dumps(rec) + "\n"); log.flush()
            print(f"{rid}: {rec['pages']} pages, {rec['words']} words, mean confidence {rec['mean_conf']}", flush=True)
    for rid in missing:
        print("no PDF for", rid, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
