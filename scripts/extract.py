"""Extract text from downloaded agreement PDFs with pdftotext; record page counts with pdfinfo.
Usage: python3 -I scripts/extract.py FILES_DIR TEXT_DIR OUT.jsonl
Each file is processed once (skips ids already in OUT.jsonl). Subprocess timeouts recorded as errors."""
import sys, os, json, subprocess, re
fdir, tdir, outp = sys.argv[1:4]
done = set()
if os.path.exists(outp):
    done = {json.loads(l)["id"] for l in open(outp)}
out = open(outp, "a")
for fn in sorted(os.listdir(fdir)):
    if not fn.endswith(".pdf"): continue
    i = fn[:-4]
    if i in done: continue
    src = os.path.join(fdir, fn); dst = os.path.join(tdir, i + ".txt")
    rec = {"id": i}
    try:
        info = subprocess.run(["pdfinfo", src], capture_output=True, text=True, timeout=60, errors="replace")
        m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
        rec["pages"] = int(m.group(1)) if m else None
        rec["encrypted"] = bool(re.search(r"^Encrypted:\s+yes", info.stdout, re.M))
        rec["pdfinfo_err"] = info.stderr.strip()[:200] or None
        r = subprocess.run(["pdftotext", "-layout", src, dst], capture_output=True, text=True, timeout=300, errors="replace")
        rec["pdftotext_rc"] = r.returncode
        rec["pdftotext_err"] = r.stderr.strip()[:200] or None
        txt = open(dst, encoding="utf-8", errors="replace").read() if os.path.exists(dst) else ""
        rec["chars_nonws"] = len(re.sub(r"\s", "", txt))
        rec["words"] = len(re.findall(r"[A-Za-z]{3,}", txt))
    except Exception as e:
        rec["error"] = repr(e)[:200]
    out.write(json.dumps(rec) + "\n"); out.flush()
print("done")
