"""Sequentially download every agreement file in the OPM CBA listing.
Usage: python3 -I scripts/download.py LISTING.json OUTDIR LOG.jsonl DEADLINE_EPOCH
Resumable: skips ids whose file already exists with a logged 'ok'. >=1 s between requests.
Stops cleanly before DEADLINE_EPOCH. Stops if cumulative bytes exceed 3 GB."""
import json, sys, os, time, hashlib, urllib.request, urllib.parse
listing, outdir, logp, deadline = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
recs = json.load(open(listing))["results"]
done = set()
if os.path.exists(logp):
    for line in open(logp):
        j = json.loads(line)
        if j["status"] == "ok": done.add(j["id"])
total = sum(os.path.getsize(os.path.join(outdir, f)) for f in os.listdir(outdir))
UA = "opm-cba-archive research script"
log = open(logp, "a")
for i, r in enumerate(recs):
    if r["id"] in done: continue
    if time.time() > deadline: print("deadline reached at index", i); break
    if total > 3e9: print("3 GB cap reached"); break
    p = urllib.parse.urlsplit(r["fileUrl"])
    url = urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, ""))
    rec = {"id": r["id"], "url": url, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            rec.update(http=resp.status, ctype=resp.headers.get("Content-Type"))
        dest = os.path.join(outdir, r["id"] + ".pdf")
        with open(dest + ".part", "wb") as f: f.write(body)
        os.replace(dest + ".part", dest)
        total += len(body)
        rec.update(status="ok", bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                   magic=body[:5].decode("latin1"))
    except Exception as e:
        rec.update(status="error", error=repr(e)[:300], http=getattr(e, "code", None))
    log.write(json.dumps(rec) + "\n"); log.flush()
    if i % 50 == 0: print(i, rec["status"], round(total/1e6), "MB", flush=True)
    time.sleep(1.0)
print("finished; total MB", round(total/1e6))
