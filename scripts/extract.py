"""Extract text from downloaded agreement PDFs with pdftotext; record page counts with pdfinfo.
Usage: python3 -I scripts/extract.py FILES_DIR TEXT_DIR OUT.jsonl
Each file is processed once (skips ids already in OUT.jsonl). Subprocess timeouts recorded as errors.
The work for one file is cba_pipeline.extract_record, which the weekly refresh calls too."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cba_pipeline import extract_record
fdir, tdir, outp = sys.argv[1:4]
done = set()
if os.path.exists(outp):
    done = {json.loads(l)["id"] for l in open(outp)}
out = open(outp, "a")
for fn in sorted(os.listdir(fdir)):
    if not fn.endswith(".pdf"): continue
    i = fn[:-4]
    if i in done: continue
    rec = extract_record(os.path.join(fdir, fn), os.path.join(tdir, i + ".txt"))
    out.write(json.dumps(rec) + "\n"); out.flush()
print("done")
