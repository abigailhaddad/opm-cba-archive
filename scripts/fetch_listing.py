"""Fetch the OPM CBA listing, validate it, and save it to data/raw/.

Exits nonzero without writing anything if the fetch or any validation fails.
"""
import argparse, datetime as dt, glob, json, os, sys, time, urllib.request

URL = "https://www.opm.gov/cba/api/documents/published"
UA = "opm-cba-archive pipeline"
PAYLOAD = {"recsPerPage": 5000, "currentPage": 1}
MAX_DROP = 0.05
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


class ValidationError(Exception):
    pass


def latest_listing(raw_dir):
    files = sorted(glob.glob(os.path.join(raw_dir, "cba_listing_*.json")))
    return files[-1] if files else None


def validate(data, prev=None, max_drop=MAX_DROP):
    """Raise ValidationError if the listing looks wrong. `prev` is the previous listing dict or None."""
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValidationError("response is not a dict with a 'results' list")
    results = data["results"]
    if data.get("rowCount") != len(results):
        raise ValidationError(f"rowCount {data.get('rowCount')} != len(results) {len(results)}")
    if not results:
        raise ValidationError("listing is empty")
    bad = [i for i, r in enumerate(results) if not isinstance(r, dict) or not r.get("id") or not r.get("fileUrl")]
    if bad:
        raise ValidationError(f"{len(bad)} records missing id or fileUrl (first index {bad[0]})")
    ids = [r["id"] for r in results]
    if len(set(ids)) != len(ids):
        raise ValidationError(f"{len(ids) - len(set(ids))} duplicate ids")
    if prev is not None:
        n_prev = len(prev.get("results", []))
        if n_prev and len(results) < n_prev * (1 - max_drop):
            raise ValidationError(f"count dropped from {n_prev} to {len(results)} (> {max_drop:.0%})")
    return True


def fetch(retries=4, backoff=5, timeout=120):
    body = json.dumps(PAYLOAD).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(URL, data=body, method="POST", headers={
                "User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # network errors, HTTP errors
            last = e
            print(f"attempt {attempt + 1} failed: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(backoff * 2 ** attempt)
    raise RuntimeError(f"fetch failed after {retries} attempts: {last}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=RAW_DIR)
    ap.add_argument("--input", help="validate/save this local file instead of fetching (for testing)")
    args = ap.parse_args(argv)
    prev_path = latest_listing(args.raw_dir)
    try:
        raw = open(args.input, "rb").read() if args.input else fetch()
        data = json.loads(raw)
        prev = json.load(open(prev_path)) if prev_path else None
        validate(data, prev)
    except (ValidationError, RuntimeError, ValueError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(args.raw_dir, f"cba_listing_{stamp}.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=1)
    print(f"saved {len(data['results'])} records to {out} (previous: {prev_path})")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new={out}\nprev={prev_path or ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
